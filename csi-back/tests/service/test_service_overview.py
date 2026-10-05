"""app.service.overview 纯函数与 ES 结果解析测试。"""

from datetime import datetime, timedelta
from unittest.mock import AsyncMock

import pytest

from app.schemas.overview import OverviewTimeUnitEnum
from app.schemas.constants import ALL_INDEX
from app.service import overview as overview_svc


def test_get_es_total_dict_and_int():
    # ES 7+ total 为对象或整数两种形态
    assert overview_svc._get_es_total({"hits": {"total": {"value": 42}}}) == 42
    assert overview_svc._get_es_total({"hits": {"total": 7}}) == 7


def test_calendar_interval():
    # 与 date_histogram 的 calendar_interval 对应
    assert overview_svc._calendar_interval(OverviewTimeUnitEnum.day) == "1d"
    assert overview_svc._calendar_interval(OverviewTimeUnitEnum.week) == "1w"
    assert overview_svc._calendar_interval(OverviewTimeUnitEnum.month) == "1M"


def test_change_rate_percent():
    # 桶数不足 2 且首桶非 0 时变化率为 0；首桶为 0 时无意义
    assert overview_svc._change_rate_percent(10, 20, 1) == 0.0
    assert overview_svc._change_rate_percent(0, 5, 3) is None
    assert overview_svc._change_rate_percent(10, 30, 5) == 200.0


def test_compute_time_window_day():
    # 近 n 天窗口：起始日为 today-(n-1) 的零点
    tz = overview_svc.TZ_SH
    now = datetime(2025, 6, 15, 14, 30, 0, tzinfo=tz)
    start, end = overview_svc.compute_time_window(OverviewTimeUnitEnum.day, 3, now=now)
    assert start == datetime(2025, 6, 13, 0, 0, 0, tzinfo=tz)
    assert end == now.replace(microsecond=0)


def test_bucket_period_start_from_key_as_string():
    # 优先使用 key_as_string 解析时间
    tz = overview_svc.TZ_SH
    b = {"key_as_string": "2025-01-01T00:00:00.000+08:00"}
    dt = overview_svc._bucket_period_start(b)
    assert dt.tzinfo is not None


def test_bucket_period_start_from_key_ms():
    # 毫秒时间戳兜底
    b = {"key": 1704067200000}
    dt = overview_svc._bucket_period_start(b)
    assert isinstance(dt, datetime)


def test_max_agg_to_datetime_empty():
    assert overview_svc._max_agg_to_datetime({}) is None


def test_today_range_bounds_microsecond_stripped():
    tz = overview_svc.TZ_SH
    now = datetime(2025, 3, 1, 15, 0, 0, 123456, tzinfo=tz)
    a, b = overview_svc._today_range_bounds(now)
    assert a.microsecond == 0
    assert b.microsecond == 0


@pytest.mark.asyncio
async def test_fetch_platform_status_shapes(monkeypatch: pytest.MonkeyPatch) -> None:
    # 聚合结果应映射为 OverviewPlatformStatusSchema
    class FakeES:
        async def count(self, index):
            return {"count": 100}

        async def search(self, index, body):
            return {
                "hits": {"total": 100},
                "aggregations": {
                    "by_platform": {
                        "buckets": [
                            {"key": "tw", "doc_count": 10},
                            {"key": 99, "doc_count": 2},
                        ]
                    }
                },
            }

    out = await overview_svc.fetch_platform_status(FakeES())
    assert out.total_doc_count == 100
    assert len(out.by_platform) == 2
    assert out.by_platform[0].platform == "tw"


@pytest.mark.asyncio
async def test_fetch_summary_status(monkeypatch: pytest.MonkeyPatch) -> None:
    class FakeES:
        async def search(self, index, body):
            return {
                "hits": {"total": {"value": 50}},
                "aggregations": {
                    "today_crawled": {"doc_count": 3},
                    "today_new": {"doc_count": 4},
                    "latest_last_edit": {"value": None, "value_as_string": None},
                },
            }

    out = await overview_svc.fetch_summary_status(FakeES())
    assert out.total_doc_count == 50
    assert out.today_crawl_count == 3
    assert out.today_new_count == 4


