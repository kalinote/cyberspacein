"""app.api.v1.endpoints.overview 路由测试。"""

import pytest
from fastapi import FastAPI
from starlette.testclient import TestClient

from app.api.v1.endpoints import overview as overview_ep
from app.schemas.response import ApiResponseSchema


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
