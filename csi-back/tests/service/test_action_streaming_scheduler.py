from datetime import datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from app.models.action.action import ActionInstanceModel, ActionInstanceNodeModel
from app.models.action.component_run import ComponentRunModel
from app.models.action.reference_bridge import ReferenceBridgeModel
from app.schemas.action.execution import BlueprintExecutionPlan
from app.schemas.action.reference import (
    ReferenceProducerKindEnum,
    ReferenceQueueBinding,
)
from app.schemas.action.sdk import SDKResultRequest
from app.schemas.constants import (
    ActionFlowStatusEnum,
    ActionInstanceNodeStatusEnum,
    ActionInvocationModeEnum,
    ActionSchedulingModeEnum,
    ComponentRunStatusEnum,
)
from app.service.action import ActionInstanceService
from app.service.action import service as action_service


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
    def __init__(self, values=None, *, count=0, updates=None):
        self.values = values or []
        self._count = count
        self.updates = updates

    async def to_list(self):
        return self.values

    async def count(self):
        return self._count

    async def update(self, payload):
        if self.updates is not None:
            self.updates.append(payload)
        return SimpleNamespace(modified_count=len(self.values))

    def sort(self, *_args):
        return self

    def limit(self, value):
        self.values = self.values[:value]
        return self


def _edge(edge_id: str, data_type: str = "reference") -> SimpleNamespace:
    """构造聚焦调度测试使用的执行边。"""
    return SimpleNamespace(
        id=edge_id,
        source="source",
        target="target",
        source_port_id="out",
        target_port_id="in",
        data_type=data_type,
    )


async def _run_readiness_case(
    monkeypatch,
    *,
    mode: ActionSchedulingModeEnum,
    data_type: str,
    source_status: ActionInstanceNodeStatusEnum,
    activated: bool = False,
    delivered: bool = False,
    aborted: bool = False,
) -> list[dict]:
    """运行一个单入边节点，并返回调度器对节点执行的字段更新。"""
    edge = _edge("edge-1", data_type)
    node = SimpleNamespace(
        id="target-instance",
        node_id="target",
        definition_id="definition-1",
        definition_snapshot={},
        delivered_dependencies=[],
        activated_input_edge_ids=[edge.id] if activated else [],
        delivered_input_edge_ids=[edge.id] if delivered else [],
        aborted_input_edge_ids=[edge.id] if aborted else [],
    )
    source = SimpleNamespace(node_id="source", status=source_status)
    action = SimpleNamespace(
        id="action-1",
        status=ActionFlowStatusEnum.RUNNING,
        execution_plan_snapshot=SimpleNamespace(
            plan_schema_version=3,
            scheduling_mode=mode,
            extension={"scheduler": {"readiness": "edge-v2"}},
            nodes=[
                SimpleNamespace(
                    id="target",
                    extension_spec=None,
                    effective_in_degree=1,
                )
            ],
            edges=[edge],
        ),
    )
    updates = []
    node_find_calls = 0

    def find_node(_query):
        nonlocal node_find_calls
        node_find_calls += 1
        if node_find_calls == 1:
            return _FindOne(node)
        return _FindOne(modified_count=0, updates=updates)

    monkeypatch.setattr(
        ActionInstanceNodeModel,
        "find_one",
        staticmethod(find_node),
    )
    monkeypatch.setattr(
        ActionInstanceNodeModel,
        "find",
        staticmethod(lambda _query: _FindMany([source])),
    )
    monkeypatch.setattr(
        ActionInstanceModel,
        "find_one",
        AsyncMock(return_value=action),
    )
    monkeypatch.setattr(
        ActionInstanceService,
        "get_instance_node_definition",
        AsyncMock(return_value=SimpleNamespace(id="definition-1")),
    )
    monkeypatch.setattr(
        ActionInstanceService,
        "find_all_previous_nodes",
        AsyncMock(return_value=["source"]),
    )

    assert await ActionInstanceService.run_node(node.id, action.id) is False
    return updates


def test_v2_plan_and_runtime_always_fall_back_to_barrier() -> None:
    plan = BlueprintExecutionPlan(
        plan_schema_version=2,
        invocation_mode=ActionInvocationModeEnum.STANDALONE,
        scheduling_mode=ActionSchedulingModeEnum.STREAMING,
        nodes=[],
        edges=[],
    )
    action = SimpleNamespace(execution_plan_snapshot=plan)

    assert plan.scheduling_mode == ActionSchedulingModeEnum.BARRIER
    assert (
        ActionInstanceService._get_scheduling_mode(action)
        == ActionSchedulingModeEnum.BARRIER
    )


