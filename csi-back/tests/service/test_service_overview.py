"""app.service.overview 纯函数与 ES 结果解析测试。"""

from datetime import datetime

import pytest

from app.schemas.overview import OverviewTimeUnitEnum
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
