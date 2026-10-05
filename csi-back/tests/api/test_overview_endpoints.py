"""app.api.v1.endpoints.overview 路由测试。"""

import pytest
from unittest.mock import AsyncMock
from fastapi import FastAPI
from starlette.testclient import TestClient

from app.api.v1.endpoints import overview as overview_ep
from app.schemas.response import ApiResponseSchema
from app.middleware.response import ResponseMiddleware


@pytest.mark.asyncio
async def test_platform_status_when_es_not_ready(monkeypatch: pytest.MonkeyPatch) -> None:
    # ES 未初始化时处理函数返回 ApiResponseSchema 错误体（与 response_model 声明不一致时 HTTP 层会校验失败，故直接测协程）
    monkeypatch.setattr("app.api.v1.endpoints.overview.get_es", lambda: None)
    out = await overview_ep.get_platform_status()
    assert isinstance(out, ApiResponseSchema)
    assert out.code == 250001
    assert "连接" in out.message


def test_platform_status_success(monkeypatch: pytest.MonkeyPatch) -> None:
    # ES 可用时返回平台统计结构
    class FakeES:
        async def count(self, index):
            return {"count": 1}

        async def search(self, index, body):
            return {
                "hits": {"total": 1},
                "aggregations": {"by_platform": {"buckets": []}},
            }

    monkeypatch.setattr(
        "app.api.v1.endpoints.overview.get_es",
        lambda: FakeES(),
    )
    app = FastAPI()
    app.include_router(overview_ep.router, prefix="/api/v1")
    client = TestClient(app)
    r = client.get("/api/v1/overview/platform-status")
    assert r.status_code == 200
    body = r.json()
    assert body["total_doc_count"] == 1
    assert "by_platform" in body


def test_latest_intelligence_success_and_response_envelope(monkeypatch: pytest.MonkeyPatch) -> None:
    """最新情报经响应中间件包装后保留实际最后编辑时间。"""
    es = AsyncMock()
    es.search.return_value = {"hits": {"hits": [{
        "_id": "article-id",
        "_index": "article",
        "_source": {"title": "最新情报", "last_edit_at": "2026-10-05T10:00:00"},
    }]}}
    monkeypatch.setattr(overview_ep, "get_es", lambda: es)
    app = FastAPI()
    app.include_router(overview_ep.router, prefix="/api/v1")
    app.add_middleware(ResponseMiddleware)
    with TestClient(app) as client:
        response = client.get("/api/v1/overview/latest-intelligence")
    assert response.status_code == 200
    body = response.json()
    assert body["code"] == 0
    assert body["data"]["items"][0]["last_edit_at"] == "2026-10-05T10:00:00+08:00"
    assert body["data"]["items"][0]["uuid"] == "article-id"
    assert es.search.call_args.kwargs["body"]["size"] == 3


@pytest.mark.parametrize("limit", [1, 12])
def test_latest_intelligence_accepts_limit_bounds(monkeypatch: pytest.MonkeyPatch, limit: int) -> None:
    """最新情报条数允许一到十二条。"""
    es = AsyncMock()
    es.search.return_value = {"hits": {"hits": []}}
    monkeypatch.setattr(overview_ep, "get_es", lambda: es)
    app = FastAPI()
    app.include_router(overview_ep.router, prefix="/api/v1")
    with TestClient(app) as client:
        response = client.get("/api/v1/overview/latest-intelligence", params={"limit": limit})
    assert response.status_code == 200
    assert response.json() == {"items": []}
    assert es.search.call_args.kwargs["body"]["size"] == limit


@pytest.mark.parametrize("limit", [0, 13, "无效数量"])
def test_latest_intelligence_rejects_invalid_limit(limit) -> None:
    """越界或非整数数量应在调用后端查询前拒绝。"""
    app = FastAPI()
    app.include_router(overview_ep.router, prefix="/api/v1")
    with TestClient(app) as client:
        response = client.get("/api/v1/overview/latest-intelligence", params={"limit": limit})
    assert response.status_code == 422


@pytest.mark.parametrize("unavailable", [True, False])
def test_latest_intelligence_error_response_is_valid(monkeypatch: pytest.MonkeyPatch, unavailable: bool) -> None:
    """连接缺失与查询异常都返回可通过响应模型校验的业务错误。"""
    es = AsyncMock()
    es.search.side_effect = RuntimeError("测试查询失败")
    monkeypatch.setattr(overview_ep, "get_es", lambda: None if unavailable else es)
    app = FastAPI()
    app.include_router(overview_ep.router, prefix="/api/v1")
    app.add_middleware(ResponseMiddleware)
    with TestClient(app) as client:
        response = client.get("/api/v1/overview/latest-intelligence")
    assert response.status_code == 200
    assert response.json()["code"] == (250001 if unavailable else 250007)
    assert response.json()["data"] is None
