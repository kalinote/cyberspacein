from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest

from app.api.v1.endpoints.action import schedule as schedule_endpoint
from app.models.action.schedule import ActionScheduleModel
from app.schemas.action.schedule import ActionScheduleCreateRequest
from app.schemas.constants import ActionScheduleTypeEnum
from app.service.action_schedule import ActionScheduleService


@pytest.mark.asyncio
async def test_create_schedule_passes_enabled_only_once(monkeypatch):
    request = ActionScheduleCreateRequest(
        name="每日采集",
        blueprint_id="blueprint-1",
        schedule_type=ActionScheduleTypeEnum.INTERVAL,
        interval_seconds=3600,
        start_at=datetime(2026, 7, 21, tzinfo=timezone.utc),
        enabled=True,
    )
    next_run = datetime(2026, 7, 21, 1, tzinfo=timezone.utc)

    async def validate_payload(_data):
        return SimpleNamespace(name="测试蓝图", version="1.0")

    monkeypatch.setattr(ActionScheduleService, "validate_payload", staticmethod(validate_payload))
    monkeypatch.setattr(ActionScheduleService, "next_runs", staticmethod(lambda _data, count: [next_run]))
    monkeypatch.setattr(ActionScheduleModel, "insert", AsyncMock(return_value=None))
    constructor = Mock(side_effect=lambda **kwargs: ActionScheduleModel.model_construct(**kwargs))
    monkeypatch.setattr(schedule_endpoint, "ActionScheduleModel", constructor)

    response = await schedule_endpoint.create_schedule(request)

    assert constructor.call_args.kwargs["enabled"] is True
    assert response.data.enabled is True
    assert response.data.next_run_at == next_run
