"""行动暂停、恢复和停止控制测试。"""

from datetime import datetime, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from app.models.action.action import ActionInstanceModel, ActionInstanceNodeModel
from app.models.action.component_run import ComponentRunModel
from app.schemas.constants import (
    ActionFlowStatusEnum,
    ActionInstanceNodeStatusEnum,
    ComponentRunStatusEnum,
)
from app.service import action as action_service
from app.service import component as component_service
from app.service.action import ActionInstanceService


class _FindOne:
    def __init__(self, value=None, *, modified_count=0, updates=None):
        self.value = value
        self.modified_count = modified_count
        self.updates = updates

    def __await__(self):
        async def resolve():
            return self.value

        return resolve().__await__()

    async def update(self, payload):
        if self.updates is not None:
            self.updates.append(payload)
        return SimpleNamespace(modified_count=self.modified_count)


class _FindMany:
    def __init__(self, values=None, *, updates=None, count=0):
        self.values = values or []
        self.updates = updates
        self.count_value = count

    async def to_list(self):
        return self.values

    async def update(self, payload):
        if self.updates is not None:
            self.updates.append(payload)
        return SimpleNamespace(modified_count=len(self.values))

    async def count(self):
        return self.count_value


@pytest.mark.asyncio
async def test_pause_keeps_queues_and_pauses_only_idle_nodes(monkeypatch):
    action = SimpleNamespace(status=ActionFlowStatusEnum.RUNNING)
    action_updates = []
    node_updates = []
    find_action_calls = 0

    def find_action(_query):
        nonlocal find_action_calls
        find_action_calls += 1
        if find_action_calls == 1:
            return _FindOne(action)
        return _FindOne(modified_count=1, updates=action_updates)

    monkeypatch.setattr(ActionInstanceModel, "find_one", staticmethod(find_action))
    monkeypatch.setattr(
        ActionInstanceNodeModel,
        "find",
        staticmethod(lambda _query: _FindMany(updates=node_updates)),
    )
    cleanup = AsyncMock()
    monkeypatch.setattr(ActionInstanceService, "cleanup_action_queues", cleanup)

    success, _ = await ActionInstanceService.pause("action-1")

    assert success is True
    assert action_updates[0]["$set"]["status"] == ActionFlowStatusEnum.PAUSED
    assert node_updates[0]["$set"]["status"] == ActionInstanceNodeStatusEnum.PAUSED
    cleanup.assert_not_awaited()


@pytest.mark.asyncio
async def test_resume_extends_deadline_and_restores_ready_node(monkeypatch):
    paused_at = datetime.now() - timedelta(seconds=8)
    deadline_at = datetime.now() + timedelta(seconds=30)
    paused_action = SimpleNamespace(
        id="action-1",
        blueprint_id="blueprint-1",
        status=ActionFlowStatusEnum.PAUSED,
        paused_at=paused_at,
        paused_duration=3,
        deadline_at=deadline_at,
    )
    running_action = SimpleNamespace(
        **{
            **paused_action.__dict__,
            "status": ActionFlowStatusEnum.RUNNING,
            "paused_at": None,
        }
    )
    paused_node = SimpleNamespace(
        id="node-instance-1",
        node_id="node-1",
        definition_id="definition-1",
        status=ActionInstanceNodeStatusEnum.PAUSED,
    )
    action_updates = []
    node_updates = []
    plain_find_calls = 0

    def find_action(query):
        nonlocal plain_find_calls
        if query.get("status") == ActionFlowStatusEnum.PAUSED:
            return _FindOne(modified_count=1, updates=action_updates)
        if query.get("status") == ActionFlowStatusEnum.RUNNING:
            return _FindOne(running_action)
        plain_find_calls += 1
        return _FindOne(paused_action if plain_find_calls == 1 else running_action)

    def find_nodes(query):
        if "status" not in query:
            return _FindMany([paused_node])
        return _FindMany([])

    monkeypatch.setattr(ActionInstanceModel, "find_one", staticmethod(find_action))
    monkeypatch.setattr(ActionInstanceNodeModel, "find", staticmethod(find_nodes))
    monkeypatch.setattr(
        ActionInstanceNodeModel,
        "find_one",
        staticmethod(
            lambda _query: _FindOne(modified_count=1, updates=node_updates)
        ),
    )
    monkeypatch.setattr(
        ActionInstanceService,
        "get_action_blueprint",
        AsyncMock(return_value=SimpleNamespace(graph=SimpleNamespace(edges=[]))),
    )
    monkeypatch.setattr(
        ActionInstanceService,
        "check_action_finished",
        AsyncMock(return_value=False),
    )

    success, _ = await ActionInstanceService.resume("action-1")

    assert success is True
    resume_fields = action_updates[0]["$set"]
    assert resume_fields["status"] == ActionFlowStatusEnum.RUNNING
    assert resume_fields["paused_at"] is None
    assert resume_fields["deadline_at"] > deadline_at
    assert node_updates[0]["$set"]["status"] == ActionInstanceNodeStatusEnum.READY


