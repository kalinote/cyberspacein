"""app.service.search 查询构建与 ES 辅助函数测试。"""

from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from app.schemas.constants import SearchModeEnum
from app.schemas.search import EntityKeywordSearchParams, EntitySearchRequestSchema
from app.service import search as search_svc


def test_get_es_total():
    assert search_svc._get_es_total({"hits": {"total": {"value": 5}}}) == 5
    assert search_svc._get_es_total({"hits": {"total": 9}}) == 9


def test_build_filter_must_empty():
    # 无筛选条件时 must 列表为空
    p = EntitySearchRequestSchema()
    assert search_svc.build_filter_must(p) == []


def test_build_filter_must_platform_and_flags():
    # 平台、布尔筛选与时间范围应生成对应子句
    tz = timezone.utc
    p = EntitySearchRequestSchema(
        platform="p1",
        entity_type=["article", "forum"],
        aigc=True,
        nsfw=False,
        is_highlighted=True,
        start_at=datetime(2024, 1, 1, tzinfo=tz),
        end_at=datetime(2024, 2, 1, tzinfo=tz),
    )
    must = search_svc.build_filter_must(p)
    assert {"term": {"platform.keyword": "p1"}} in must
    assert {"term": {"aigc": True}} in must
    assert {"term": {"nsfw": False}} in must
    assert {"term": {"is_highlighted": True}} in must
    range_clause = next(x for x in must if "range" in x)
    assert "last_edit_at" in range_clause["range"]


def test_keyword_query_body_has_highlight_when_keywords():
    # 有有效关键词时应带 highlight 配置
    p = EntitySearchRequestSchema(keywords="测试", page=1, page_size=10)
    body = search_svc.keyword_query_body(p, 0, 10)
    assert "highlight" in body
    assert body["query"]["bool"]["must"]


def test_keyword_query_body_no_highlight_without_keywords():
    p = EntitySearchRequestSchema(keywords=None, page=1, page_size=10)
    body = search_svc.keyword_query_body(p, 0, 10)
    assert "highlight" not in body


def test_normalize_keywords_dedupes():
    assert search_svc._normalize_keywords(["a", "  a ", "", "b"]) == ["a", "b"]


def test_build_keyword_must_clause_and():
    clause = search_svc.build_keyword_must_clause(["foo", "bar"], "and")
    assert clause is not None
    assert "must" in clause["bool"]
    assert len(clause["bool"]["must"]) == 2


def test_build_keyword_must_clause_or():
    clause = search_svc.build_keyword_must_clause(["foo", "bar"], "or")
    assert clause is not None
    assert clause["bool"]["minimum_should_match"] == 1
    assert len(clause["bool"]["should"]) == 2


def test_hit_to_tool_search_hit_snippets_and_plain_title():
    hit = {
        "_id": "id1",
        "_source": {
            "uuid": "u1",
            "entity_type": "article",
            "title": "完整标题",
        },
        "highlight": {
            "clean_content": [
                "片段<em>一</em>",
                "<em>二</em>片段",
            ],
            "title": ["<em>完整</em>标题"],
        },
    }
    item = search_svc.hit_to_tool_search_hit(hit)
    assert item.title == "完整标题"
    assert len(item.snippets) == 2
    assert item.keywords_hits >= 2
    assert item.uuid == "u1"
    assert item.entity_type == "article"


def test_keyword_list_query_body_with_keywords():
    p = EntityKeywordSearchParams(
        keywords=["测试", "关键词"],
        keyword_match_mode="and",
        page=1,
        page_size=5,
    )
    body = search_svc.keyword_list_query_body(p, 0, 5)
    assert "highlight" in body
    must = body["query"]["bool"]["must"]
    assert any("must" in m.get("bool", {}) for m in must if "bool" in m)


@pytest.mark.parametrize("entity_types", [None, ["post"], ["article", "post"]])
def test_post_date_filter_falls_back_without_changing_existing_entities(entity_types):
    """贴文按缺失字段回退时间，文章和论坛仍按编辑时间筛选。"""
    params = EntitySearchRequestSchema(
        entity_type=entity_types,
        start_at=datetime(2026, 10, 16, tzinfo=timezone.utc),
    )
    date_filter = search_svc.build_filter_must(params)[-1]["bool"]

    assert date_filter["minimum_should_match"] == 1
    assert "last_edit_at" in date_filter["should"][0]["range"]
    fallback = date_filter["should"][1]["bool"]
    assert fallback["filter"] == [{"term": {"entity_type.keyword": "post"}}]
    assert fallback["must_not"] == [{"exists": {"field": "last_edit_at"}}]
    assert "publish_at" in fallback["should"][0]["range"]
    missing_publication = fallback["should"][1]["bool"]
    assert missing_publication["must_not"] == [{"exists": {"field": "publish_at"}}]
    assert "crawled_at" in missing_publication["filter"][0]["range"]


