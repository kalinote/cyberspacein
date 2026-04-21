"""app.service.search 查询构建与 ES 辅助函数测试。"""

from datetime import datetime, timezone

from app.schemas.constants import SearchModeEnum
from app.schemas.search import EntitySearchRequestSchema
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