@pytest.mark.asyncio
async def test_stop_is_terminal_cancels_components_and_cleans_queues(monkeypatch):
    now = datetime.now()
    action = SimpleNamespace(
        status=ActionFlowStatusEnum.RUNNING,
        start_at=now - timedelta(seconds=20),
        paused_at=None,
        paused_duration=4,
    )
    active_run = SimpleNamespace(id="run-1")
    action_updates = []
    component_updates = []
    node_updates = []
    find_action_calls = 0

    def find_action(_query):
        nonlocal find_action_calls
        find_action_calls += 1
        if find_action_calls == 1:
            return _FindOne(action)
        return _FindOne(modified_count=1, updates=action_updates)

    component_find_calls = 0

    def find_components(_query):
        nonlocal component_find_calls
        component_find_calls += 1
        if component_find_calls == 1:
            return _FindMany([active_run])
        return _FindMany(updates=component_updates)

    monkeypatch.setattr(ActionInstanceModel, "find_one", staticmethod(find_action))
    monkeypatch.setattr(ComponentRunModel, "find", staticmethod(find_components))
    monkeypatch.setattr(
        ActionInstanceNodeModel,
        "find",
        staticmethod(lambda _query: _FindMany(updates=node_updates)),
    )
    cancel = AsyncMock(return_value=True)
    cleanup = AsyncMock(return_value=True)
    monkeypatch.setattr(action_service, "cancel_component_run", cancel)
    monkeypatch.setattr(ActionInstanceService, "cleanup_action_queues", cleanup)

    success, _ = await ActionInstanceService.stop("action-1")

    assert success is True
    assert action_updates[0]["$set"]["status"] == ActionFlowStatusEnum.STOPPED
    assert component_updates[0]["$set"]["status"] == ComponentRunStatusEnum.CANCELLED
    assert node_updates[0]["$set"]["status"] == ActionInstanceNodeStatusEnum.CANCELLED
    cancel.assert_awaited_once_with(active_run)
    cleanup.assert_awaited_once_with("action-1")


@pytest.mark.asyncio
async def test_stopped_action_cannot_resume(monkeypatch):
    monkeypatch.setattr(
        ActionInstanceModel,
        "find_one",
        AsyncMock(
            return_value=SimpleNamespace(status=ActionFlowStatusEnum.STOPPED)
        ),
    )

    success, message = await ActionInstanceService.resume("action-1")

    assert success is False
    assert message == "已停止的行动无法恢复"


@pytest.mark.asyncio
async def test_paused_action_cannot_lose_queues_to_finish_race(monkeypatch):
    action = SimpleNamespace(
        status=ActionFlowStatusEnum.PAUSED,
        start_at=datetime.now() - timedelta(seconds=5),
        paused_duration=0,
        finished_nodes_instance=[],
        nodes_id=["node-1"],
    )
    find_action_calls = 0

    def find_action(_query):
        nonlocal find_action_calls
        find_action_calls += 1
        if find_action_calls == 1:
            return _FindOne(action)
        return _FindOne(modified_count=0)

    monkeypatch.setattr(ActionInstanceModel, "find_one", staticmethod(find_action))
    monkeypatch.setattr(
        ActionInstanceNodeModel,
        "find",
        staticmethod(lambda _query: _FindMany(count=0)),
    )
    cleanup = AsyncMock()
    monkeypatch.setattr(ActionInstanceService, "cleanup_action_queues", cleanup)

    assert await ActionInstanceService.finish_action("action-1") is False
    cleanup.assert_not_awaited()


@pytest.mark.asyncio
async def test_paused_action_does_not_cancel_created_component(monkeypatch):
    component_run = SimpleNamespace(
        action_id="action-1",
        status=ComponentRunStatusEnum.CREATED,
        save=AsyncMock(),
    )
    monkeypatch.setattr(
        ActionInstanceModel,
        "find_one",
        AsyncMock(
            return_value=SimpleNamespace(status=ActionFlowStatusEnum.PAUSED)
        ),
    )
    run_component = AsyncMock()
    monkeypatch.setattr(component_service, "run_component", run_component)

    accepted = await component_service.dispatch_component_run(
        component_run,
        "csi-component",
        ["run", "main:run"],
    )

    assert accepted is False
    assert component_run.status == ComponentRunStatusEnum.CREATED
    component_run.save.assert_not_awaited()
    run_component.assert_not_awaited()
