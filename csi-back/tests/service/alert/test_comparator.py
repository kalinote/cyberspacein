from datetime import datetime, timezone

import pytest

from app.schemas.alert.condition import AlertCondition, AlertExpression, AlertThresholdValue
from app.schemas.alert.constants import AlertOperatorEnum, AlertValueTypeEnum
from app.service.alert.comparator import (
    compare_values,
    evaluate_expression,
    normalize_threshold,
    normalize_value,
)


def _expression(operator: AlertOperatorEnum, value, unit: str | None = None):
    """构造单条件测试表达式。"""
    return AlertExpression(
        conditions=[
            AlertCondition(
                field_key="value",
                operator=operator,
                value=AlertThresholdValue(value=value, unit=unit),
            )
        ]
    )


def test_duration_threshold_is_normalized_to_seconds():
    threshold = normalize_threshold(
        AlertValueTypeEnum.DURATION,
        AlertThresholdValue(value=7, unit="day"),
    )

    assert threshold.value == 7 * 86400
    assert threshold.unit == "day"


def test_duration_expression_supports_trigger_and_recovery_hysteresis():
    trigger = _expression(AlertOperatorEnum.LT, 7, "day")
    recovery = _expression(AlertOperatorEnum.GT, 10, "day")

    assert evaluate_expression(trigger, AlertValueTypeEnum.DURATION, 6 * 86400)
    assert not evaluate_expression(recovery, AlertValueTypeEnum.DURATION, 9 * 86400)
    assert evaluate_expression(recovery, AlertValueTypeEnum.DURATION, 11 * 86400)


def test_datetime_is_normalized_to_utc():
    value = normalize_value(
        AlertValueTypeEnum.DATETIME,
        "2026-07-29T20:00:00+08:00",
    )

    assert value == datetime(2026, 7, 29, 12, tzinfo=timezone.utc)


def test_enum_and_list_operators():
    assert compare_values(
        AlertValueTypeEnum.ENUM,
        "timeout",
        AlertOperatorEnum.EQ,
        "timeout",
    )
    assert compare_values(
        AlertValueTypeEnum.ENUM,
        "timeout",
        AlertOperatorEnum.IN,
        ["failed", "timeout"],
    )


@pytest.mark.parametrize("value", [float("nan"), float("inf"), True])
def test_invalid_numeric_values_are_rejected(value):
    with pytest.raises(ValueError):
        normalize_value(AlertValueTypeEnum.NUMBER, value)


def test_percentage_range_is_enforced():
    with pytest.raises(ValueError, match="0 到 100"):
        normalize_value(AlertValueTypeEnum.PERCENTAGE, 101)


def test_ordered_operator_is_rejected_for_enum():
    with pytest.raises(ValueError, match="不支持顺序比较"):
        compare_values(
            AlertValueTypeEnum.ENUM,
            "timeout",
            AlertOperatorEnum.GT,
            "running",
        )