def test_exact_map_expression_preserves_dotted_port_id() -> None:
    value = {"key": "value", "value": "$literal-value", "type": "value"}

    expression = ActionInstanceService._build_exact_map_expression(
        "outputs",
        {"builtin.blueprint.input.value": value},
    )

    assert expression == {
        "$setField": {
            "field": {"$literal": "builtin.blueprint.input.value"},
            "input": {"$ifNull": ["$outputs", {}]},
            "value": {"$literal": value},
        }
    }


@pytest.mark.asyncio
async def test_failed_component_waits_for_running_sibling(monkeypatch) -> None:
    active = SimpleNamespace(
        id="run-failed",
        attempt=1,
        result_id=None,
        progress=40,
        node_instance_id="node-1",
        status=ComponentRunStatusEnum.RUNNING,
    )
    failed = SimpleNamespace(
        **{
            **active.__dict__,
            "status": ComponentRunStatusEnum.FAILED,
            "error_message": "组件失败",
            "exit_code": 1,
            "has_successful_result": False,
        }
    )
    sibling = SimpleNamespace(
        id="run-sibling",
        status=ComponentRunStatusEnum.RUNNING,
        has_successful_result=False,
    )
    node = SimpleNamespace(id="node-1")
    find_one_values = [active, None, failed]
    cancellation_updates = []

    def find_run(_query):
        value = find_one_values.pop(0)
        if value is None:
            return _FindOne(modified_count=1)
        return _FindOne(value)

    def find_runs(query):
        if "status" in query:
            return _FindMany([sibling], updates=cancellation_updates)
        return _FindMany([failed, sibling])

    monkeypatch.setattr(ComponentRunModel, "find_one", staticmethod(find_run))
    monkeypatch.setattr(ComponentRunModel, "find", staticmethod(find_runs))
    monkeypatch.setattr(
        ActionInstanceNodeModel,
        "find_one",
        staticmethod(lambda _query: _FindOne(node)),
    )
    finish_node = AsyncMock()
    monkeypatch.setattr(ActionInstanceService, "finish_node", finish_node)

    assert await ActionInstanceService.finish_component_run(
        active.id,
        SDKResultRequest(
            result_id="result-failed",
            attempt=1,
            status="failed",
            error="组件失败",
            exit_code=1,
        ),
    )

    assert any(
        update["$set"].get("cancel_requested") is True
        for update in cancellation_updates
    )
    finish_node.assert_not_awaited()


@pytest.mark.asyncio
async def test_retried_component_result_resumes_node_finalization(monkeypatch) -> None:
    terminal_run = SimpleNamespace(
        id="run-failed",
        attempt=1,
        result_id="result-failed",
        progress=80,
        node_instance_id="node-1",
        status=ComponentRunStatusEnum.FAILED,
        error_message="组件失败",
        exit_code=1,
        has_successful_result=True,
    )
    node = SimpleNamespace(id="node-1", finalization_claimed=False)
    node_find_calls = 0

    def find_node(_query):
        nonlocal node_find_calls
        node_find_calls += 1
        if node_find_calls == 1:
            return _FindOne(node)
        return _FindOne(modified_count=1)

    monkeypatch.setattr(
        ComponentRunModel,
        "find_one",
        staticmethod(lambda _query: _FindOne(terminal_run)),
    )
    monkeypatch.setattr(
        ComponentRunModel,
        "find",
        staticmethod(
            lambda query: (
                _FindMany([])
                if "status" in query
                else _FindMany([terminal_run])
            )
        ),
    )
    monkeypatch.setattr(
        ActionInstanceNodeModel,
        "find_one",
        staticmethod(find_node),
    )
    finish_node = AsyncMock(return_value=True)
    monkeypatch.setattr(ActionInstanceService, "finish_node", finish_node)

    assert await ActionInstanceService.finish_component_run(
        terminal_run.id,
        SDKResultRequest(
            result_id=terminal_run.result_id,
            attempt=terminal_run.attempt,
            status="failed",
            error=terminal_run.error_message,
            has_successful_result=True,
            exit_code=1,
        ),
    )

    node_result = finish_node.await_args.args[1]
    assert node_result.status == "failed"
    assert node_result.has_successful_result is True


@pytest.mark.asyncio
async def test_ready_reconciliation_rotates_across_actions(monkeypatch) -> None:
    first = SimpleNamespace(id="node-instance-1", action_id="action-1", node_id="node-1")
    second = SimpleNamespace(id="node-instance-2", action_id="action-2", node_id="node-2")
    queries = []

    def find_nodes(query):
        queries.append(query)
        values = [second] if "_id" in query else [first, second]
        return _FindMany(values)

    schedule = AsyncMock(return_value=1)
    monkeypatch.setattr(ActionInstanceNodeModel, "find", staticmethod(find_nodes))
    monkeypatch.setattr(ActionInstanceService, "schedule_ready_nodes", schedule)
    ActionInstanceService._ready_reconcile_cursor = None

    try:
        assert await ActionInstanceService.reconcile_ready_nodes(limit=1) == 1
        assert await ActionInstanceService.reconcile_ready_nodes(limit=1) == 1
    finally:
        ActionInstanceService._ready_reconcile_cursor = None

    assert schedule.await_args_list[0].args == ("action-1", ["node-1"])
    assert schedule.await_args_list[1].args == ("action-2", ["node-2"])
    assert queries[1]["_id"] == {"$gt": "node-instance-1"}


