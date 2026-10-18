"""验证贴文详情契约、媒体保留及既有平台名称关联规则。"""

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from elastic_transport import ApiResponseMeta, NodeConfig
from elasticsearch import NotFoundError
from fastapi import FastAPI
from starlette.testclient import TestClient

from app.api.v1.endpoints import post as endpoint
from app.core import route_permissions
from app.core.exceptions import ForbiddenException
from starlette.requests import Request


@pytest.fixture
def post_client(monkeypatch):
    """使用独立路由和可追踪的索引客户端隔离真实数据库。"""
    es = SimpleNamespace(get=AsyncMock())
    platform_lookup = AsyncMock(return_value=SimpleNamespace(id="platform-1"))
    monkeypatch.setattr(endpoint, "get_es", lambda: es)
    monkeypatch.setattr(endpoint.PlatformModel, "find_one", platform_lookup)
    app = FastAPI()
    app.include_router(endpoint.router, prefix="/api/v1")
    return TestClient(app), es, platform_lookup


def test_post_detail_preserves_media_and_resolves_standard_platform(post_client):
    """媒体归档结果、关系和正文完整返回，平台仅按正式名称查询。"""
    client, es, lookup = post_client
    source = {
        "uuid": "post-1", "entity_type": "post", "platform": "Twitter",
        "spider_name": "twitter", "post_type": "reply", "parent_id": "parent-1",
        "clean_content": "正文", "raw_content": '{"text":"正文"}',
        "publish_at": "2026-10-16T08:00:00+00:00", "crawled_at": "2026-10-16T08:01:00Z",
        "metrics": {"likes": 0, "views": -1}, "mentions": ["user-1"],
        "entities": {"person": ["作者"]}, "clean_content_vector": [0.1, 0.2],
        "media_resources": [{"source_url": "https://source.example/a.mp4", "stored_url": "https://storage.example/hash", "content_type": "video/mp4", "status": "stored", "media_id": "media-1", "type": "video"}],
        "files_urls": ["https://storage.example/hash"],
        "media_summary": {"status": "complete", "total": 1, "stored": 1},
    }
    es.get.return_value = {"_source": source}
    response = client.get("/api/v1/post/detail/post-1")
    assert response.status_code == 200 and response.json()["code"] == 0
    data = response.json()["data"]
    for field in ("platform", "spider_name", "post_type", "parent_id", "mentions", "raw_content", "media_resources", "files_urls", "media_summary", "metrics"):
        assert data[field] == source[field]
    assert data["platform_uuid"] == "platform-1"
    assert data["publish_at"] == "2026-10-16T08:00:00Z"
    assert data["entities"]["person"] == ["作者"]
    assert "clean_content_vector" not in data
    es.get.assert_awaited_once_with(index="post", id="post-1")
    lookup.assert_awaited_once_with({"name": "Twitter"})


@pytest.mark.parametrize("media", [None, [], ["https://storage.example/a.jpg"]])
def test_post_detail_allows_missing_optional_fields(post_client, media):
    """仅含媒体或缺少标题作者等可选字段的贴文仍可读取。"""
    client, es, _ = post_client
    es.get.return_value = {"_source": {"media_resources": media}}
    data = client.get("/api/v1/post/detail/post-1").json()["data"]
    assert data["uuid"] == "post-1" and data["entity_type"] == "post"
    assert data["media_resources"] == media
    assert data["title"] is None and data["entities"] is None


def test_post_detail_platform_lookup_failure_does_not_hide_content(post_client):
    """平台暂不可用时仍可展示已存储的贴文与媒体。"""
    client, es, lookup = post_client
    es.get.return_value = {"_source": {"platform": "Twitter", "clean_content": "正文"}}
    lookup.side_effect = RuntimeError("平台库暂不可用")
    result = client.get("/api/v1/post/detail/post-1").json()
    assert result["code"] == 0 and result["data"]["platform_uuid"] is None


def test_post_detail_handles_missing_index_or_record(post_client):
    """索引或贴文不存在时返回系统统一的未找到状态。"""
    client, es, _ = post_client
    es.get.side_effect = NotFoundError("不存在", meta=ApiResponseMeta(404, "1.1", {}, 0, NodeConfig("http", "localhost", 9200)), body={})
    result = client.get("/api/v1/post/detail/missing").json()
    assert result["code"] == 240415 and "贴文不存在" in result["message"]


def test_post_detail_handles_unavailable_es(post_client, monkeypatch):
    """连接未初始化和查询失败均返回可识别的业务错误。"""
    client, es, _ = post_client
    monkeypatch.setattr(endpoint, "get_es", lambda: None)
    assert client.get("/api/v1/post/detail/post-1").json()["code"] == 250001
    monkeypatch.setattr(endpoint, "get_es", lambda: es)
    es.get.side_effect = RuntimeError("查询暂不可用")
    assert client.get("/api/v1/post/detail/post-1").json()["code"] == 250002


@pytest.mark.asyncio
async def test_post_detail_requires_its_own_read_permission(monkeypatch):
    """贴文详情不能仅凭文章读取权限放行，必须检查贴文读取权限。"""
    request = Request({"type": "http", "method": "GET", "path": "/api/v1/post/detail/post-1", "headers": [], "route": SimpleNamespace(path="/api/v1/post/detail/{uuid}")})
    user = SimpleNamespace(id="user-1")
    monkeypatch.setattr(route_permissions, "get_current_auth_context", AsyncMock(return_value=SimpleNamespace(user=user)))
    allowed = AsyncMock(return_value=False)
    monkeypatch.setattr(route_permissions, "has_backend_permissions", allowed)
    with pytest.raises(ForbiddenException):
        await route_permissions.authorize_registered_route(request, None)
    allowed.assert_awaited_once_with(user, ["operation:content:post:read"])
    allowed.return_value = True
    await route_permissions.authorize_registered_route(request, None)
