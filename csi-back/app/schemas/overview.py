from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field, model_validator


class OverviewTimeUnitEnum(str, Enum):
    day = "day"
    week = "week"
    month = "month"


class OverviewPlatformCountSchema(BaseModel):
    platform: str = Field(description="平台标识")
    doc_count: int = Field(description="文档数量")


class OverviewPlatformStatusSchema(BaseModel):
    by_platform: list[OverviewPlatformCountSchema] = Field(description="按平台汇总的文档量")
    total_doc_count: int = Field(description="全部平台文档合计")


class OverviewSummaryStatusSchema(BaseModel):
    total_doc_count: int = Field(description="数据总量")
    today_crawl_count: int = Field(description="今日采集量（crawled_at 落在当日的文档数）")
    today_new_count: int = Field(description="今日新增量（last_edit_at 落在当日的文档数）")
    latest_last_edit_at: Optional[datetime] = Field(
        default=None,
        description="全部数据中 last_edit_at 的最大值；无数据时为 null",
    )


class OverviewTimeBucketSchema(BaseModel):
    period_start: datetime = Field(description="该统计区间起始时刻（含时区）")
    doc_count: int = Field(description="该区间内文档数")


class OverviewTimeSeriesStatsSchema(BaseModel):
    unit: OverviewTimeUnitEnum = Field(description="统计粒度：天/周/月")
    n: int = Field(description="近 n 天/周/月中的 n")
    start_at: datetime = Field(description="统计窗口起始")
    end_at: datetime = Field(description="统计窗口结束")
    total: int = Field(description="窗口内文档总数")
    average_daily: int = Field(description="日均数量（总条数 / 窗口内日历日数，四舍五入取整）")
    change_rate_percent: Optional[float] = Field(
        default=None,
        description="变化率（%），保留两位小数；(最后区间 - 第一区间) / 第一区间 × 100；首区间为 0 时无意义则为 null",
    )
    buckets: list[OverviewTimeBucketSchema] = Field(description="按粒度划分的时间序列")


class OverviewTimeSeriesParamsSchema(BaseModel):
    n: int = Field(ge=1, description="近 n 天、近 n 周或近 n 月")
    unit: OverviewTimeUnitEnum = Field(description="统计单位")

    @model_validator(mode="after")
    def validate_n_upper_bound(self) -> "OverviewTimeSeriesParamsSchema":
        caps = {
            OverviewTimeUnitEnum.day: 366,
            OverviewTimeUnitEnum.week: 52,
            OverviewTimeUnitEnum.month: 36,
        }
        cap = caps[self.unit]
        if self.n > cap:
            raise ValueError(f"当 unit={self.unit.value} 时，n 不能超过 {cap}")
        return self
