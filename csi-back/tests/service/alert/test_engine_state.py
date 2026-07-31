from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock

import pytest

from app.models.alert.evaluation_state import AlertRuleEvaluationStateModel
from app.models.alert.rule import AlertRuleModel
from app.schemas.alert.condition import (
    AlertCondition,
    AlertExpression,
    AlertThresholdValue,
)
from app.schemas.alert.constants import (
    AlertEvaluationModeEnum,
    AlertInitialEvaluationPolicyEnum,
    AlertOperatorEnum,
    AlertRuleStateEnum,
    AlertSeverityEnum,
    AlertValueTypeEnum,
)
from app.schemas.alert.observation import AlertObservation
from app.service.alert.engine import AlertEngine
from app.service.action.alert_source import ActionInstanceAlertSource
from app.service.alert.registry import AlertSourceRegistry


def expression(value: str) -> AlertExpression:
    """构造状态相等表达式。"""
    return AlertExpression(
        conditions=[
            AlertCondition(
                field_key="status",
                operator=AlertOperatorEnum.EQ,
                value=AlertThresholdValue(value=value),
            )
        ]
    )


def rule() -> AlertRuleModel:
    """构造带自动恢复条件的规则。"""
    now = datetime.now(timezone.utc)
    return AlertRuleModel.model_construct(
        _id="rule-1",
        name="行动超时",
        source_key="action.instance",
        field_key="status",
        signal_key="execution_status",
        trigger_expression=expression("timeout"),
        recovery_expression=expression("completed"),
        severity=AlertSeverityEnum.ERROR,
        evaluation_mode=AlertEvaluationModeEnum.REALTIME,
        initial_evaluation_policy=AlertInitialEvaluationPolicyEnum.FROM_ACTIVATION,
        active_from=now,
    )


def observation(observation_id: str, value: str) -> AlertObservation:
    """构造行动状态观测。"""
    return AlertObservation(
        observation_id=observation_id,
        source_key="action.instance",
        resource_type="action_instance",
        resource_id="action-1",
        resource_name="测试行动",
        field_key="status",
        signal_key="execution_status",
        value_type=AlertValueTypeEnum.ENUM,
        value=value,
    )


@pytest.mark.asyncio
async def test_rule_state_triggers_and_recovers(monkeypatch):
    now = datetime.now(timezone.utc)
    state = AlertRuleEvaluationStateModel.model_construct(
        _id="state-1",
        rule_id="rule-1",
        rule_version=1,
        source_key="action.instance",
        resource_type="action_instance",
        resource_id="action-1",
        signal_key="execution_status",
        incident_key="incident-1",
        last_value="running",
        last_value_type=AlertValueTypeEnum.ENUM,
        last_observation_id="observation-0",
        last_observed_at=now,
    )
    monkeypatch.setattr(
        AlertEngine,
        "_get_or_create_rule_state",
        AsyncMock(return_value=(state, False)),
    )
    save = AsyncMock()
    monkeypatch.setattr(AlertRuleEvaluationStateModel, "save", save)

    await AlertEngine._apply_rule(
        rule(),
        observation("observation-1", "timeout"),
        "incident-1",
    )
    assert state.state == AlertRuleStateEnum.ACTIVE

    await AlertEngine._apply_rule(
        rule(),
        observation("observation-2", "completed"),
        "incident-1",
    )
    assert state.state == AlertRuleStateEnum.NORMAL
    assert save.await_count == 2


@pytest.mark.asyncio
async def test_severity_only_version_change_keeps_active_state(monkeypatch):
    current_rule = rule()
    fingerprint = AlertEngine.condition_fingerprint(current_rule)
    state = AlertRuleEvaluationStateModel.model_construct(
        _id="state-1",
        rule_id=current_rule.id,
        rule_version=1,
        condition_fingerprint=fingerprint,
        source_key="action.instance",
        resource_type="action_instance",
        resource_id="action-1",
        signal_key="execution_status",
        incident_key="incident-1",
        state=AlertRuleStateEnum.ACTIVE,
        last_value="timeout",
        last_value_type=AlertValueTypeEnum.ENUM,
        last_observation_id="observation-1",
        last_observed_at=datetime.now(timezone.utc),
    )
    changed_rule = current_rule.model_copy(
        update={"version": 2, "severity": AlertSeverityEnum.CRITICAL}
    )
    monkeypatch.setattr(
        AlertEngine,
        "_get_or_create_rule_state",
        AsyncMock(return_value=(state, False)),
    )
    monkeypatch.setattr(
        AlertRuleEvaluationStateModel,
        "save",
        AsyncMock(),
    )

    await AlertEngine._apply_rule(
        changed_rule,
        observation("observation-1", "timeout"),
        "incident-1",
    )

    assert state.state == AlertRuleStateEnum.ACTIVE
    assert state.rule_version == 2
    assert state.condition_fingerprint == fingerprint