@pytest.mark.parametrize("sort_by", ["time", "last_edit_at", "publish_at", "crawled_at", "priority"])
def test_sort_accepts_indices_without_optional_fields(sort_by):
    """新贴文索引尚无编辑时间或信任度映射时仍可排序。"""
    body = search_svc.keyword_query_body(EntitySearchRequestSchema(sort_by=sort_by), 0, 5)

    assert all("unmapped_type" in next(iter(item.values())) for item in body["sort"])
    if sort_by == "priority":
        assert body["sort"][0] == {
            "confidence": {"order": "desc", "missing": "_last", "unmapped_type": "double"}
        }


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("keywords", "mode"),
    [(None, SearchModeEnum.KEYWORD), ("贴文", SearchModeEnum.KEYWORD),
     ("贴文", SearchModeEnum.VECTOR), ("贴文", SearchModeEnum.HYBRID)],
)
async def test_all_search_modes_include_posts_and_tolerate_missing_indices(monkeypatch, keywords, mode):
    """各检索模式都查询贴文，并兼容尚未创建贴文索引的部署。"""
    hit = {
        "_id": "post-1", "_index": "post", "_score": 1,
        "_source": {
            "uuid": "post-1", "entity_type": "post", "source_id": "source-1",
            "platform": "twitter", "author_name": None, "keywords": None,
            "clean_content": "贴文正文 <测试>", "update_at": "2026-10-16T15:00:00",
        },
    }
    es = SimpleNamespace(search=AsyncMock(return_value={
        "hits": {"total": {"value": 1}, "hits": [hit]},
    }))
    monkeypatch.setattr(search_svc.PlatformModel, "find_one", AsyncMock(return_value=SimpleNamespace(id="twitter-id")))
    embed = AsyncMock(return_value=[0.1, 0.2])
    monkeypatch.setattr(search_svc, "embed_query_async", embed)

    response = await search_svc.search_entity(es, EntitySearchRequestSchema(
        keywords=keywords, search_mode=mode, entity_type=["post"], platform="twitter",
    ))

    assert response.total == (2 if mode == SearchModeEnum.HYBRID else 1)
    assert len(response.items) == 1
    assert response.items[0].entity_type == "post"
    assert response.items[0].platform_id == "twitter-id"
    assert response.items[0].title == "贴文正文 &lt;测试&gt;"
    assert response.items[0].keywords == []
    assert response.items[0].author_name == ""
    for args in es.search.call_args_list:
        assert args.kwargs["index"] == ["article", "forum", "post"]
        assert args.kwargs["ignore_unavailable"] is True
        assert args.kwargs["allow_no_indices"] is True
    if mode == SearchModeEnum.KEYWORD:
        embed.assert_not_awaited()


@pytest.mark.asyncio
async def test_platform_related_search_http_endpoint_returns_posts(monkeypatch):
    """平台关联情报沿用公开检索接口及平台精确过滤。"""
    from fastapi import FastAPI
    from httpx import ASGITransport, AsyncClient
    from app.api.v1.endpoints import search as endpoint
    from app.middleware.response import ResponseMiddleware

    hit = {
        "_id": "post-1", "_source": {
            "entity_type": "post", "platform": "twitter", "clean_content": "贴文正文",
            "update_at": "2026-10-16T15:00:00",
        },
    }
    es = SimpleNamespace(search=AsyncMock(return_value={
        "hits": {"total": {"value": 1}, "hits": [hit]},
    }))
    monkeypatch.setattr(endpoint, "get_es", lambda: es)
    monkeypatch.setattr(search_svc.PlatformModel, "find_one", AsyncMock(return_value=SimpleNamespace(id="twitter-id")))
    app = FastAPI()
    app.add_middleware(ResponseMiddleware)
    app.include_router(endpoint.router, prefix="/api/v1")

    async with AsyncClient(transport=ASGITransport(app), base_url="http://test") as client:
        response = await client.post("/api/v1/search/entity", json={
            "platform": "twitter", "entity_type": ["post"], "sort_by": "time",
        })

    assert response.status_code == 200
    assert response.json()["data"]["items"][0]["entity_type"] == "post"
    query = es.search.call_args.kwargs["body"]["query"]
    assert {"term": {"platform.keyword": "twitter"}} in query["bool"]["filter"]