@pytest.mark.asyncio
async def test_fetch_latest_intelligence_uses_last_edit_at_and_cross_index() -> None:
    """验证最新情报仅按最后编辑时间查询跨索引真实记录。"""
    es = AsyncMock()
    es.search.return_value = {
        "hits": {"hits": [
            {
                "_id": "article-id",
                "_index": "article",
                "_source": {
                    "uuid": "article-uuid",
                    "entity_type": "article",
                    "title": "最新文章",
                    "clean_content": "正文" * 150,
                    "platform": "新闻平台",
                    "section": "资讯",
                    "last_edit_at": "2026-10-05T10:00:00+08:00",
                    "update_at": "2026-10-01T10:00:00+08:00",
                    "is_highlighted": True,
                },
            },
            {
                "_id": "forum-id",
                "_index": "forum",
                "_source": {
                    "uuid": None,
                    "entity_type": None,
                    "title": None,
                    "clean_content": None,
                    "platform": None,
                    "section": None,
                    "last_edit_at": "2026-10-04T10:00:00",
                    "update_at": "2026-10-06T10:00:00+08:00",
                    "is_highlighted": None,
                },
            },
        ]},
    }

    result = await overview_svc.fetch_latest_intelligence(es, 3)

    request = es.search.call_args.kwargs
    assert request["index"] == ALL_INDEX
    assert request["body"]["size"] == 3
    assert request["body"]["query"] == {"exists": {"field": "last_edit_at"}}
    assert request["body"]["sort"] == [
        {"last_edit_at": {"order": "desc", "unmapped_type": "date"}}
    ]
    assert set(request["body"]["_source"]) == {
        "uuid", "entity_type", "title", "clean_content", "platform",
        "section", "last_edit_at", "is_highlighted",
    }
    assert [item.uuid for item in result.items] == ["article-uuid", "forum-id"]
    article, forum = result.items
    assert article.last_edit_at > forum.last_edit_at
    assert article.title == "最新文章"
    assert article.clean_content == "正文" * 100
    assert article.is_highlighted is True
    assert forum.entity_type == "forum"
    assert forum.title == forum.clean_content == forum.platform == forum.section == ""
    assert forum.is_highlighted is False
    assert forum.last_edit_at.utcoffset() == timedelta(hours=8)
    assert forum.last_edit_at.isoformat() == "2026-10-04T10:00:00+08:00"


@pytest.mark.asyncio
@pytest.mark.parametrize("source_time, expected", [
    ("2026-10-04T19:31:50", "2026-10-04T19:31:50+08:00"),
    ("2026-10-04T19:31:50+08:00", "2026-10-04T19:31:50+08:00"),
    ("2026-10-04T19:31:50Z", "2026-10-05T03:31:50+08:00"),
])
async def test_fetch_latest_intelligence_preserves_source_time_semantics(source_time, expected) -> None:
    """沿用源记录的时间语义，无时区值按北京时间处理，显式时区正常转换。"""
    es = AsyncMock()
    es.search.return_value = {
        "hits": {"hits": [{
            "_id": "article-id",
            "_index": "article",
            "_source": {"last_edit_at": source_time},
        }]},
    }
    result = await overview_svc.fetch_latest_intelligence(es, 3)
    assert result.items[0].last_edit_at.isoformat() == expected


@pytest.mark.asyncio
@pytest.mark.parametrize("index, source_type, expected", [
    ("article", "post", "article"),
    ("forum", "article", "forum"),
    (None, "Article", "article"),
    ("未知索引", "Forum", "forum"),
    ("未知索引", "post", None),
    (None, None, None),
])
async def test_fetch_latest_intelligence_only_returns_supported_entity_types(index, source_type, expected) -> None:
    """优先采用已知索引类型，并排除没有对应详情页的实体。"""
    es = AsyncMock()
    es.search.return_value = {
        "hits": {"hits": [{
            "_id": "entity-id",
            "_index": index,
            "_source": {"entity_type": source_type, "last_edit_at": "2026-10-04T19:31:50"},
        }]},
    }
    result = await overview_svc.fetch_latest_intelligence(es, 3)
    if expected is None:
        assert result.items == []
    else:
        assert result.items[0].entity_type == expected


@pytest.mark.asyncio
@pytest.mark.parametrize("last_edit_at", [None, "", "无效时间"])
async def test_fetch_latest_intelligence_does_not_fallback_to_other_times(last_edit_at) -> None:
    """无有效最后编辑时间时不得使用发布时间或入库时间替代。"""
    es = AsyncMock()
    es.search.return_value = {
        "hits": {"hits": [{
            "_id": "article-id",
            "_index": "article",
            "_source": {
                "last_edit_at": last_edit_at,
                "publish_at": "2026-10-05T10:00:00+08:00",
                "update_at": "2026-10-05T10:00:00+08:00",
                "crawled_at": "2026-10-05T10:00:00+08:00",
            },
        }]},
    }
    assert (await overview_svc.fetch_latest_intelligence(es, 3)).items == []


@pytest.mark.asyncio
async def test_fetch_latest_intelligence_empty() -> None:
    """无情报时返回空列表。"""
    es = AsyncMock()
    es.search.return_value = {"hits": {"hits": []}}
    assert (await overview_svc.fetch_latest_intelligence(es, 3)).items == []