@pytest.mark.asyncio
async def test_condition_change_recalculates_same_resource_snapshot(monkeypatch):
    current_rule = rule()
    state = AlertRuleEvaluationStateModel.model_construct(
        _id="state-1",
        rule_id=current_rule.id,
        rule_version=1,
        condition_fingerprint=AlertEngine.condition_fingerprint(current_rule),
        source_key="action.instance",
        resource_type="action_instance",
        resource_id="action-1",
        signal_key="execution_status",
        incident_key="incident-1",
        state=AlertRuleStateEnum.ACTIVE,
        last_value="timeout",
        last_value_type=AlertValueTypeEnum.ENUM,
        last_observation_id="observation-1",
        last_observed_at=datetime.now(timezone.utc),
    )
    changed_rule = current_rule.model_copy(
        update={
            "version": 2,
            "trigger_expression": expression("completed"),
            "recovery_expression": None,
        }
    )
    monkeypatch.setattr(
        AlertEngine,
        "_get_or_create_rule_state",
        AsyncMock(return_value=(state, False)),
    )
    monkeypatch.setattr(
        AlertRuleEvaluationStateModel,
        "save",
        AsyncMock(),
    )

    await AlertEngine._apply_rule(
        changed_rule,
        observation("observation-1", "timeout"),
        "incident-1",
    )

    assert state.state == AlertRuleStateEnum.NORMAL
    assert state.rule_version == 2


@pytest.mark.asyncio
async def test_older_observation_does_not_roll_back_rule_state(monkeypatch):
    current_rule = rule()
    newer_time = datetime.now(timezone.utc)
    state = AlertRuleEvaluationStateModel.model_construct(
        _id="state-1",
        rule_id=current_rule.id,
        rule_version=current_rule.version,
        condition_fingerprint=AlertEngine.condition_fingerprint(current_rule),
        source_key="action.instance",
        resource_type="action_instance",
        resource_id="action-1",
        signal_key="execution_status",
        incident_key="incident-1",
        state=AlertRuleStateEnum.ACTIVE,
        last_value="timeout",
        last_value_type=AlertValueTypeEnum.ENUM,
        last_observation_id="observation-new",
        last_observed_at=newer_time,
    )
    monkeypatch.setattr(
        AlertEngine,
        "_get_or_create_rule_state",
        AsyncMock(return_value=(state, False)),
    )
    save = AsyncMock()
    monkeypatch.setattr(AlertRuleEvaluationStateModel, "save", save)
    older = observation("observation-old", "completed")
    older.observed_at = newer_time - timedelta(seconds=1)

    _, applied = await AlertEngine._apply_rule(
        current_rule,
        older,
        "incident-1",
    )

    assert applied is False
    assert state.state == AlertRuleStateEnum.ACTIVE
    save.assert_not_awaited()


@pytest.mark.asyncio
async def test_same_time_observation_uses_source_ordering_key(monkeypatch):
    current_rule = rule()
    observed_at = datetime.now(timezone.utc)
    state = AlertRuleEvaluationStateModel.model_construct(
        _id="state-1",
        rule_id=current_rule.id,
        rule_version=current_rule.version,
        condition_fingerprint=AlertEngine.condition_fingerprint(current_rule),
        source_key="action.instance",
        resource_type="action_instance",
        resource_id="action-1",
        signal_key="execution_status",
        incident_key="incident-1",
        state=AlertRuleStateEnum.ACTIVE,
        last_value="timeout",
        last_value_type=AlertValueTypeEnum.ENUM,
        last_observation_id="observation-b",
        last_observation_ordering_key="report-b",
        last_observed_at=observed_at,
    )
    monkeypatch.setattr(
        AlertEngine,
        "_get_or_create_rule_state",
        AsyncMock(return_value=(state, False)),
    )
    save = AsyncMock()
    monkeypatch.setattr(AlertRuleEvaluationStateModel, "save", save)
    item = observation("observation-z", "completed")
    item.observed_at = observed_at
    item.ordering_key = "report-a"

    _, applied = await AlertEngine._apply_rule(
        current_rule,
        item,
        "incident-1",
    )

    assert applied is False
    assert state.state == AlertRuleStateEnum.ACTIVE
    save.assert_not_awaited()


@pytest.mark.asyncio
async def test_realtime_and_periodic_processing_select_expected_rules(monkeypatch):
    registry = AlertSourceRegistry()
    registry.register(ActionInstanceAlertSource())
    captured = []

    class _Query:
        async def to_list(self):
            return []

    def find(filters):
        captured.append(filters)
        return _Query()

    monkeypatch.setattr(AlertRuleModel, "find", staticmethod(find))
    engine = AlertEngine(registry)
    item = observation("observation-1", "timeout")

    await engine.process_observation(item, realtime_only=True)
    await engine.process_observation(item, target_rule_id="rule-1")

    assert captured[0]["evaluation_mode"]["$in"] == [
        AlertEvaluationModeEnum.REALTIME,
        AlertEvaluationModeEnum.HYBRID,
    ]
    assert captured[1]["_id"] == "rule-1"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "process_kwargs",
    [
        {"realtime_only": True},
        {"target_rule_id": "rule-1"},
    ],
)
async def test_naive_rule_activation_time_is_compared_as_utc(
    monkeypatch,
    process_kwargs,
):
    registry = AlertSourceRegistry()
    registry.register(ActionInstanceAlertSource())
    item = observation("observation-1", "timeout")
    item.observed_at = datetime.now(timezone.utc)
    current_rule = rule().model_copy(
        update={
            "active_from": (
                item.observed_at - timedelta(minutes=1)
            ).replace(tzinfo=None)
        }
    )

    class _Query:
        async def to_list(self):
            return [current_rule]

    monkeypatch.setattr(
        AlertRuleModel,
        "find",
        staticmethod(lambda filters: _Query()),
    )
    acquire_lock = AsyncMock(return_value=None)
    monkeypatch.setattr(AlertEngine, "_acquire_lock", acquire_lock)
    engine = AlertEngine(registry)

    result = await engine.process_observation(item, **process_kwargs)

    assert result == 0
    assert item.observed_at.tzinfo == timezone.utc
    acquire_lock.assert_awaited_once_with(engine.incident_key(item))
