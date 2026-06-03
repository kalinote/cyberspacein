"""app.service.search 查询构建与 ES 辅助函数测试。"""

from datetime import datetime, timezone

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
