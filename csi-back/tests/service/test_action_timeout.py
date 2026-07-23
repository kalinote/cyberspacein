"""行动整体期限与组件独立超时测试。"""

from datetime import datetime, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from pydantic import ValidationError

from app.models.action.action import ActionInstanceModel, ActionInstanceNodeModel
from app.models.action.component_run import ComponentRunModel
from app.schemas.action.blueprint import ActionBlueprintSchema
from app.schemas.action.sdk import SDKResultRequest
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


def _blueprint_payload(implementation_period=None):
    payload = {
        "name": "测试蓝图",
        "description": "",
        "version": "1.0.0",
        "target": "测试",
        "graph": {
            "nodes": [],
            "edges": [],
            "viewport": {"x": 0, "y": 0, "zoom": 1},
        },
    }
    if implementation_period is not None:
        payload["implementation_period"] = implementation_period
    return payload


def test_action_timeout_defaults_to_unlimited_and_rejects_negative():
    assert ActionBlueprintSchema.model_validate(_blueprint_payload()).implementation_period == 0
    with pytest.raises(ValidationError):
        ActionBlueprintSchema.model_validate(_blueprint_payload(-1))


@pytest.mark.asyncio
async def test_timed_out_component_waits_for_running_sibling(monkeypatch):
    running = SimpleNamespace(
        id="run-timeout",
        attempt=1,
        result_id=None,
        progress=10,
        node_instance_id="node-1",
        status=ComponentRunStatusEnum.RUNNING,
    )
    timed_out = SimpleNamespace(
        **{**running.__dict__, "status": ComponentRunStatusEnum.TIMED_OUT}
    )
    sibling = SimpleNamespace(status=ComponentRunStatusEnum.RUNNING)
    node = SimpleNamespace(id="node-1")
    find_one_values = [running, None, timed_out]

    def find_run(_query):
        value = find_one_values.pop(0)
        if value is None:
            return _FindOne(modified_count=1)
        return _FindOne(value)

    monkeypatch.setattr(ComponentRunModel, "find_one", staticmethod(find_run))
    monkeypatch.setattr(
        ComponentRunModel,
        "find",
        staticmethod(lambda _query: _FindMany([timed_out, sibling])),
    )
    monkeypatch.setattr(
        ActionInstanceNodeModel,
        "find_one",
        staticmethod(lambda _query: _FindOne(node)),
    )
    finish_node = AsyncMock()
    monkeypatch.setattr(ActionInstanceService, "finish_node", finish_node)

    accepted = await ActionInstanceService.finish_component_run(
        running.id,
        SDKResultRequest(
            result_id="result-timeout",
            attempt=1,
            status="timed_out",
            error="组件超时",
            exit_code=1,
        ),
    )

    assert accepted is True
    finish_node.assert_not_awaited()


@pytest.mark.asyncio
async def test_node_becomes_timeout_after_other_components_finish(monkeypatch):
    running = SimpleNamespace(
        id="run-success",
        attempt=1,
        result_id=None,
        progress=90,
        node_instance_id="node-1",
        status=ComponentRunStatusEnum.RUNNING,
    )
    succeeded = SimpleNamespace(
        **{
            **running.__dict__,
            "status": ComponentRunStatusEnum.SUCCEEDED,
            "component_id": "component-success",
            "outputs": {},
        }
    )
    timed_out = SimpleNamespace(
        status=ComponentRunStatusEnum.TIMED_OUT,
        component_id="component-timeout",
        error_message="组件超时",
        exit_code=1,
        outputs={},
    )
    node = SimpleNamespace(id="node-1", definition_id="definition-1")
    find_one_values = [running, None, succeeded]

    def find_run(_query):
        value = find_one_values.pop(0)
        if value is None:
            return _FindOne(modified_count=1)
        return _FindOne(value)

    node_find_calls = 0

    def find_node(_query):
        nonlocal node_find_calls
        node_find_calls += 1
        if node_find_calls == 1:
            return _FindOne(node)
        return _FindOne(modified_count=1)

    monkeypatch.setattr(ComponentRunModel, "find_one", staticmethod(find_run))
    monkeypatch.setattr(
        ComponentRunModel,
        "find",
        staticmethod(lambda _query: _FindMany([timed_out, succeeded])),
    )
    monkeypatch.setattr(ActionInstanceNodeModel, "find_one", staticmethod(find_node))
    finish_node = AsyncMock(return_value=True)
    monkeypatch.setattr(ActionInstanceService, "finish_node", finish_node)

    await ActionInstanceService.finish_component_run(
        running.id,
        SDKResultRequest(
            result_id="result-success",
            attempt=1,
            status="success",
            outputs={},
            exit_code=0,
        ),
    )

    assert finish_node.await_args.args[1].status == "timed_out"


@pytest.mark.asyncio
async def test_component_runtime_timeout_uses_own_limit_and_keeps_zero_unlimited(monkeypatch):
    now = datetime.now()
    unlimited = SimpleNamespace(
        id="run-unlimited",
        attempt=1,
        timeout_seconds=0,
        started_at=now - timedelta(hours=3),
        lease_expires_at=now + timedelta(minutes=1),
    )
    expired = SimpleNamespace(
        id="run-expired",
        attempt=1,
        timeout_seconds=5,
        started_at=now - timedelta(seconds=10),
        lease_expires_at=now + timedelta(minutes=1),
    )
    monkeypatch.setattr(
        ComponentRunModel,
        "find",
        staticmethod(lambda _query: _FindMany([unlimited, expired])),
    )
    finish_run = AsyncMock(return_value=True)
    stop_run = AsyncMock(return_value=True)
    monkeypatch.setattr(ActionInstanceService, "finish_component_run", finish_run)
    monkeypatch.setattr(action_service, "cancel_component_run", stop_run)

    assert await ActionInstanceService.expire_stale_component_runs() == 1
    assert finish_run.await_args.args[0] == "run-expired"
    assert stop_run.await_args.args[0].id == "run-expired"


