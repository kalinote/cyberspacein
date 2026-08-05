"""行动整体期限与组件独立超时测试。"""

from datetime import datetime, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from pydantic import ValidationError

from app.models.action.action import ActionInstanceModel, ActionInstanceNodeModel
from app.models.action.component_run import ComponentRunModel
from app.schemas.action.blueprint import ActionBlueprintSchema
from app.schemas.action.reference import ReferenceQueueBinding
from app.schemas.action.sdk import SDKResultRequest
from app.schemas.constants import (
    ActionFlowStatusEnum,
    ActionInstanceNodeStatusEnum,
    ComponentRunStatusEnum,
)
from app.service.action import service as action_service
from app.service.component import service as component_service
from app.service.action import ActionInstanceService


class _FindOne:
    def __init__(
        self,
        value=None,
        *,
        modified_count=0,
        updates=None,
        on_update=None,
    ):
        self.value = value
        self.modified_count = modified_count
        self.updates = updates
        self.on_update = on_update

    def __await__(self):
        async def resolve():
            return self.value

        return resolve().__await__()

    async def update(self, payload):
        if self.updates is not None:
            self.updates.append(payload)
        if self.on_update is not None:
            self.on_update(payload)
        return SimpleNamespace(modified_count=self.modified_count)


class _FindMany:
    def __init__(
        self,
        values=None,
        *,
        updates=None,
        count=0,
        on_update=None,
    ):
        self.values = values or []
        self.updates = updates
        self.count_value = count
        self.on_update = on_update

    def limit(self, _limit):
        return self

    async def to_list(self):
        return self.values

    async def update(self, payload):
        if self.updates is not None:
            self.updates.append(payload)
        if self.on_update is not None:
            self.on_update(payload)
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
async def test_component_timeout_claim_keeps_lease_guard_atomic(monkeypatch):
    now = datetime.now()
    running = SimpleNamespace(
        id="run-renewed",
        attempt=1,
        result_id=None,
        progress=50,
        status=ComponentRunStatusEnum.RUNNING,
    )
    queries = []
    find_one_calls = 0

    def find_run(query):
        nonlocal find_one_calls
        find_one_calls += 1
        queries.append(query)
        if find_one_calls == 2:
            return _FindOne(modified_count=0)
        return _FindOne(running)

    monkeypatch.setattr(ComponentRunModel, "find_one", staticmethod(find_run))

    accepted = await ActionInstanceService.finish_component_run(
        running.id,
        SDKResultRequest(
            result_id="timeout:run-renewed:1",
            attempt=1,
            status="timed_out",
            error="组件心跳租约已过期",
            exit_code=1,
        ),
        _active_run_filter={"lease_expires_at": {"$lte": now}},
    )

    assert accepted is False
    assert queries[1]["lease_expires_at"] == {"$lte": now}


