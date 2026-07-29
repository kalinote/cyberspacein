from datetime import datetime, timezone
from math import isfinite
from typing import Any

from app.schemas.alert.condition import AlertExpression, AlertThresholdValue
from app.schemas.alert.constants import AlertOperatorEnum, AlertValueTypeEnum


_DURATION_UNITS = {
    None: 1,
    "second": 1,
    "seconds": 1,
    "秒": 1,
    "minute": 60,
    "minutes": 60,
    "分钟": 60,
    "hour": 3600,
    "hours": 3600,
    "小时": 3600,
    "day": 86400,
    "days": 86400,
    "天": 86400,
}

_ORDERED_TYPES = {
    AlertValueTypeEnum.NUMBER,
    AlertValueTypeEnum.PERCENTAGE,
    AlertValueTypeEnum.DURATION,
    AlertValueTypeEnum.DATETIME,
}


def _normalize_number(value: Any) -> float:
    """规范化有限数值并拒绝布尔值。"""
    if isinstance(value, bool):
        raise ValueError("布尔值不能作为数值")
    try:
        normalized = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError("数值格式无效") from exc
    if not isfinite(normalized):
        raise ValueError("数值必须是有限值")
    return normalized


def _normalize_datetime(value: Any) -> datetime:
    """规范化 ISO 日期时间为 UTC。"""
    if isinstance(value, str):
        try:
            value = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError as exc:
            raise ValueError("日期时间格式无效") from exc
    if not isinstance(value, datetime):
        raise ValueError("日期时间格式无效")
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def normalize_value(
    value_type: AlertValueTypeEnum,
    value: Any,
    *,
    unit: str | None = None,
) -> Any:
    """将字段值或阈值转换为统一内部类型。"""
    if value_type in {AlertValueTypeEnum.ENUM, AlertValueTypeEnum.STRING}:
        if not isinstance(value, str):
            raise ValueError("字符串或枚举值格式无效")
        if len(value) > 4000:
            raise ValueError("字符串值过长")
        return value
    if value_type == AlertValueTypeEnum.BOOLEAN:
        if not isinstance(value, bool):
            raise ValueError("布尔值格式无效")
        return value
    if value_type == AlertValueTypeEnum.DATETIME:
        return _normalize_datetime(value)
    normalized = _normalize_number(value)
    if value_type == AlertValueTypeEnum.PERCENTAGE and not 0 <= normalized <= 100:
        raise ValueError("百分比必须在 0 到 100 之间")
    if value_type == AlertValueTypeEnum.DURATION:
        multiplier = _DURATION_UNITS.get(unit)
        if multiplier is None:
            raise ValueError(f"不支持的时长单位: {unit}")
        normalized *= multiplier
        if normalized < 0:
            raise ValueError("时长不能小于 0")
        return int(normalized)
    return normalized


def compare_values(
    value_type: AlertValueTypeEnum,
    actual: Any,
    operator: AlertOperatorEnum,
    expected: Any,
) -> bool:
    """比较已经规范化的实际值和阈值。"""
    if operator == AlertOperatorEnum.EQ:
        return actual == expected
    if operator == AlertOperatorEnum.NE:
        return actual != expected
    if operator in {AlertOperatorEnum.IN, AlertOperatorEnum.NOT_IN}:
        if not isinstance(expected, list):
            raise ValueError("属于运算符需要列表阈值")
        matched = actual in expected
        return matched if operator == AlertOperatorEnum.IN else not matched
    if value_type not in _ORDERED_TYPES:
        raise ValueError(f"{value_type.value} 类型不支持顺序比较")
    if operator == AlertOperatorEnum.LT:
        return actual < expected
    if operator == AlertOperatorEnum.LTE:
        return actual <= expected
    if operator == AlertOperatorEnum.GT:
        return actual > expected
    if operator == AlertOperatorEnum.GTE:
        return actual >= expected
    raise ValueError(f"不支持的运算符: {operator.value}")


def normalize_threshold(
    value_type: AlertValueTypeEnum,
    threshold: AlertThresholdValue,
) -> AlertThresholdValue:
    """规范化规则阈值并保留显示单位。"""
    if isinstance(threshold.value, list):
        if value_type not in {AlertValueTypeEnum.ENUM, AlertValueTypeEnum.STRING}:
            raise ValueError("仅枚举和字符串支持列表阈值")
        normalized = [
            normalize_value(value_type, item, unit=threshold.unit)
            for item in threshold.value
        ]
        return AlertThresholdValue(value=normalized, unit=threshold.unit)
    return AlertThresholdValue(
        value=normalize_value(value_type, threshold.value, unit=threshold.unit),
        unit=threshold.unit,
    )


def evaluate_expression(
    expression: AlertExpression,
    value_type: AlertValueTypeEnum,
    actual_value: Any,
) -> bool:
    """执行已经通过字段校验的条件表达式。"""
    actual = normalize_value(value_type, actual_value)
    results = []
    for condition in expression.conditions:
        threshold = normalize_threshold(value_type, condition.value)
        results.append(
            compare_values(
                value_type,
                actual,
                condition.operator,
                threshold.value,
            )
        )
    return all(results) if expression.logic == "all" else any(results)