@pytest.mark.asyncio
async def test_overall_timeout_stops_active_runs_and_cancels_future_nodes(monkeypatch):
    now = datetime.now()
    action = SimpleNamespace(
        id="action-1",
        status=ActionFlowStatusEnum.RUNNING,
        implementation_period=5,
        deadline_at=now - timedelta(seconds=1),
        start_at=now - timedelta(seconds=6),
    )
    active_run = SimpleNamespace(id="run-1")
    action_updates = []
    component_updates = []
    node_updates = []

    monkeypatch.setattr(
        ActionInstanceModel,
        "find",
        staticmethod(lambda _query: _FindMany([action])),
    )
    monkeypatch.setattr(
        ActionInstanceModel,
        "find_one",
        staticmethod(
            lambda _query: _FindOne(modified_count=1, updates=action_updates)
        ),
    )
    component_find_calls = 0

    def find_components(_query):
        nonlocal component_find_calls
        component_find_calls += 1
        if component_find_calls == 1:
            return _FindMany([active_run])
        return _FindMany(updates=component_updates)

    monkeypatch.setattr(ComponentRunModel, "find", staticmethod(find_components))
    monkeypatch.setattr(
        ActionInstanceNodeModel,
        "find",
        staticmethod(lambda _query: _FindMany(updates=node_updates)),
    )
    stop_run = AsyncMock(return_value=True)
    monkeypatch.setattr(action_service, "cancel_component_run", stop_run)
    monkeypatch.setattr(ActionInstanceService, "cleanup_action_queues", AsyncMock())

    assert await ActionInstanceService.expire_stale_actions() == 1
    assert action_updates[0]["$set"]["status"] == ActionFlowStatusEnum.TIMEOUT
    assert component_updates[0]["$set"]["cancel_requested"] is True
    assert [update["$set"]["status"] for update in node_updates] == [
        ActionInstanceNodeStatusEnum.TIMEOUT,
        ActionInstanceNodeStatusEnum.CANCELLED,
    ]
    stop_run.assert_awaited_once_with(active_run)


@pytest.mark.asyncio
async def test_finish_action_prefers_timeout_status(monkeypatch):
    action = SimpleNamespace(
        id="action-1",
        status=ActionFlowStatusEnum.RUNNING,
        start_at=datetime.now() - timedelta(seconds=3),
        finished_nodes_instance=[],
        nodes_id=["node-1"],
    )
    action_updates = []
    find_action_calls = 0

    def find_action(_query):
        nonlocal find_action_calls
        find_action_calls += 1
        if find_action_calls == 1:
            return _FindOne(action)
        return _FindOne(modified_count=1, updates=action_updates)

    node_find_calls = 0

    def find_nodes(_query):
        nonlocal node_find_calls
        node_find_calls += 1
        return _FindMany(count=1 if node_find_calls == 1 else 0)

    monkeypatch.setattr(ActionInstanceModel, "find_one", staticmethod(find_action))
    monkeypatch.setattr(ActionInstanceNodeModel, "find", staticmethod(find_nodes))
    monkeypatch.setattr(ActionInstanceService, "cleanup_action_queues", AsyncMock())

    assert await ActionInstanceService.finish_action(action.id) is True
    assert action_updates[0]["$set"]["status"] == ActionFlowStatusEnum.TIMEOUT


@pytest.mark.asyncio
async def test_timeout_predecessor_cancels_dependent_node(monkeypatch):
    dependent = SimpleNamespace(
        id="node-dependent",
        node_id="dependent",
        status=ActionInstanceNodeStatusEnum.UNREADY,
        finished_at=None,
        save=AsyncMock(),
    )

    async def next_nodes(_action_id, node_id):
        return {dependent.id: []} if node_id == "timed-out" else {}

    monkeypatch.setattr(ActionInstanceService, "find_next_node", next_nodes)
    monkeypatch.setattr(
        ActionInstanceNodeModel,
        "find_one",
        AsyncMock(return_value=dependent),
    )

    await ActionInstanceService.cancel_following_nodes("action-1", "timed-out")

    assert dependent.status == ActionInstanceNodeStatusEnum.CANCELLED
    dependent.save.assert_awaited_once()


@pytest.mark.asyncio
async def test_cancel_component_run_calls_platform_cancel_endpoint(monkeypatch):
    component_run = SimpleNamespace(
        id="run-1",
        platform_task_id="platform-task-1",
        dispatch_ref=None,
    )
    post = AsyncMock(return_value={"code": 0, "data": {}})
    monkeypatch.setattr(component_service, "async_post", post)

    assert await component_service.cancel_component_run(component_run) is True
    assert post.await_args.args[0].endswith("/tasks/platform-task-1/cancel")


@pytest.mark.asyncio
async def test_component_is_not_dispatched_after_action_timeout(monkeypatch):
    component_run = SimpleNamespace(
        id="run-1",
        action_id="action-1",
        status=ComponentRunStatusEnum.CREATED,
        cancel_requested=False,
        error_message=None,
        finished_at=None,
        updated_at=None,
        save=AsyncMock(),
    )
    monkeypatch.setattr(
        ActionInstanceModel,
        "find_one",
        AsyncMock(
            return_value=SimpleNamespace(status=ActionFlowStatusEnum.TIMEOUT)
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
    assert component_run.status == ComponentRunStatusEnum.CANCELLED
    component_run.save.assert_awaited_once()
    run_component.assert_not_awaited()
