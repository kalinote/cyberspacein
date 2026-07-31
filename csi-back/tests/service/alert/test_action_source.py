from datetime import datetime, timezone
from types import SimpleNamespace

from app.schemas.constants import ActionFlowStatusEnum
from app.service.action.alert_source import (
    ActionInstanceAlertSource,
    action_status_observation,
)


def test_action_source_describes_status_and_timeout():
    descriptor = ActionInstanceAlertSource().describe()
    field = descriptor.fields[0]

    assert descriptor.module_name == "行动系统"
    assert field.field_key == "status"
    assert any(
        option.value == ActionFlowStatusEnum.TIMEOUT.value
        and option.label == "超时"
        for option in field.enum_options
    )


def test_action_status_observation_is_stable_and_uses_relative_url():
    observed_at = datetime(2026, 7, 29, 8, 0)
    action = SimpleNamespace(
        id="action-1",
        blueprint_snapshot=SimpleNamespace(name="测试行动"),
    )

    first = action_status_observation(
        action,
        ActionFlowStatusEnum.TIMEOUT,
        observed_at,
    )
    second = action_status_observation(
        action,
        ActionFlowStatusEnum.TIMEOUT,
        observed_at,
    )

    assert first.observation_id == second.observation_id
    assert first.resource_url == "/action/action-1"
    assert first.value == "timeout"
    assert first.observed_at.tzinfo == timezone.utc
