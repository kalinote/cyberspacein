import logging
from datetime import date, datetime, timedelta, timezone
from typing import Optional

from elasticsearch import AsyncElasticsearch

from app.schemas.constants import ALL_INDEX
from app.schemas.overview import (
    OverviewPlatformCountSchema,
    OverviewPlatformStatusSchema,
    OverviewSummaryStatusSchema,
    OverviewTimeBucketSchema,
    OverviewTimeSeriesStatsSchema,
    OverviewTimeUnitEnum,
)
from app.utils.date_time import parse_datetime

logger = logging.getLogger(__name__)

TZ_SH = timezone(timedelta(hours=8))


def _get_es_total(result: dict) -> int:
    total = result["hits"]["total"]
    return total["value"] if isinstance(total, dict) else total


def _start_of_month(d: date) -> date:
    return date(d.year, d.month, 1)


def _subtract_months_from_first_of_month(d: date, months: int) -> date:
    anchor = _start_of_month(d)
    y, m = anchor.year, anchor.month
    m -= months
    while m <= 0:
        m += 12
        y -= 1
    return date(y, m, 1)


def compute_time_window(
    unit: OverviewTimeUnitEnum, n: int, now: Optional[datetime] = None
) -> tuple[datetime, datetime]:
    if now is None:
        now = datetime.now(TZ_SH)
    elif now.tzinfo is None:
        now = now.replace(tzinfo=TZ_SH)
    else:
        now = now.astimezone(TZ_SH)
    now = now.replace(microsecond=0)
    today = now.date()

    if unit == OverviewTimeUnitEnum.day:
        start_d = today - timedelta(days=n - 1)
    elif unit == OverviewTimeUnitEnum.week:
        start_d = today - timedelta(days=n * 7 - 1)
    else:
        start_d = _subtract_months_from_first_of_month(today, n)

    start_local = datetime.combine(start_d, datetime.min.time(), tzinfo=TZ_SH)
    return start_local, now


def _calendar_interval(unit: OverviewTimeUnitEnum) -> str:
    if unit == OverviewTimeUnitEnum.day:
        return "1d"
    if unit == OverviewTimeUnitEnum.week:
        return "1w"
    return "1M"


def _bucket_period_start(bucket: dict) -> datetime:
    if bucket.get("key_as_string"):
        dt = parse_datetime(bucket["key_as_string"])
        if dt:
            if dt.tzinfo is None:
                return dt.replace(tzinfo=TZ_SH)
            return dt.astimezone(TZ_SH)
    key_ms = bucket.get("key")
    if key_ms is not None:
        return datetime.fromtimestamp(key_ms / 1000.0, tz=TZ_SH)
    raise ValueError("无法解析直方图桶时间")


def _change_rate_percent(first_count: int, last_count: int, bucket_count: int) -> Optional[float]:
    if bucket_count < 2:
        if first_count == 0:
            return None
        return 0.0
    if first_count == 0:
        return None
    return (last_count - first_count) / first_count * 100.0


async def fetch_platform_status(es: AsyncElasticsearch) -> OverviewPlatformStatusSchema:
    count_result = await es.count(index=ALL_INDEX)
    total_doc_count = int(count_result.get("count", 0))

    body = {
        "size": 0,
        "query": {"match_all": {}},
        "aggs": {
            "by_platform": {
                "terms": {"field": "platform.keyword", "size": 500, "order": {"_count": "desc"}}
            }
        },
    }
    result = await es.search(index=ALL_INDEX, body=body)
    by_platform: list[OverviewPlatformCountSchema] = []
    for b in result.get("aggregations", {}).get("by_platform", {}).get("buckets", []):
        key = b.get("key")
        platform = key if isinstance(key, str) else (str(key) if key is not None else "")
        by_platform.append(OverviewPlatformCountSchema(platform=platform, doc_count=int(b.get("doc_count", 0))))

    return OverviewPlatformStatusSchema(by_platform=by_platform, total_doc_count=total_doc_count)


def _today_range_bounds(now: Optional[datetime] = None) -> tuple[datetime, datetime]:
    if now is None:
        now = datetime.now(TZ_SH)
    elif now.tzinfo is None:
        now = now.replace(tzinfo=TZ_SH)
    else:
        now = now.astimezone(TZ_SH)
    now = now.replace(microsecond=0)
    today_start = datetime.combine(now.date(), datetime.min.time(), tzinfo=TZ_SH)
    return today_start, now


