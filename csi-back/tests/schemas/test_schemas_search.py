"""app.schemas.search 搜索请求与结果 Schema 测试。"""

import pytest
from datetime import datetime, timezone

from app.schemas.constants import SearchModeEnum
from app.schemas.search import (
    EntitySearchRequestSchema,
    SearchResultSchema,
    SearchTemplateCreateRequestSchema,
)


def test_entity_search_request_inherits_page_defaults():
    # 继承分页默认值与搜索模式默认
    r = EntitySearchRequestSchema()
    assert r.page == 1
    assert r.page_size == 10
    assert r.search_mode == SearchModeEnum.KEYWORD


def test_entity_search_request_time_range_optional():
    # 时间范围与筛选条件可选
    tz = timezone.utc
    r = EntitySearchRequestSchema(
        start_at=datetime(2024, 1, 1, tzinfo=tz),
        end_at=datetime(2024, 12, 31, tzinfo=tz),
        platform="twitter",
        aigc=False,
    )
    assert r.platform == "twitter"
    assert r.aigc is False


def test_search_result_schema_minimal():
    # 搜索结果必填字段
    tz = timezone.utc
    SearchResultSchema(
        uuid="u1",
        entity_type="article",
        source_id="s1",
        data_version=1,
        platform="p",
        section="",
        update_at=datetime.now(tz),
        author_name="a",
        nsfw=False,
        aigc=False,
        keywords=[],
        title="t",
    )


def test_search_template_create_rejects_empty_title():
    # 标题与查询串有最小长度约束
    with pytest.raises(Exception):
        SearchTemplateCreateRequestSchema(title="", description="d", search_query="q")
