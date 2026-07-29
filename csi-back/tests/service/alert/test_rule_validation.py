from pydantic import ValidationError
import pytest

from app.core.exceptions import BadRequestException
from app.schemas.alert.condition import (
    AlertCondition,
    AlertExpression,
    AlertThresholdValue,
)
from app.schemas.alert.constants import (
    AlertEvaluationModeEnum,
    AlertOperatorEnum,
    AlertSeverityEnum,
)
from app.schemas.alert.rule import AlertRuleCreateRequest
from app.service.action_alert_source import ActionInstanceAlertSource
from app.service.alert.registry import AlertSourceRegistry
from app.service.alert.rule_service import AlertRuleService


def rule_payload(**updates):
    """构造行动超时规则测试数据。"""
    values = {
        "name": "行动超时",
        "source_key": "action.instance",
        "field_key": "status",
        "trigger_expression": AlertExpression(
            conditions=[
                AlertCondition(
                    field_key="status",
                    operator=AlertOperatorEnum.EQ,
                    value=AlertThresholdValue(value="timeout"),
                )
            ]
        ),
        "severity": AlertSeverityEnum.ERROR,
        "evaluation_mode": AlertEvaluationModeEnum.REALTIME,
    }
    values.update(updates)
    return AlertRuleCreateRequest(**values)


def test_rule_service_accepts_registered_action_status_rule():
    registry = AlertSourceRegistry()
    registry.register(ActionInstanceAlertSource())

    descriptor, field = AlertRuleService(registry).validate_payload(rule_payload())

    assert descriptor.source_key == "action.instance"
    assert field.signal_key == "execution_status"


def test_rule_service_rejects_unsupported_operator():
    registry = AlertSourceRegistry()
    registry.register(ActionInstanceAlertSource())
    payload = rule_payload(
        trigger_expression=AlertExpression(
            conditions=[
                AlertCondition(
                    field_key="status",
                    operator=AlertOperatorEnum.GT,
                    value=AlertThresholdValue(value="timeout"),
                )
            ]
        )
    )

    with pytest.raises(BadRequestException, match="不支持运算符"):
        AlertRuleService(registry).validate_payload(payload)


def test_rule_service_rejects_unknown_enum_value():
    registry = AlertSourceRegistry()
    registry.register(ActionInstanceAlertSource())
    payload = rule_payload(
        trigger_expression=AlertExpression(
            conditions=[
                AlertCondition(
                    field_key="status",
                    operator=AlertOperatorEnum.EQ,
                    value=AlertThresholdValue(value="missing"),
                )
            ]
        )
    )

    with pytest.raises(BadRequestException, match="枚举阈值不存在"):
        AlertRuleService(registry).validate_payload(payload)


def test_first_version_rejects_resource_filter_and_missing_interval():
    with pytest.raises(ValidationError, match="全部资源"):
        rule_payload(resource_scope={"type": "ids", "ids": ["action-1"]})
    with pytest.raises(ValidationError, match="检测周期"):
        rule_payload(evaluation_mode=AlertEvaluationModeEnum.INTERVAL)
