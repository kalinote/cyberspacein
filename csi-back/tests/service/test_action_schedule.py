from datetime import datetime, timezone
from types import SimpleNamespace

import pytest
from pydantic import ValidationError

from app.models.action.blueprint import ActionBlueprintModel
from app.models.action.action import ActionInstanceModel
from app.models.action.schedule import ActionScheduleModel
from app.schemas.action.schedule import ActionSchedulePayload
from app.schemas.constants import (
    ActionScheduleMisfirePolicyEnum,
    ActionScheduleOverlapPolicyEnum,
    ActionScheduleTypeEnum,
)
from app.service.action_schedule import (
    ActionScheduleService,
    calculate_next_runs,
    latest_due_time,
    validate_blueprint_params,
    validate_cron_expression,
)


class _Schedule(SimpleNamespace):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.save_count = 0

    async def save(self):
        self.save_count += 1


def _schedule(**overrides):
    """构造调度策略测试使用的计划。"""
    values = {
        "id": "schedule-1",
        "name": "每日采集",
        "blueprint_id": "blueprint-1",
        "params": {},
        "schedule_type": ActionScheduleTypeEnum.INTERVAL,
        "cron_expression": None,
        "interval_seconds": 3600,
        "timezone": "Asia/Shanghai",
        "start_at": datetime(2026, 7, 20, 0, tzinfo=timezone.utc),
        "end_at": None,
        "enabled": True,
        "priority": 8,
        "overlap_policy": ActionScheduleOverlapPolicyEnum.FORBID,
        "misfire_policy": ActionScheduleMisfirePolicyEnum.FIRE_ONCE,
        "next_run_at": datetime(2026, 7, 20, 1, tzinfo=timezone.utc),
        "last_scheduled_for": None,
        "last_action_id": None,
        "last_trigger_status": None,
        "last_error": None,
        "updated_at": datetime(2026, 7, 20, 0, tzinfo=timezone.utc),
    }
    values.update(overrides)
    return _Schedule(**values)


def _patch_schedule_lock(monkeypatch):
    """让策略测试固定取得计划锁。"""
    async def acquire(_schedule_id):
        return "lock-token"

    async def release(_schedule_id, _token):
        return None

    monkeypatch.setattr(ActionScheduleService, "_acquire_lock", staticmethod(acquire))
    monkeypatch.setattr(ActionScheduleService, "_release_lock", staticmethod(release))


def test_cron_next_run_uses_selected_timezone():
    runs = calculate_next_runs(
        ActionScheduleTypeEnum.CRON,
        cron_expression="0 8 * * *",
        interval_seconds=None,
        timezone_name="Asia/Shanghai",
        start_at=datetime(2026, 7, 1, tzinfo=timezone.utc),
        end_at=None,
        now=datetime(2026, 7, 20, 23, tzinfo=timezone.utc),
        count=2,
    )

    assert runs == [
        datetime(2026, 7, 21, 0, tzinfo=timezone.utc),
        datetime(2026, 7, 22, 0, tzinfo=timezone.utc),
    ]


def test_interval_next_run_is_anchored_without_drift():
    runs = calculate_next_runs(
        ActionScheduleTypeEnum.INTERVAL,
        cron_expression=None,
        interval_seconds=3600,
        timezone_name="Asia/Shanghai",
        start_at=datetime(2026, 7, 20, 0, tzinfo=timezone.utc),
        end_at=None,
        now=datetime(2026, 7, 20, 1, 1, tzinfo=timezone.utc),
        count=2,
    )

    assert runs == [
        datetime(2026, 7, 20, 2, tzinfo=timezone.utc),
        datetime(2026, 7, 20, 3, tzinfo=timezone.utc),
    ]


def test_interval_respects_end_time():
    runs = calculate_next_runs(
        ActionScheduleTypeEnum.INTERVAL,
        cron_expression=None,
        interval_seconds=3600,
        timezone_name="UTC",
        start_at=datetime(2026, 7, 20, 0, tzinfo=timezone.utc),
        end_at=datetime(2026, 7, 20, 1, 30, tzinfo=timezone.utc),
        now=datetime(2026, 7, 20, 1, 1, tzinfo=timezone.utc),
        count=2,
    )

    assert runs == []


def test_latest_due_interval_returns_recent_slot():
    schedule = ActionScheduleModel.model_construct(
        id="schedule",
        name="test",
        blueprint_id="blueprint",
        schedule_type=ActionScheduleTypeEnum.INTERVAL,
        interval_seconds=3600,
        start_at=datetime(2026, 7, 20, 0, tzinfo=timezone.utc),
        enabled=True,
        priority=5,
        overlap_policy=ActionScheduleOverlapPolicyEnum.FORBID,
        misfire_policy=ActionScheduleMisfirePolicyEnum.FIRE_ONCE,
    )

    assert latest_due_time(schedule, datetime(2026, 7, 20, 3, 40, tzinfo=timezone.utc)) == datetime(
        2026, 7, 20, 3, tzinfo=timezone.utc
    )


def test_only_five_field_cron_is_accepted():
    assert validate_cron_expression(" 0  8 * * * ") == "0 8 * * *"
    with pytest.raises(ValueError, match="五段"):
        validate_cron_expression("0 0 8 * * *")


