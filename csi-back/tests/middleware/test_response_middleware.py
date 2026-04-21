"""app.middleware.response ResponseMiddleware 行为测试。"""

from fastapi import FastAPI
from fastapi.responses import JSONResponse, PlainTextResponse
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response
from starlette.testclient import TestClient

from app.middleware.response import ResponseMiddleware


def _build_client_with_middleware() -> TestClient:
    app = FastAPI()

    class InnerRaiseMiddleware(BaseHTTPMiddleware):
        async def dispatch(self, request, call_next):
            if request.url.path == "/inner-boom":
                raise ValueError("内部模拟异常")
            return await call_next(request)

    app.add_middleware(InnerRaiseMiddleware)
    app.add_middleware(ResponseMiddleware)

    @app.get("/json-dict-no-code")
    def json_dict_no_code():
        return {"hello": "world"}

    @app.get("/json-list")
    def json_list():
        return [1, 2, 3]

    @app.get("/already-wrapped")
    def already_wrapped():
        return JSONResponse(
            content={"code": 0, "message": "ok", "data": {"x": 1}},
            status_code=200,
        )

    @app.get("/non-200")
    def non_200():
        return PlainTextResponse("nope", status_code=404)

    @app.get("/non-json-200")
    def non_json_200():
        return PlainTextResponse("plain", status_code=200)

    @app.get("/bad-json-body")
    def bad_json_body():
        return Response(
            content=b"{not-json",
            media_type="application/json",
            status_code=200,
        )

    @app.get("/inner-boom")
    def inner_boom_route():
        return {"never": "reached"}

    return TestClient(app)


def test_middleware_wraps_plain_dict_json_with_success_envelope():
    # 200 + application/json 且 body 无 code 字段时，应包一层 ApiResponseSchema.success
    client = _build_client_with_middleware()
    r = client.get("/json-dict-no-code")
    assert r.status_code == 200
    body = r.json()
    assert body["code"] == 0
    assert body["message"] == "success"
    assert body["data"] == {"hello": "world"}


def test_middleware_wraps_json_array_with_success_envelope():
    # 非 dict 的合法 JSON（如列表）同样包一层 success，data 为列表
    client = _build_client_with_middleware()
    r = client.get("/json-list")
    assert r.status_code == 200
    body = r.json()
    assert body["code"] == 0
    assert body["data"] == [1, 2, 3]


def test_middleware_passes_through_when_code_present():
    # body 已为带 code 的字典时不再二次包装，原样返回
    client = _build_client_with_middleware()
    r = client.get("/already-wrapped")
    assert r.status_code == 200
    assert r.json() == {"code": 0, "message": "ok", "data": {"x": 1}}


def test_middleware_skips_openapi_docs_paths():
    # /openapi.json、/docs、/redoc 不经过包装逻辑；关闭框架自带 OpenAPI 以便固定响应体
    app = FastAPI(openapi_url=None)
    app.add_middleware(ResponseMiddleware)

    @app.get("/openapi.json")
    def openapi_stub():
        return {"openapi": "3.0.0"}

    client = TestClient(app)
    r = client.get("/openapi.json")
    assert r.status_code == 200
    assert r.json() == {"openapi": "3.0.0"}


def test_middleware_skips_docs_path():
    # /docs 在排除列表中，200 JSON 不应再包一层 ApiResponseSchema（需关闭自带 Swagger 路径）
    app = FastAPI(docs_url=None)
    app.add_middleware(ResponseMiddleware)

    @app.get("/docs")
    def docs_stub():
        return {"docs": "stub"}

    client = TestClient(app)
    r = client.get("/docs")
    assert r.status_code == 200
    assert r.json() == {"docs": "stub"}


def test_middleware_skips_redoc_path():
    # /redoc 在排除列表中，200 JSON 不应再包一层 ApiResponseSchema（需关闭自带 ReDoc 路径）
    app = FastAPI(redoc_url=None)
    app.add_middleware(ResponseMiddleware)

    @app.get("/redoc")
    def redoc_stub():
        return {"redoc": "stub"}

    client = TestClient(app)
    r = client.get("/redoc")
    assert r.status_code == 200
    assert r.json() == {"redoc": "stub"}


def test_middleware_non_json_200_unchanged():
    # 200 但非 JSON Content-Type 时直接透传
    client = _build_client_with_middleware()
    r = client.get("/non-json-200")
    assert r.status_code == 200
    assert r.text == "plain"


def test_middleware_non_200_unchanged():
    # 非 200 状态码不进入 JSON 包装分支
    client = _build_client_with_middleware()
    r = client.get("/non-200")
    assert r.status_code == 404
    assert r.text == "nope"


def test_middleware_invalid_json_returns_raw_body():
    # 声明为 JSON 但内容无法解析时，返回原始字节与状态码
    client = _build_client_with_middleware()
    r = client.get("/bad-json-body")
    assert r.status_code == 200
    assert r.content == b"{not-json"


def test_middleware_outer_exception_returns_error_envelope():
    # 内层中间件在 call_next 前抛错时，外层捕获并返回统一错误 JSON（HTTP 200）
    client = _build_client_with_middleware()
    r = client.get("/inner-boom")
    assert r.status_code == 200
    body = r.json()
    assert body["code"] != 0
    assert "服务器内部错误" in body["message"]
