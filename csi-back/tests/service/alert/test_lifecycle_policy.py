from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from app.core.exceptions import BadRequestException
from app.models.alert.instance import AlertInstanceModel
from app.schemas.alert.constants import (
    AlertEventTypeEnum,
    AlertSeverityEnum,
    AlertStatusEnum,
    AlertValueTypeEnum,
)
from app.service.alert.lifecycle import AlertLifecycleService


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "severity",
    [AlertSeverityEnum.ERROR, AlertSeverityEnum.CRITICAL],
)
async def test_serious_alert_requires_manual_resolution_note(
    monkeypatch,
    severity,
):
    now = datetime.now(timezone.utc)
    alert = AlertInstanceModel.model_construct(
        _id="alert-1",
        open_key="incident-1",
        incident_key="incident-1",
        anomaly_sequence=1,
        source_key="action.instance",
        resource_type="action_instance",
        resource_id="action-1",
        resource_name="测试行动",
        field_key="status",
        signal_key="execution_status",
        title="行动超时",
        detail="测试行动已超时",
        status=AlertStatusEnum.FIRING,
        initial_severity=severity,
        current_severity=severity,
        trigger_value="timeout",
        trigger_value_type=AlertValueTypeEnum.ENUM,
        latest_value="timeout",
        latest_observed_at=now,
        triggered_at=now,
    )
    monkeypatch.setattr(
        AlertLifecycleService,
        "get",
        AsyncMock(return_value=alert),
    )

    with pytest.raises(BadRequestException, match="必须填写处理说明"):
        await AlertLifecycleService.resolve_manual(
            alert.id,
            expected_version=1,
            note=" ",
        )


@pytest.mark.asyncio
async def test_pending_event_is_replayed_and_cleared(monkeypatch):
    now = datetime.now(timezone.utc)
    alert = AlertInstanceModel.model_construct(
        _id="alert-1",
        open_key="incident-1",
        incident_key="incident-1",
        anomaly_sequence=1,
        source_key="action.instance",
        resource_type="action_instance",
        resource_id="action-1",
        resource_name="测试行动",
        field_key="status",
        signal_key="execution_status",
        title="行动超时",
        detail="测试行动已超时",
        status=AlertStatusEnum.ACKNOWLEDGED,
        initial_severity=AlertSeverityEnum.ERROR,
        current_severity=AlertSeverityEnum.ERROR,
        trigger_value="timeout",
        trigger_value_type=AlertValueTypeEnum.ENUM,
        latest_value="timeout",
        latest_observed_at=now,
        acknowledged_at=now,
        pending_event={
            "event_type": AlertEventTypeEnum.ACKNOWLEDGED.value,
            "from_status": AlertStatusEnum.FIRING.value,
            "to_status": AlertStatusEnum.ACKNOWLEDGED.value,
            "from_severity": None,
            "to_severity": None,
            "rule_id": None,
            "rule_version": None,
            "observation": None,
            "note": None,
        },
        version=2,
        triggered_at=now,
    )
    record_event = AsyncMock()
    collection = SimpleNamespace(
        update_one=AsyncMock(
            return_value=SimpleNamespace(modified_count=1)
        )
    )
    monkeypatch.setattr(
        AlertLifecycleService,
        "_record_event",
        record_event,
    )
    monkeypatch.setattr(
        AlertInstanceModel,
        "get_motor_collection",
        lambda: collection,
    )

    result = await AlertLifecycleService._flush_pending_event(alert)

    assert result.pending_event is None
    record_event.assert_awaited_once()
    assert (
        record_event.await_args.args[1]
        == AlertEventTypeEnum.ACKNOWLEDGED
    )
    collection.update_one.assert_awaited_once_with(
        {
            "_id": "alert-1",
            "version": 2,
            "pending_event.event_type": "acknowledged",
        },
        {"$set": {"pending_event": None}},
    )