def test_schedule_payload_rejects_mixed_fields():
    with pytest.raises(ValidationError):
        ActionSchedulePayload(
            name="test",
            blueprint_id="blueprint",
            schedule_type="cron",
            cron_expression="0 8 * * *",
            interval_seconds=3600,
        )


def test_template_params_validate_required_and_type():
    blueprint = ActionBlueprintModel.model_construct(
        id="blueprint",
        name="test",
        version="1",
        description="",
        target="",
        implementation_period=60,
        graph={"nodes": [], "edges": [], "viewport": {"x": 0, "y": 0, "zoom": 1}},
        is_template=True,
        template={
            "params": [
                {"name": "page", "type": "int", "required": True},
                {"name": "platforms", "type": "tags", "required": False},
            ]
        },
    )

    validate_blueprint_params(blueprint, {"page": 1, "platforms": ["test"]})
    with pytest.raises(ValueError, match="缺少必填"):
        validate_blueprint_params(blueprint, {})
    with pytest.raises(ValueError, match="必须为整数"):
        validate_blueprint_params(blueprint, {"page": "1"})


@pytest.mark.asyncio
async def test_misfire_skip_advances_without_creating_action(monkeypatch):
    schedule = _schedule(misfire_policy=ActionScheduleMisfirePolicyEnum.SKIP)
    _patch_schedule_lock(monkeypatch)

    async def find_schedule(_query):
        return schedule

    async def fail_init(*_args, **_kwargs):
        pytest.fail("跳过错过周期时不应创建 Action")

    monkeypatch.setattr(ActionScheduleModel, "find_one", staticmethod(find_schedule))
    monkeypatch.setattr(
        "app.service.action_schedule.ActionInstanceService.init",
        fail_init,
    )

    result = await ActionScheduleService.trigger_due_schedule(
        schedule.id,
        datetime(2026, 7, 20, 3, 40, tzinfo=timezone.utc),
    )

    assert result is None
    assert schedule.last_trigger_status == "skipped_misfire"
    assert schedule.next_run_at == datetime(2026, 7, 20, 4, tzinfo=timezone.utc)
    assert schedule.save_count == 1


@pytest.mark.asyncio
async def test_overlap_forbid_skips_active_schedule_action(monkeypatch):
    schedule = _schedule(next_run_at=datetime(2026, 7, 20, 3, 40, tzinfo=timezone.utc))
    _patch_schedule_lock(monkeypatch)

    async def find_schedule(_query):
        return schedule

    async def find_active(_query):
        return SimpleNamespace(id="active-action")

    monkeypatch.setattr(ActionScheduleModel, "find_one", staticmethod(find_schedule))
    monkeypatch.setattr(ActionInstanceModel, "find_one", staticmethod(find_active))

    result = await ActionScheduleService.trigger_due_schedule(
        schedule.id,
        datetime(2026, 7, 20, 3, 40, tzinfo=timezone.utc),
    )

    assert result is None
    assert schedule.last_trigger_status == "skipped_overlap"
    assert schedule.next_run_at == datetime(2026, 7, 20, 4, tzinfo=timezone.utc)


@pytest.mark.asyncio
async def test_fire_once_uses_latest_slot_and_passes_priority(monkeypatch):
    schedule = _schedule(overlap_policy=ActionScheduleOverlapPolicyEnum.ALLOW)
    blueprint = SimpleNamespace(is_template=False)
    captured = {}
    started = []
    _patch_schedule_lock(monkeypatch)

    async def find_schedule(_query):
        return schedule

    async def find_blueprint(_query):
        return blueprint

    async def init_action(blueprint_id, params, **kwargs):
        captured.update({"blueprint_id": blueprint_id, "params": params, **kwargs})
        return True, "action-1"

    async def start_action(action_id):
        started.append(action_id)

    monkeypatch.setattr(ActionScheduleModel, "find_one", staticmethod(find_schedule))
    monkeypatch.setattr(ActionBlueprintModel, "find_one", staticmethod(find_blueprint))
    monkeypatch.setattr(
        "app.service.action_schedule.ActionInstanceService.init",
        init_action,
    )
    monkeypatch.setattr(
        "app.service.action_schedule.ActionInstanceService.start",
        start_action,
    )

    result = await ActionScheduleService.trigger_due_schedule(
        schedule.id,
        datetime(2026, 7, 20, 3, 40, tzinfo=timezone.utc),
    )

    assert result == "action-1"
    assert captured["scheduled_for"] == datetime(2026, 7, 20, 3, tzinfo=timezone.utc)
    assert captured["schedule_priority"] == 8
    assert captured["trigger_key"] == "schedule:schedule-1:2026-07-20T03:00:00+00:00"
    assert schedule.next_run_at == datetime(2026, 7, 20, 4, tzinfo=timezone.utc)
    assert schedule.last_trigger_status == "created"
    assert started == ["action-1"]


@pytest.mark.asyncio
async def test_lock_contention_does_not_read_or_trigger_schedule(monkeypatch):
    async def acquire(_schedule_id):
        return None

    async def fail_find(_query):
        pytest.fail("未取得计划锁时不应读取计划")

    monkeypatch.setattr(ActionScheduleService, "_acquire_lock", staticmethod(acquire))
    monkeypatch.setattr(ActionScheduleModel, "find_one", staticmethod(fail_find))

    assert await ActionScheduleService.trigger_due_schedule("schedule-1") is None
