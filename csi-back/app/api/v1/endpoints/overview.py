import logging
from typing import Annotated

from fastapi import APIRouter, Depends, Query

from app.db.elasticsearch import get_es
from app.schemas.overview import (
    OverviewPlatformStatusSchema,
    OverviewSummaryStatusSchema,
    OverviewTimeSeriesParamsSchema,
    OverviewTimeSeriesStatsSchema,
    OverviewTimeUnitEnum,
)
from app.schemas.response import ApiResponseSchema
from app.service.overview import fetch_platform_status, fetch_summary_status, fetch_time_field_stats

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/overview",
    tags=["概览"],
)


def _time_series_params(
    n: int = Query(7, ge=1, description="近 n 天、近 n 周或近 n 月，默认 7"),
    unit: OverviewTimeUnitEnum = Query(
        OverviewTimeUnitEnum.day, description="统计单位：day / week / month，默认 day"
    ),
) -> OverviewTimeSeriesParamsSchema:
    return OverviewTimeSeriesParamsSchema(n=n, unit=unit)


@router.get(
    "/platform-status",
    response_model=OverviewPlatformStatusSchema,
    summary="平台数据量与分布",
)
async def get_platform_status():
    es = get_es()
    if not es:
        return ApiResponseSchema.error(code=250001, message="Elasticsearch连接未初始化")
    try:
        return await fetch_platform_status(es)
    except Exception as e:
        logger.error(f"平台数据统计失败: {e}", exc_info=True)
        return ApiResponseSchema.error(code=250003, message=f"平台数据统计失败: {str(e)}")


@router.get(
    "/summary-status",
    response_model=OverviewSummaryStatusSchema,
    summary="数据总量、今日采集、今日新增与最新数据时间",
)
async def get_summary_status():
    es = get_es()
    if not es:
        return ApiResponseSchema.error(code=250001, message="Elasticsearch连接未初始化")
    try:
        return await fetch_summary_status(es)
    except Exception as e:
        logger.error(f"概览汇总统计失败: {e}", exc_info=True)
        return ApiResponseSchema.error(code=250006, message=f"概览汇总统计失败: {str(e)}")


@router.get(
    "/crawl-status",
    response_model=OverviewTimeSeriesStatsSchema,
    summary="按采集时间统计（crawled_at）",
)
async def get_crawl_status(
    params: Annotated[OverviewTimeSeriesParamsSchema, Depends(_time_series_params)],
):
    es = get_es()
    if not es:
        return ApiResponseSchema.error(code=250001, message="Elasticsearch连接未初始化")
    try:
        return await fetch_time_field_stats(es, "crawled_at", params.unit, params.n)
    except Exception as e:
        logger.error(f"crawled_at 概览统计失败: {e}", exc_info=True)
        return ApiResponseSchema.error(code=250004, message=f"crawled_at 概览统计失败: {str(e)}")


@router.get(
    "/new-data-status",
    response_model=OverviewTimeSeriesStatsSchema,
    summary="按最后编辑时间统计（last_edit_at）",
)
async def get_new_data_status(
    params: Annotated[OverviewTimeSeriesParamsSchema, Depends(_time_series_params)],
):
    es = get_es()
    if not es:
        return ApiResponseSchema.error(code=250001, message="Elasticsearch连接未初始化")
    try:
        return await fetch_time_field_stats(es, "last_edit_at", params.unit, params.n)
    except Exception as e:
        logger.error(f"last_edit_at 概览统计失败: {e}", exc_info=True)
        return ApiResponseSchema.error(code=250005, message=f"last_edit_at 概览统计失败: {str(e)}")