@pytest.mark.asyncio
async def test_streaming_reference_is_ready_after_activation(monkeypatch) -> None:
    updates = await _run_readiness_case(
        monkeypatch,
        mode=ActionSchedulingModeEnum.STREAMING,
        data_type="reference",
        source_status=ActionInstanceNodeStatusEnum.RUNNING,
        activated=True,
    )

    assert updates[0]["$set"]["status"] == ActionInstanceNodeStatusEnum.QUEUED


@pytest.mark.asyncio
async def test_barrier_reference_still_waits_after_activation(monkeypatch) -> None:
    updates = await _run_readiness_case(
        monkeypatch,
        mode=ActionSchedulingModeEnum.BARRIER,
        data_type="reference",
        source_status=ActionInstanceNodeStatusEnum.RUNNING,
        activated=True,
    )

    assert updates == [
        {"$set": {"status": ActionInstanceNodeStatusEnum.UNREADY}}
    ]


@pytest.mark.asyncio
async def test_streaming_value_remains_blocked_until_delivered(monkeypatch) -> None:
    updates = await _run_readiness_case(
        monkeypatch,
        mode=ActionSchedulingModeEnum.STREAMING,
        data_type="value",
        source_status=ActionInstanceNodeStatusEnum.RUNNING,
    )

    assert updates == [
        {"$set": {"status": ActionInstanceNodeStatusEnum.UNREADY}}
    ]


@pytest.mark.asyncio
async def test_activated_reference_allows_consumer_after_source_failure(
    monkeypatch,
) -> None:
    updates = await _run_readiness_case(
        monkeypatch,
        mode=ActionSchedulingModeEnum.STREAMING,
        data_type="reference",
        source_status=ActionInstanceNodeStatusEnum.FAILED,
        activated=True,
        aborted=True,
    )

    assert updates[0]["$set"]["status"] == ActionInstanceNodeStatusEnum.QUEUED


@pytest.mark.asyncio
@pytest.mark.parametrize("data_type", ["reference", "value"])
async def test_unavailable_failed_input_cancels_consumer(
    monkeypatch,
    data_type: str,
) -> None:
    updates = await _run_readiness_case(
        monkeypatch,
        mode=ActionSchedulingModeEnum.STREAMING,
        data_type=data_type,
        source_status=ActionInstanceNodeStatusEnum.FAILED,
        aborted=True,
    )

    assert updates[0]["$set"]["status"] == ActionInstanceNodeStatusEnum.CANCELLED


@pytest.mark.asyncio
async def test_component_reference_waits_for_all_expected_producers(
    monkeypatch,
) -> None:
    edge = _edge("edge-1")
    binding = ReferenceQueueBinding(
        edge_id=edge.id,
        stream_id="stream-1",
        queue_name="queue-1",
        owner_action_id="action-1",
        source_node_id="source",
        source_port_id="out",
        target_node_id="target",
        target_port_id="in",
        producer_kind=ReferenceProducerKindEnum.COMPONENT,
        expected_producer_ids=["run-1", "run-2"],
    )
    source = SimpleNamespace(
        id="source-instance",
        node_id="source",
        reference_queue_bindings={edge.id: binding},
    )
    action = SimpleNamespace(
        id="action-1",
        status=ActionFlowStatusEnum.RUNNING,
        execution_plan_snapshot=SimpleNamespace(edges=[edge]),
    )
    target_updates = []
    schedule = AsyncMock()
    producer_snapshots = [
        [SimpleNamespace(id="run-1", started_at=datetime.now())],
        [
            SimpleNamespace(id="run-1", started_at=datetime.now()),
            SimpleNamespace(id="run-2", started_at=datetime.now()),
        ],
    ]

    monkeypatch.setattr(
        ComponentRunModel,
        "find",
        staticmethod(lambda _query: _FindMany(producer_snapshots.pop(0))),
    )
    monkeypatch.setattr(
        ActionInstanceNodeModel,
        "find_one",
        staticmethod(
            lambda _query: _FindOne(modified_count=1, updates=target_updates)
        ),
    )
    monkeypatch.setattr(ActionInstanceService, "schedule_ready_nodes", schedule)

    await ActionInstanceService._mark_reference_outputs_activated(action, source)
    assert target_updates == []
    schedule.assert_not_awaited()

    await ActionInstanceService._mark_reference_outputs_activated(action, source)
    assert target_updates == [
        {
            "$addToSet": {
                "activated_input_edge_ids": {"$each": [edge.id]},
            }
        }
    ]
    schedule.assert_awaited_once_with(action.id, ["target"])


