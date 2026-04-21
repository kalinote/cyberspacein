"""app.schemas.overview 总览相关 Schema 与校验测试。"""

import pytest

from app.schemas.overview import (
    OverviewTimeSeriesParamsSchema,
    OverviewTimeUnitEnum,
)


def test_overview_time_unit_enum_values():
    # 枚举值与 API 约定一致
    assert OverviewTimeUnitEnum.day.value == "day"
    assert OverviewTimeUnitEnum.week.value == "week"
    assert OverviewTimeUnitEnum.month.value == "month"


def test_overview_time_series_params_n_cap_day():
    # 按天统计时 n 不能超过 366
    with pytest.raises(ValueError, match="n 不能超过"):
        OverviewTimeSeriesParamsSchema(n=400, unit=OverviewTimeUnitEnum.day)


def test_overview_time_series_params_n_cap_week():
    # 按周统计时 n 不能超过 52
    with pytest.raises(ValueError, match="n 不能超过"):
        OverviewTimeSeriesParamsSchema(n=60, unit=OverviewTimeUnitEnum.week)


def test_overview_time_series_params_n_cap_month():
    # 按月统计时 n 不能超过 36
    with pytest.raises(ValueError, match="n 不能超过"):
        OverviewTimeSeriesParamsSchema(n=40, unit=OverviewTimeUnitEnum.month)


def test_overview_time_series_params_valid():
    # 边界内应通过校验
    s = OverviewTimeSeriesParamsSchema(n=366, unit=OverviewTimeUnitEnum.day)
    assert s.n == 366