def _max_agg_to_datetime(agg: dict) -> Optional[datetime]:
    if not agg:
        return None
    s = agg.get("value_as_string")
    if s:
        dt = parse_datetime(s)
        if dt:
            if dt.tzinfo is None:
                return dt.replace(tzinfo=TZ_SH)
            return dt.astimezone(TZ_SH)
    v = agg.get("value")
    if v is None:
        return None
    try:
        return datetime.fromtimestamp(float(v) / 1000.0, tz=TZ_SH)
    except (TypeError, ValueError, OSError):
        return None


async def fetch_summary_status(es: AsyncElasticsearch) -> OverviewSummaryStatusSchema:
    today_start, now = _today_range_bounds()
    gte = today_start.isoformat()
    lte = now.isoformat()

    body = {
        "size": 0,
        "track_total_hits": True,
        "query": {"match_all": {}},
        "aggs": {
            "today_crawled": {
                "filter": {"range": {"crawled_at": {"gte": gte, "lte": lte}}},
            },
            "today_new": {
                "filter": {"range": {"last_edit_at": {"gte": gte, "lte": lte}}},
            },
            "latest_last_edit": {"max": {"field": "last_edit_at"}},
        },
    }
    result = await es.search(index=ALL_INDEX, body=body)
    total = _get_es_total(result)
    aggs = result.get("aggregations") or {}
    today_crawl = int(aggs.get("today_crawled", {}).get("doc_count", 0))
    today_new = int(aggs.get("today_new", {}).get("doc_count", 0))
    latest = _max_agg_to_datetime(aggs.get("latest_last_edit") or {})

    return OverviewSummaryStatusSchema(
        total_doc_count=total,
        today_crawl_count=today_crawl,
        today_new_count=today_new,
        latest_last_edit_at=latest,
    )


async def fetch_time_field_stats(
    es: AsyncElasticsearch, field: str, unit: OverviewTimeUnitEnum, n: int
) -> OverviewTimeSeriesStatsSchema:
    start_local, end_local = compute_time_window(unit, n)
    day_span = (end_local.date() - start_local.date()).days + 1
    if day_span < 1:
        day_span = 1

    start_iso = start_local.isoformat()
    end_iso = end_local.isoformat()

    body = {
        "query": {
            "bool": {
                "filter": [
                    {"range": {field: {"gte": start_iso, "lte": end_iso}}},
                ]
            }
        },
        "size": 0,
        "track_total_hits": True,
        "aggs": {
            "timeline": {
                "date_histogram": {
                    "field": field,
                    "calendar_interval": _calendar_interval(unit),
                    "time_zone": "+08:00",
                    "min_doc_count": 0,
                    "extended_bounds": {"min": start_iso, "max": end_iso},
                }
            }
        },
    }

    result = await es.search(index=ALL_INDEX, body=body)
    total = _get_es_total(result)
    buckets_raw = result.get("aggregations", {}).get("timeline", {}).get("buckets", [])

    buckets: list[OverviewTimeBucketSchema] = []
    for b in buckets_raw:
        try:
            ps = _bucket_period_start(b)
        except ValueError:
            logger.warning("跳过无法解析的直方图桶: %s", b)
            continue
        buckets.append(OverviewTimeBucketSchema(period_start=ps, doc_count=int(b.get("doc_count", 0))))

    counts = [x.doc_count for x in buckets]
    first_c = counts[0] if counts else 0
    last_c = counts[-1] if counts else 0
    change_rate = _change_rate_percent(first_c, last_c, len(buckets))

    average_daily = float(total) / float(day_span) if day_span else float(total)
    average_daily_int = int(round(average_daily))
    change_rate_rounded = round(change_rate, 2) if change_rate is not None else None

    return OverviewTimeSeriesStatsSchema(
        unit=unit,
        n=n,
        start_at=start_local,
        end_at=end_local,
        total=total,
        average_daily=average_daily_int,
        change_rate_percent=change_rate_rounded,
        buckets=buckets,
    )