@pytest.mark.asyncio
async def test_component_runtime_timeout_uses_own_limit_and_keeps_zero_unlimited(monkeypatch):
    now = datetime.now()
    unlimited = SimpleNamespace(
        id="run-unlimited",
        attempt=1,
        status=ComponentRunStatusEnum.RUNNING,
        timeout_seconds=0,
        started_at=now - timedelta(hours=3),
        lease_expires_at=now + timedelta(minutes=1),
    )
    expired = SimpleNamespace(
        id="run-expired",
        attempt=1,
        status=ComponentRunStatusEnum.RUNNING,
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
    assert finish_run.await_args.kwargs["_active_run_filter"] == {
        "timeout_seconds": 5,
        "started_at": expired.started_at,
    }
    assert finish_run.await_args.args[1].error == "组件运行时限已过期"
    assert stop_run.await_args.args[0].id == "run-expired"


@pytest.mark.asyncio
async def test_dispatched_component_expires_when_sdk_never_initializes(monkeypatch):
    now = datetime.now()
    dispatched = SimpleNamespace(
        id="run-dispatched",
        attempt=1,
        status=ComponentRunStatusEnum.DISPATCHED,
        timeout_seconds=0,
        started_at=None,
        lease_expires_at=now - timedelta(seconds=1),
    )
    monkeypatch.setattr(
        ComponentRunModel,
        "find",
        staticmethod(lambda _query: _FindMany([dispatched])),
    )
    finish_run = AsyncMock(return_value=True)
    stop_run = AsyncMock(return_value=True)
    monkeypatch.setattr(ActionInstanceService, "finish_component_run", finish_run)
    monkeypatch.setattr(action_service, "cancel_component_run", stop_run)

    assert await ActionInstanceService.expire_stale_component_runs() == 1
    result = finish_run.await_args.args[1]
    assert result.status == "timed_out"
    assert "完成初始化" in result.error
    lease_guard = finish_run.await_args.kwargs["_active_run_filter"]
    assert set(lease_guard) == {"lease_expires_at"}
    assert now <= lease_guard["lease_expires_at"]["$lte"] <= datetime.now()
    stop_run.assert_awaited_once_with(dispatched)


@pytest.mark.asyncio
async def test_legacy_dispatched_component_without_lease_is_recovered(monkeypatch):
    now = datetime.now()
    dispatched = SimpleNamespace(
        id="run-without-lease",
        attempt=1,
        status=ComponentRunStatusEnum.DISPATCHED,
        timeout_seconds=0,
        started_at=None,
        lease_expires_at=None,
        updated_at=now
        - timedelta(
            seconds=action_service.settings.COMPONENT_BOOTSTRAP_EXPIRE_SECONDS
            + 1
        ),
    )
    monkeypatch.setattr(
        ComponentRunModel,
        "find",
        staticmethod(lambda _query: _FindMany([dispatched])),
    )
    finish_run = AsyncMock(return_value=True)
    stop_run = AsyncMock(return_value=True)
    monkeypatch.setattr(ActionInstanceService, "finish_component_run", finish_run)
    monkeypatch.setattr(action_service, "cancel_component_run", stop_run)

    assert await ActionInstanceService.expire_stale_component_runs() == 1
    assert finish_run.await_args.args[0] == "run-without-lease"
    assert "完成初始化" in finish_run.await_args.args[1].error
    assert finish_run.await_args.kwargs["_active_run_filter"]["status"] == (
        ComponentRunStatusEnum.DISPATCHED
    )
    assert (
        finish_run.await_args.kwargs["_active_run_filter"]["lease_expires_at"]
        is None
    )
    stop_run.assert_awaited_once_with(dispatched)


@pytest.mark.asyncio
async def test_renewed_component_is_not_cancelled_from_stale_snapshot(monkeypatch):
    now = datetime.now()
    stale_snapshot = SimpleNamespace(
        id="run-renewed",
        attempt=1,
        status=ComponentRunStatusEnum.RUNNING,
        timeout_seconds=0,
        started_at=now - timedelta(minutes=1),
        lease_expires_at=now - timedelta(seconds=1),
    )
    monkeypatch.setattr(
        ComponentRunModel,
        "find",
        staticmethod(lambda _query: _FindMany([stale_snapshot])),
    )
    finish_run = AsyncMock(return_value=False)
    stop_run = AsyncMock(return_value=True)
    monkeypatch.setattr(ActionInstanceService, "finish_component_run", finish_run)
    monkeypatch.setattr(action_service, "cancel_component_run", stop_run)

    assert await ActionInstanceService.expire_stale_component_runs() == 0
    finish_run.assert_awaited_once()
    stop_run.assert_not_awaited()


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
async def test_managed_timeout_cleanup_is_not_reversed_by_abort_retry(
    monkeypatch,
):
    now = datetime.now()
    action = SimpleNamespace(
        id="action-managed-timeout",
        status=ActionFlowStatusEnum.RUNNING,
        implementation_period=5,
        deadline_at=now - timedelta(seconds=1),
        start_at=now - timedelta(seconds=6),
        paused_duration=0,
        reference_queue_lifecycle="active",
        queue_cleanup_state="pending",
    )
    binding = ReferenceQueueBinding(
        edge_id="edge-1",
        stream_id="stream-1",
        queue_name="managed-queue",
        owner_action_id=action.id,
        source_node_id="source",
        source_port_id="out",
        target_node_id="target",
        target_port_id="in",
    )
    node = SimpleNamespace(
        id="source-instance",
        error_message="行动整体执行超时，节点未再运行",
        reference_queue_bindings={"edge-1": binding},
        save=AsyncMock(),
    )
    queues = {binding.queue_name}
    events = []

    def matches(document, query):
        for field, expected in query.items():
            if field == "$or":
                if not any(matches(document, branch) for branch in expected):
                    return False
                continue
            actual = (
                document.id if field == "_id" else getattr(document, field)
            )
            if isinstance(expected, dict):
                if "$in" in expected and actual not in expected["$in"]:
                    return False
                if "$gt" in expected and actual <= expected["$gt"]:
                    return False
                continue
            if actual != expected:
                return False
        return True

    def update_action(payload):
        for field, value in payload.get("$set", {}).items():
            setattr(action, field, value)

    def find_actions(query):
        return _FindMany([action] if matches(action, query) else [])

    def find_action(query):
        matched = matches(action, query)
        return _FindOne(
            action if matched else None,
            modified_count=1 if matched else 0,
            on_update=update_action if matched else None,
        )

    def find_nodes(query):
        if query == {"action_id": action.id}:
            return _FindMany([node])
        return _FindMany()

    async def delete_queue(queue_name):
        events.append(("delete", queue_name))
        queues.discard(queue_name)
        return True

    async def publish_control(**kwargs):
        events.append(("publish", kwargs["queue_names"][0]))

    monkeypatch.setattr(
        ActionInstanceModel,
        "find",
        staticmethod(find_actions),
    )
    monkeypatch.setattr(
        ActionInstanceModel,
        "find_one",
        staticmethod(find_action),
    )
    monkeypatch.setattr(
        ActionInstanceNodeModel,
        "find",
        staticmethod(find_nodes),
    )
    monkeypatch.setattr(
        ComponentRunModel,
        "find",
        staticmethod(lambda _query: _FindMany()),
    )
    monkeypatch.setattr(action_service, "delete_queue", delete_queue)
    monkeypatch.setattr(
        action_service,
        "publish_reference_control",
        publish_control,
    )
    monkeypatch.setattr(
        action_service.RuntimeDomainEventService,
        "publish_action_terminal",
        AsyncMock(),
    )
    monkeypatch.setattr(
        action_service,
        "publish_action_status_observation",
        AsyncMock(),
    )
    monkeypatch.setattr(
        ActionInstanceService,
        "cancel_node_executions",
        AsyncMock(return_value=0),
    )
    monkeypatch.setattr(
        ActionInstanceService,
        "cancel_reference_bridges",
        AsyncMock(return_value=0),
    )
    reference_state_collection = SimpleNamespace(
        find_one=AsyncMock(return_value={}),
        update_one=AsyncMock(
            return_value=SimpleNamespace(modified_count=1)
        ),
    )
    monkeypatch.setattr(
        ActionInstanceModel,
        "get_motor_collection",
        staticmethod(lambda: reference_state_collection),
    )

    round_results = [
        (
            await ActionInstanceService.expire_stale_actions(),
            await ActionInstanceService.retry_open_reference_aborts(),
            await ActionInstanceService.retry_failed_queue_cleanup(),
        )
    ]
    action.finished_at = datetime.now() - timedelta(
        seconds=action_service.REFERENCE_QUEUE_CLEANUP_GRACE_SECONDS + 1
    )
    round_results.append(
        (
            await ActionInstanceService.expire_stale_actions(),
            await ActionInstanceService.retry_open_reference_aborts(),
            await ActionInstanceService.retry_failed_queue_cleanup(),
        )
    )

    assert round_results == [(1, 0, 0), (0, 0, 1)]
    assert action.status == ActionFlowStatusEnum.TIMEOUT
    assert action.reference_queue_lifecycle == "cleaned"
    assert action.queue_cleanup_state == "completed"
    assert queues == set()
    delete_index = events.index(("delete", binding.queue_name))
    assert not any(event[0] == "publish" for event in events[delete_index + 1 :])


@pytest.mark.asyncio
async def test_finish_action_prefers_timeout_status(monkeypatch):
    action = SimpleNamespace(
        id="action-1",
        status=ActionFlowStatusEnum.RUNNING,
        start_at=datetime.now() - timedelta(seconds=3),
        finished_nodes_instance=[],
        nodes_id=["node-1"],
        execution_plan_snapshot=SimpleNamespace(
            nodes=[SimpleNamespace(id="node-1")]
        ),
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
async def test_dispatch_assigns_sdk_startup_lease(monkeypatch):
    now_before = datetime.now()
    claim_updates = []
    active_run = SimpleNamespace(
        id="run-1",
        action_id="action-1",
        component_id="component-1",
        status=ComponentRunStatusEnum.DISPATCHED,
        cancel_requested=False,
    )
    component_run = SimpleNamespace(
        id=active_run.id,
        action_id=active_run.action_id,
        component_id=active_run.component_id,
    )

    def find_component(query):
        if query.get("status") == ComponentRunStatusEnum.CREATED:
            return _FindOne(modified_count=1, updates=claim_updates)
        return _FindOne(active_run)

    monkeypatch.setattr(
        ActionInstanceModel,
        "find_one",
        AsyncMock(
            return_value=SimpleNamespace(status=ActionFlowStatusEnum.RUNNING)
        ),
    )
    monkeypatch.setattr(
        ComponentRunModel,
        "find_one",
        staticmethod(find_component),
    )
    monkeypatch.setattr(
        component_service,
        "run_component",
        AsyncMock(return_value={"_id": "platform-task-1"}),
    )

    accepted = await component_service.dispatch_component_run(
        component_run,
        "csi-component",
        ["run", "main:run"],
    )

    assert accepted is True
    lease_expires_at = claim_updates[0]["$set"]["lease_expires_at"]
    expected_seconds = component_service.settings.COMPONENT_BOOTSTRAP_EXPIRE_SECONDS
    assert timedelta(seconds=expected_seconds - 1) <= lease_expires_at - now_before
    assert lease_expires_at - now_before <= timedelta(seconds=expected_seconds + 1)


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