@pytest.mark.asyncio
async def test_successful_result_only_counts_business_terminal_nodes(
    monkeypatch,
) -> None:
    action = SimpleNamespace(
        id="action-1",
        execution_plan_snapshot=SimpleNamespace(
            nodes=[
                SimpleNamespace(
                    id="intermediate",
                    effective_out_degree=1,
                    extension={},
                    extension_spec=None,
                ),
                SimpleNamespace(
                    id="terminal",
                    effective_out_degree=0,
                    extension={},
                    extension_spec=None,
                ),
                SimpleNamespace(
                    id="debug-terminal",
                    effective_out_degree=0,
                    extension={},
                    extension_spec=SimpleNamespace(
                        execution_policy="debug.observer"
                    ),
                ),
                SimpleNamespace(
                    id="boundary-terminal",
                    effective_out_degree=0,
                    extension={"boundary": "output"},
                    extension_spec=None,
                ),
            ]
        ),
    )
    node_queries = []

    def find_nodes(query):
        node_queries.append(query)
        return _FindMany(count=1)

    monkeypatch.setattr(
        ActionInstanceNodeModel,
        "find",
        staticmethod(find_nodes),
    )
    monkeypatch.setattr(
        ReferenceBridgeModel,
        "find",
        staticmethod(lambda _query: _FindMany(count=0)),
    )

    assert await ActionInstanceService._has_successful_terminal_result(action)
    assert node_queries == [
        {
            "action_id": action.id,
            "node_id": {"$in": ["terminal"]},
            "has_successful_result": True,
        }
    ]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("mode", "timeout_count", "has_terminal_result", "expected"),
    [
        (
            ActionSchedulingModeEnum.STREAMING,
            0,
            True,
            ActionFlowStatusEnum.PARTIALLY_COMPLETED,
        ),
        (
            ActionSchedulingModeEnum.STREAMING,
            0,
            False,
            ActionFlowStatusEnum.FAILED,
        ),
        (
            ActionSchedulingModeEnum.BARRIER,
            0,
            True,
            ActionFlowStatusEnum.FAILED,
        ),
        (
            ActionSchedulingModeEnum.STREAMING,
            1,
            True,
            ActionFlowStatusEnum.TIMEOUT,
        ),
    ],
)
async def test_finish_action_partial_result_and_timeout_precedence(
    monkeypatch,
    mode: ActionSchedulingModeEnum,
    timeout_count: int,
    has_terminal_result: bool,
    expected: ActionFlowStatusEnum,
) -> None:
    action = SimpleNamespace(
        id="action-1",
        status=ActionFlowStatusEnum.RUNNING,
        start_at=datetime.now(),
        paused_duration=0,
        reference_finalization_state="none",
        execution_plan_snapshot=SimpleNamespace(
            plan_schema_version=3,
            scheduling_mode=mode,
            nodes=[SimpleNamespace(id="terminal")],
        ),
    )
    action_updates = []

    monkeypatch.setattr(
        ActionInstanceModel,
        "find_one",
        staticmethod(
            lambda query: (
                _FindOne(action)
                if "status" not in query
                else _FindOne(modified_count=1, updates=action_updates)
            )
        ),
    )

    def find_nodes(query):
        status = query.get("status")
        if status == ActionInstanceNodeStatusEnum.TIMEOUT:
            return _FindMany(count=timeout_count)
        if isinstance(status, dict) and status.get("$in") == [
            ActionInstanceNodeStatusEnum.FAILED,
            ActionInstanceNodeStatusEnum.CANCELLED,
        ]:
            return _FindMany(count=1)
        return _FindMany(count=1 + timeout_count)

    monkeypatch.setattr(
        ActionInstanceNodeModel,
        "find",
        staticmethod(find_nodes),
    )
    terminal_result = AsyncMock(return_value=has_terminal_result)
    monkeypatch.setattr(
        ActionInstanceService,
        "_has_successful_terminal_result",
        terminal_result,
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
        "cancel_reference_bridges",
        AsyncMock(return_value=0),
    )
    monkeypatch.setattr(
        ActionInstanceService,
        "cleanup_action_queues",
        AsyncMock(),
    )

    assert await ActionInstanceService.finish_action(action.id) is True
    assert action_updates[0]["$set"]["status"] == expected
    if mode == ActionSchedulingModeEnum.STREAMING and timeout_count == 0:
        terminal_result.assert_awaited_once_with(action)
    else:
        terminal_result.assert_not_awaited()
