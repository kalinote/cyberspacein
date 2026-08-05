import asyncio
from datetime import datetime, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.db import rabbitmq as rabbit_mod
from app.models.action.action import ActionInstanceModel, ActionInstanceNodeModel
from app.schemas.action.execution import (
    NativeNodeExtensionSpec,
    NodeExecutionContext,
    NodeExecutionSpec,
)
from app.schemas.action.node import ActionNode
from app.schemas.action.sdk import SDKResultRequest
from app.schemas.constants import (
    ActionExecutionDriverEnum,
    ActionConfigIOTypeEnum,
    ActionFlowStatusEnum,
    ActionInstanceNodeStatusEnum,
    ActionInvocationModeEnum,
    ActionNodeKindEnum,
    ActionNodeTypeEnum,
    ComponentRunStatusEnum,
)
from app.schemas.action.reference import (
    ReferenceProducerKindEnum,
    ReferenceQueueBinding,
)
from app.service.action import service as action_service
from app.service.action import ActionInstanceService
from app.service.debug_output_runtime import DebugOutputRuntimeService
from app.service.node_executors import component as component_executor
from app.service.node_executors.component import ComponentNodeExecutor


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
    def __init__(self, values):
        self.values = values

    def limit(self, _limit):
        return self

    async def to_list(self):
        return self.values


async def _node_definition(_definition_id):
    return SimpleNamespace(id="definition-1")


def _allow_reference_abort_publish(monkeypatch):
    """为 Reference ABORT 测试提供成功的发布租约。"""
    claim = AsyncMock(return_value="publish-token")
    renew = AsyncMock(return_value=True)
    release = AsyncMock()
    monkeypatch.setattr(
        ActionInstanceService,
        "_claim_reference_abort_publish",
        claim,
    )
    monkeypatch.setattr(
        ActionInstanceService,
        "_renew_reference_abort_publish",
        renew,
    )
    monkeypatch.setattr(
        ActionInstanceService,
        "_release_reference_abort_publish",
        release,
    )
    return claim, renew, release


def _mock_empty_reference_abort_publish_state(monkeypatch):
    """模拟 Action 文档中不存在内部 ABORT 发布栅栏。"""
    collection = SimpleNamespace(
        find_one=AsyncMock(return_value={}),
        update_one=AsyncMock(
            return_value=SimpleNamespace(modified_count=0)
        ),
    )
    monkeypatch.setattr(
        ActionInstanceModel,
        "get_motor_collection",
        staticmethod(lambda: collection),
    )
    return collection


def test_action_node_uses_default_component_command():
    node = ActionNode(
        name="分析节点",
        description="测试默认运行命令",
        type=ActionNodeTypeEnum.PROCESSOR,
        version="1.0.0",
        handles=[],
        inputs=[],
        related_components=[],
    )

    assert node.command == "csi-component"
    assert node.command_args == ["main:run"]


def test_action_node_empty_command_uses_shared_default():
    node = ActionNode(
        name="分析节点",
        description="测试空命令兼容",
        type=ActionNodeTypeEnum.PROCESSOR,
        version="1.0.0",
        handles=[],
        inputs=[],
        related_components=[],
        command="   ",
        command_args=["should-be-replaced"],
    )

    assert node.command == "csi-component"
    assert node.command_args == ["main:run"]


@pytest.mark.parametrize(
    ("command", "command_args", "message"),
    [
        ("python;whoami", ["worker.py"], "组件命令"),
        ("python", ["worker.py", "--component-run-id=fake"], "运行时保留"),
        ("python", ["worker.py && whoami"], "不安全字符"),
    ],
)
def test_unsafe_component_command_is_rejected(
    command: str,
    command_args: list[str],
    message: str,
):
    with pytest.raises(ValueError, match=message):
        ActionNode(
            name="组件节点",
            description="测试自定义命令安全校验",
            type=ActionNodeTypeEnum.PROCESSOR,
            version="1.0.0",
            handles=[],
            inputs=[],
            related_components=[],
            command=command,
            command_args=command_args,
        )


@pytest.mark.asyncio
async def test_run_node_dispatch_claim_accepts_pending_node(monkeypatch):
    node = SimpleNamespace(
        id="node-instance-1",
        node_id="target-node",
        definition_id="definition-1",
        definition_snapshot={},
        delivered_dependencies=[],
    )
    find_one_queries = []

    def find_one(query):
        find_one_queries.append(query)
        if len(find_one_queries) == 1:
            return _FindOne(node)
        return _FindOne(modified_count=0)

    monkeypatch.setattr(ActionInstanceNodeModel, "find_one", staticmethod(find_one))
    monkeypatch.setattr(
        ActionInstanceNodeModel,
        "find",
        staticmethod(lambda _query: _FindMany([])),
    )
    monkeypatch.setattr(
        ActionInstanceService,
        "get_instance_node_definition",
        staticmethod(lambda _node: _node_definition("definition-1")),
    )
    monkeypatch.setattr(
        ActionInstanceModel,
        "find_one",
        AsyncMock(
                return_value=SimpleNamespace(
                    status=action_service.ActionFlowStatusEnum.RUNNING,
                    execution_plan_snapshot=SimpleNamespace(
                        nodes=[
                            SimpleNamespace(
                                id="target-node",
                                extension_spec=None,
                                effective_in_degree=0,
                            )
                        ]
                    ),
                )
        ),
    )

    async def no_previous_nodes(_action_id, _node_id):
        return []

    monkeypatch.setattr(
        ActionInstanceService,
        "find_all_previous_nodes",
        staticmethod(no_previous_nodes),
    )

    assert await ActionInstanceService.run_node("node-instance-1", "action-1") is False
    claim_statuses = find_one_queries[1]["status"]["$in"]
    assert ActionInstanceNodeStatusEnum.PENDING in claim_statuses


@pytest.mark.asyncio
async def test_run_node_can_move_pending_join_node_to_unready(monkeypatch):
    node = SimpleNamespace(
        id="node-instance-1",
        node_id="target-node",
        definition_id="definition-1",
        definition_snapshot={},
        delivered_dependencies=[],
    )
    previous = SimpleNamespace(
        id="previous-instance",
        node_id="previous-node",
        status=ActionInstanceNodeStatusEnum.RUNNING,
    )
    find_one_queries = []
    updates = []

    def find_one(query):
        find_one_queries.append(query)
        if len(find_one_queries) == 1:
            return _FindOne(node)
        return _FindOne(modified_count=1, updates=updates)

    monkeypatch.setattr(ActionInstanceNodeModel, "find_one", staticmethod(find_one))
    monkeypatch.setattr(
        ActionInstanceNodeModel,
        "find",
        staticmethod(lambda _query: _FindMany([previous])),
    )
    monkeypatch.setattr(
        ActionInstanceService,
        "get_instance_node_definition",
        staticmethod(lambda _node: _node_definition("definition-1")),
    )
    monkeypatch.setattr(
        ActionInstanceModel,
        "find_one",
        AsyncMock(
                return_value=SimpleNamespace(
                    status=action_service.ActionFlowStatusEnum.RUNNING,
                    execution_plan_snapshot=SimpleNamespace(
                        nodes=[
                            SimpleNamespace(
                                id="target-node",
                                extension_spec=None,
                                effective_in_degree=1,
                            )
                        ]
                    ),
                )
        ),
    )

    async def previous_nodes(_action_id, _node_id):
        return ["previous-node"]

    monkeypatch.setattr(
        ActionInstanceService,
        "find_all_previous_nodes",
        staticmethod(previous_nodes),
    )

    assert await ActionInstanceService.run_node("node-instance-1", "action-1") is False
    waiting_statuses = find_one_queries[1]["status"]["$in"]
    assert ActionInstanceNodeStatusEnum.PENDING in waiting_statuses
    assert updates == [
        {"$set": {"status": ActionInstanceNodeStatusEnum.UNREADY}}
    ]


@pytest.mark.asyncio
async def test_edge_v1_counts_multiple_edges_from_same_upstream(monkeypatch):
    node = SimpleNamespace(
        id="target-instance",
        node_id="target-node",
        definition_id="definition-1",
        definition_snapshot={},
        delivered_dependencies=["source-node"],
        delivered_input_edge_ids=["edge-left", "edge-right"],
        aborted_input_edge_ids=[],
    )
    previous = SimpleNamespace(
        node_id="source-node",
        status=ActionInstanceNodeStatusEnum.COMPLETED,
    )
    find_one_queries = []

    def find_one(query):
        find_one_queries.append(query)
        if len(find_one_queries) == 1:
            return _FindOne(node)
        return _FindOne(modified_count=0)

    monkeypatch.setattr(
        ActionInstanceNodeModel,
        "find_one",
        staticmethod(find_one),
    )
    monkeypatch.setattr(
        ActionInstanceNodeModel,
        "find",
        staticmethod(lambda _query: _FindMany([previous])),
    )
    monkeypatch.setattr(
        ActionInstanceService,
        "get_instance_node_definition",
        staticmethod(lambda _node: _node_definition("definition-1")),
    )
    monkeypatch.setattr(
        ActionInstanceService,
        "find_all_previous_nodes",
        AsyncMock(return_value=["source-node"]),
    )
    monkeypatch.setattr(
        ActionInstanceModel,
        "find_one",
        AsyncMock(
            return_value=SimpleNamespace(
                status=ActionFlowStatusEnum.RUNNING,
                execution_plan_snapshot=SimpleNamespace(
                    extension={"scheduler": {"readiness": "edge-v1"}},
                    nodes=[
                        SimpleNamespace(
                            id="target-node",
                            extension_spec=None,
                            effective_in_degree=2,
                        )
                    ],
                    edges=[
                        SimpleNamespace(id="edge-left", target="target-node"),
                        SimpleNamespace(id="edge-right", target="target-node"),
                    ],
                ),
            )
        ),
    )

    assert await ActionInstanceService.run_node(
        node.id,
        "action-1",
    ) is False
    assert len(find_one_queries) == 2
    assert ActionInstanceNodeStatusEnum.PENDING in (
        find_one_queries[1]["status"]["$in"]
    )


@pytest.mark.asyncio
async def test_run_node_dispatches_custom_command_and_keeps_bootstrap_value(monkeypatch):
    node = SimpleNamespace(
        id="node-instance-1",
        node_id="start-node",
        definition_id="definition-1",
    )
    node_definition = SimpleNamespace(
        command="python",
        command_args=["worker.py"],
        related_components=["component-1"],
        component_timeouts={"component-1": 30},
    )
    action = SimpleNamespace(
        id="action-1",
        schedule_priority=5,
    )
    monkeypatch.setattr(
        component_executor.ActionInstanceModel,
        "find_one",
        AsyncMock(return_value=action),
    )
    monkeypatch.setattr(
        component_executor.ActionInstanceNodeModel,
        "find_one",
        AsyncMock(return_value=node),
    )
    component_run = SimpleNamespace(
        id="component-run-1",
        component_id="component-1",
        status=ComponentRunStatusEnum.CREATED,
        insert=AsyncMock(),
    )
    component_run_factory = MagicMock(return_value=component_run)
    component_run_factory.find = MagicMock(return_value=_FindMany([]))
    monkeypatch.setattr(
        component_executor,
        "ComponentRunModel",
        component_run_factory,
    )
    monkeypatch.setattr(
        component_executor,
        "issue_component_bootstrap",
        AsyncMock(return_value="-bootstrap"),
    )
    dispatch = AsyncMock(return_value=True)
    monkeypatch.setattr(component_executor, "dispatch_component_run", dispatch)

    result = await ComponentNodeExecutor(
        AsyncMock(return_value=node_definition)
    ).start(
        NodeExecutionContext(
            action_id=action.id,
            node_instance_id=node.id,
            node_id=node.node_id,
        ),
        NodeExecutionSpec(
            driver=ActionExecutionDriverEnum.COMPONENT,
            handler="component.run",
        ),
    )

    assert result.state == "running"
    assert component_run_factory.call_args.kwargs["timeout_seconds"] == 30
    assert dispatch.await_args.args[1] == "python"
    command_args = dispatch.await_args.args[2]
    assert "worker.py" in command_args
    assert "--component-bootstrap=-bootstrap" in command_args
    assert "--component-bootstrap" not in command_args


@pytest.mark.asyncio
async def test_subflow_inherits_parent_debug_mode(monkeypatch) -> None:
    parent = SimpleNamespace(
        id="parent-action",
        nesting_depth=0,
        root_action_id="parent-action",
        initiator_user_id="user-1",
        debug=True,
        execution_plan_snapshot=SimpleNamespace(edges=[]),
    )
    parent_node = SimpleNamespace(
        id="parent-node-instance",
        node_id="subflow-node",
        inputs={},
        instance_config={},
        reference_queue_bindings={},
    )
    child = SimpleNamespace(
        execution_plan_snapshot=SimpleNamespace(
            nodes=[],
            edges=[],
            public_interface_snapshot={},
        ),
        invocation_reference_outputs={},
        reference_finalization_state="none",
        save=AsyncMock(),
    )
    monkeypatch.setattr(
        ActionInstanceModel,
        "find_one",
        AsyncMock(side_effect=[parent, child]),
    )
    monkeypatch.setattr(
        ActionInstanceNodeModel,
        "find_one",
        AsyncMock(return_value=parent_node),
    )
    monkeypatch.setattr(
        ActionInstanceNodeModel,
        "find",
        staticmethod(lambda _query: _FindMany([])),
    )
    monkeypatch.setattr(
        ActionInstanceService,
        "get_instance_node_definition",
        AsyncMock(return_value=SimpleNamespace(handles=[])),
    )
    monkeypatch.setattr(
        action_service.ActionBlueprintRevisionModel,
        "find_one",
        AsyncMock(
            return_value=SimpleNamespace(
                interface_snapshot=SimpleNamespace(inputs=[])
            )
        ),
    )
    monkeypatch.setattr(
        action_service.ActionNodeExecutionModel,
        "find_one",
        AsyncMock(return_value=SimpleNamespace(id="execution-1")),
    )
    init = AsyncMock(return_value=(True, "child-action"))
    start = AsyncMock()
    monkeypatch.setattr(ActionInstanceService, "init", init)
    monkeypatch.setattr(ActionInstanceService, "start", start)

    child_action_id = await ActionInstanceService._start_subflow_attempt(
        NodeExecutionContext(
            action_id=parent.id,
            node_instance_id=parent_node.id,
            node_id=parent_node.node_id,
        ),
        NodeExecutionSpec(
            driver=ActionExecutionDriverEnum.SUBFLOW,
            handler="subflow.invoke",
            config={
                "blueprint_id": "child-blueprint",
                "revision_id": "child-revision",
            },
        ),
    )

    assert child_action_id == "child-action"
    assert init.await_args.kwargs["debug"] is True
    start.assert_awaited_once_with("child-action")


def test_reference_queue_bindings_are_isolated_by_edge():
    graph = SimpleNamespace(
        nodes=[
            SimpleNamespace(
                id="source",
                data=SimpleNamespace(definition_id="source-definition"),
            ),
            SimpleNamespace(
                id="target",
                data=SimpleNamespace(definition_id="target-definition"),
            ),
        ]
    )
    execution_plan = SimpleNamespace(
        edges=[
            SimpleNamespace(
                id="edge-a",
                source="source",
                source_port_id="out-a",
                target="target",
                target_port_id="in-a",
                data_type="reference",
                reference_protocol="eos-v1",
            ),
            SimpleNamespace(
                id="edge-b",
                source="source",
                source_port_id="out-b",
                target="target",
                target_port_id="in-b",
                data_type="reference",
                reference_protocol="eos-v1",
            ),
        ]
    )
    definitions = {
        "source-definition": SimpleNamespace(
            builtin_key=None,
            node_kind=ActionNodeKindEnum.ORDINARY,
            related_components=["component-a", "component-b"],
        ),
        "target-definition": SimpleNamespace(
            builtin_key=None,
            node_kind=ActionNodeKindEnum.ORDINARY,
            related_components=[],
        ),
    }

    bindings = ActionInstanceService._build_reference_queue_bindings(
        "action-1",
        execution_plan,
        graph,
        definitions,
    )["source"]

    assert set(bindings) == {"edge-a", "edge-b"}
    assert bindings["edge-a"].queue_name != bindings["edge-b"].queue_name
    assert bindings["edge-a"].stream_id != bindings["edge-b"].stream_id
    assert bindings["edge-a"].owner_action_id == "action-1"
    assert bindings["edge-a"].producer_kind == ReferenceProducerKindEnum.COMPONENT
    assert len(bindings["edge-a"].expected_producer_ids) == 2


@pytest.mark.asyncio
async def test_native_reference_output_publishes_eos_once(monkeypatch):
    binding = ReferenceQueueBinding(
        edge_id="edge-a",
        stream_id="stream-a",
        queue_name="queue-a",
        owner_action_id="action-1",
        source_node_id="source",
        source_port_id="out",
        target_node_id="target",
        target_port_id="in",
        producer_kind=ReferenceProducerKindEnum.NATIVE,
        expected_producer_ids=["native-run"],
    )
    node_instance = SimpleNamespace(
        id="node-instance-1",
        reference_queue_bindings={"edge-a": binding},
        save=AsyncMock(),
    )
    publish = AsyncMock()
    monkeypatch.setattr(action_service, "publish_reference_control", publish)

    assert await ActionInstanceService._close_native_reference_outputs(
        node_instance,
        status="eos",
    )
    assert await ActionInstanceService._close_native_reference_outputs(
        node_instance,
        status="eos",
    )

    publish.assert_awaited_once_with(
        queue_names=["queue-a"],
        stream_id="stream-a",
        producer_id="native-run",
        action_id="action-1",
        status="eos",
        reason=None,
    )
    assert binding.control_status == "eos"


@pytest.mark.asyncio
async def test_retry_open_reference_abort_only_closes_after_all_confirms(
    monkeypatch,
) -> None:
    binding = ReferenceQueueBinding(
        edge_id="edge-a",
        stream_id="stream-a",
        queue_name="queue-a",
        owner_action_id="action-1",
        source_node_id="source",
        source_port_id="out",
        target_node_id="target",
        target_port_id="in",
        expected_producer_ids=["producer-a", "producer-b"],
    )
    node_instance = SimpleNamespace(
        id="source-instance",
        error_message="生产者失败",
        reference_queue_bindings={"edge-a": binding},
        save=AsyncMock(),
    )
    monkeypatch.setattr(
        ActionInstanceModel,
        "find",
        staticmethod(
            lambda _query: _FindMany([SimpleNamespace(id="action-1")])
        ),
    )
    monkeypatch.setattr(
        ActionInstanceNodeModel,
        "find",
        staticmethod(lambda _query: _FindMany([node_instance])),
    )
    publish = AsyncMock(side_effect=[None, RuntimeError("confirm failed")])
    monkeypatch.setattr(action_service, "publish_reference_control", publish)
    _, renew, release = _allow_reference_abort_publish(monkeypatch)

    assert await ActionInstanceService.retry_open_reference_aborts() == 0
    assert binding.control_status == "open"
    node_instance.save.assert_not_awaited()

    publish.reset_mock(side_effect=True)
    publish.side_effect = None
    assert await ActionInstanceService.retry_open_reference_aborts() == 1
    assert binding.control_status == "abort"
    node_instance.save.assert_awaited_once()
    assert renew.await_count == 4
    assert release.await_count == 2
    assert [call.kwargs["producer_id"] for call in publish.await_args_list] == [
        "producer-a",
        "producer-b",
    ]


@pytest.mark.asyncio
async def test_retry_abort_stops_remaining_producers_after_action_closes(
    monkeypatch,
) -> None:
    binding = ReferenceQueueBinding(
        edge_id="edge-a",
        stream_id="stream-a",
        queue_name="queue-a",
        owner_action_id="action-1",
        source_node_id="source",
        source_port_id="out",
        target_node_id="target",
        target_port_id="in",
        expected_producer_ids=["producer-a", "producer-b"],
    )
    node = SimpleNamespace(
        id="source-instance",
        action_id="action-1",
        error_message="生产者失败",
        reference_queue_bindings={binding.edge_id: binding},
        save=AsyncMock(),
    )
    token = "publish-token"
    raw_action = {
        "_id": "action-1",
        "status": ActionFlowStatusEnum.RUNNING.value,
        action_service.REFERENCE_ABORT_PUBLISH_CLOSED_FIELD: False,
        action_service.REFERENCE_ABORT_PUBLISH_TOKEN_FIELD: token,
        action_service.REFERENCE_ABORT_PUBLISH_EXPIRES_FIELD: (
            datetime.now() + timedelta(seconds=30)
        ),
    }

    def matches(query):
        for field, expected in query.items():
            actual = raw_action.get(field)
            if not isinstance(expected, dict):
                if actual != expected:
                    return False
                continue
            if "$in" in expected and actual not in expected["$in"]:
                return False
            if "$ne" in expected and actual == expected["$ne"]:
                return False
            if "$gt" in expected and (
                actual is None or actual <= expected["$gt"]
            ):
                return False
        return True

    async def update_one(query, update):
        if not matches(query):
            return SimpleNamespace(modified_count=0)
        raw_action.update(update.get("$set", {}))
        return SimpleNamespace(modified_count=1)

    collection = SimpleNamespace(update_one=update_one)
    monkeypatch.setattr(
        ActionInstanceModel,
        "get_motor_collection",
        staticmethod(lambda: collection),
    )
    monkeypatch.setattr(
        ActionInstanceModel,
        "find",
        staticmethod(
            lambda _query: _FindMany([SimpleNamespace(id="action-1")])
        ),
    )
    monkeypatch.setattr(
        ActionInstanceNodeModel,
        "find",
        staticmethod(lambda _query: _FindMany([node])),
    )
    monkeypatch.setattr(
        ActionInstanceService,
        "_claim_reference_abort_publish",
        AsyncMock(return_value=token),
    )
    release = AsyncMock()
    monkeypatch.setattr(
        ActionInstanceService,
        "_release_reference_abort_publish",
        release,
    )
    published_producers = []

    async def publish_control(**kwargs):
        published_producers.append(kwargs["producer_id"])
        raw_action["status"] = ActionFlowStatusEnum.TIMEOUT.value
        raw_action[action_service.REFERENCE_ABORT_PUBLISH_CLOSED_FIELD] = True

    monkeypatch.setattr(
        action_service,
        "publish_reference_control",
        publish_control,
    )

    assert await ActionInstanceService.retry_open_reference_aborts() == 0

    assert published_producers == ["producer-a"]
    assert binding.control_status == "open"
    node.save.assert_not_awaited()
    release.assert_awaited_once_with("action-1", token)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "status",
    [ActionFlowStatusEnum.RUNNING, ActionFlowStatusEnum.PAUSED],
)
async def test_retry_open_reference_abort_scans_active_actions(
    monkeypatch,
    status,
) -> None:
    binding = ReferenceQueueBinding(
        edge_id="edge-a",
        stream_id="stream-a",
        queue_name="queue-a",
        owner_action_id="action-1",
        source_node_id="source",
        source_port_id="out",
        target_node_id="target",
        target_port_id="in",
    )
    node_instance = SimpleNamespace(
        id="source-instance",
        error_message="生产者失败",
        reference_queue_bindings={"edge-a": binding},
        save=AsyncMock(),
    )
    action_queries = []
    node_queries = []

    def find_actions(query):
        action_queries.append(query)
        statuses = query["status"]["$in"]
        return _FindMany(
            [SimpleNamespace(id="action-1")] if status in statuses else []
        )

    def find_nodes(query):
        node_queries.append(query)
        return _FindMany([node_instance])

    monkeypatch.setattr(
        ActionInstanceModel,
        "find",
        staticmethod(find_actions),
    )
    monkeypatch.setattr(
        ActionInstanceNodeModel,
        "find",
        staticmethod(find_nodes),
    )
    publish = AsyncMock()
    monkeypatch.setattr(action_service, "publish_reference_control", publish)
    claim, renew, release = _allow_reference_abort_publish(monkeypatch)

    assert await ActionInstanceService.retry_open_reference_aborts() == 1

    assert action_queries == [
        {
            "status": {
                "$in": [
                    ActionFlowStatusEnum.RUNNING,
                    ActionFlowStatusEnum.PAUSED,
                ]
            }
        }
    ]
    assert node_queries[0]["action_id"] == {"$in": ["action-1"]}
    publish.assert_awaited_once()
    claim.assert_awaited_once_with("action-1")
    renew.assert_awaited_once_with("action-1", "publish-token")
    release.assert_awaited_once_with("action-1", "publish-token")
    assert binding.control_status == "abort"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "status",
    [
        ActionFlowStatusEnum.COMPLETED,
        ActionFlowStatusEnum.PARTIALLY_COMPLETED,
        ActionFlowStatusEnum.FAILED,
        ActionFlowStatusEnum.CANCELLED,
        ActionFlowStatusEnum.TIMEOUT,
        ActionFlowStatusEnum.STOPPED,
    ],
)
async def test_retry_open_reference_abort_skips_terminal_actions(
    monkeypatch,
    status,
) -> None:
    node_find = MagicMock(return_value=_FindMany([]))

    def find_actions(query):
        statuses = query["status"]["$in"]
        return _FindMany(
            [SimpleNamespace(id="action-1")] if status in statuses else []
        )

    monkeypatch.setattr(
        ActionInstanceModel,
        "find",
        staticmethod(find_actions),
    )
    monkeypatch.setattr(
        ActionInstanceNodeModel,
        "find",
        staticmethod(node_find),
    )
    publish = AsyncMock()
    monkeypatch.setattr(action_service, "publish_reference_control", publish)
    claim, _, release = _allow_reference_abort_publish(monkeypatch)

    assert await ActionInstanceService.retry_open_reference_aborts() == 0
    node_find.assert_not_called()
    publish.assert_not_awaited()
    claim.assert_not_awaited()
    release.assert_not_awaited()


@pytest.mark.asyncio
async def test_retry_reference_abort_does_not_publish_when_claim_is_lost(
    monkeypatch,
) -> None:
    binding = ReferenceQueueBinding(
        edge_id="edge-a",
        stream_id="stream-a",
        queue_name="queue-a",
        owner_action_id="action-1",
        source_node_id="source",
        source_port_id="out",
        target_node_id="target",
        target_port_id="in",
    )
    node = SimpleNamespace(
        id="source-instance",
        action_id="action-1",
        error_message="生产者失败",
        reference_queue_bindings={"edge-a": binding},
        save=AsyncMock(),
    )
    terminal_action = SimpleNamespace(
        id="action-1",
        status=ActionFlowStatusEnum.TIMEOUT,
    )
    monkeypatch.setattr(
        ActionInstanceModel,
        "find",
        staticmethod(
            lambda _query: _FindMany([terminal_action])
        ),
    )
    collection = SimpleNamespace(
        update_one=AsyncMock(
            return_value=SimpleNamespace(modified_count=0)
        )
    )
    monkeypatch.setattr(
        ActionInstanceModel,
        "get_motor_collection",
        staticmethod(lambda: collection),
    )
    monkeypatch.setattr(
        ActionInstanceNodeModel,
        "find",
        staticmethod(lambda _query: _FindMany([node])),
    )
    renew = AsyncMock(return_value=True)
    release = AsyncMock()
    monkeypatch.setattr(
        ActionInstanceService,
        "_renew_reference_abort_publish",
        renew,
    )
    monkeypatch.setattr(
        ActionInstanceService,
        "_release_reference_abort_publish",
        release,
    )
    publish = AsyncMock()
    monkeypatch.setattr(action_service, "publish_reference_control", publish)

    assert await ActionInstanceService.retry_open_reference_aborts() == 0

    claim_query = collection.update_one.await_args.args[0]
    assert claim_query["_id"] == terminal_action.id
    assert claim_query["status"] == {
        "$in": [
            ActionFlowStatusEnum.RUNNING.value,
            ActionFlowStatusEnum.PAUSED.value,
        ]
    }
    assert claim_query[action_service.REFERENCE_ABORT_PUBLISH_CLOSED_FIELD] == {
        "$ne": True
    }
    renew.assert_not_awaited()
    publish.assert_not_awaited()
    release.assert_not_awaited()
    assert binding.control_status == "open"
    node.save.assert_not_awaited()


@pytest.mark.asyncio
async def test_missing_value_output_aborts_edge_and_notifies_debug_runtime(
    monkeypatch,
) -> None:
    source = SimpleNamespace(
        id="source-instance",
        action_id="action-1",
        node_id="source",
        status=ActionInstanceNodeStatusEnum.RUNNING,
        start_at=None,
        outputs={},
        current_execution_id=None,
        progress=0,
        reference_queue_bindings={},
        save=AsyncMock(),
    )
    target = SimpleNamespace(
        id="target-instance",
        node_id="target",
        inputs={},
    )
    edge = SimpleNamespace(
        id="edge-value",
        source="source",
        source_port_id="value-out",
        target="target",
        target_port_id="debug-in",
    )
    action = SimpleNamespace(
        id="action-1",
        status=ActionFlowStatusEnum.PAUSED,
        execution_plan_snapshot=SimpleNamespace(
            public_interface_snapshot={"outputs": []},
            edges=[edge],
        ),
        finished_nodes_instance=[],
        invocation_outputs={},
        save=AsyncMock(),
    )
    source_definition = SimpleNamespace(handles=[])
    target_definition = SimpleNamespace(
        builtin_key="debug.output",
        extension=SimpleNamespace(
            config={"compiler": {"allow_multiple_inputs": True}}
        ),
    )
    target_updates = []
    node_find_calls = 0

    def find_node(_query):
        nonlocal node_find_calls
        node_find_calls += 1
        if node_find_calls == 1:
            return _FindOne(source)
        if node_find_calls == 2:
            return _FindOne(target)
        return _FindOne(target, updates=target_updates)

    monkeypatch.setattr(
        ActionInstanceNodeModel,
        "find_one",
        staticmethod(find_node),
    )
    monkeypatch.setattr(
        ActionInstanceModel,
        "find_one",
        AsyncMock(return_value=action),
    )
    monkeypatch.setattr(
        ActionInstanceService,
        "get_instance_node_definition",
        AsyncMock(side_effect=[source_definition, target_definition]),
    )
    monkeypatch.setattr(
        ActionInstanceService,
        "find_next_node",
        AsyncMock(return_value={target.id: [("value-out", "debug-in")]}),
    )
    monkeypatch.setattr(
        ActionInstanceService,
        "resolve_node_handle_definition",
        AsyncMock(
            side_effect=[
                (
                    SimpleNamespace(id="debug-in"),
                    SimpleNamespace(handle_name="data_in"),
                ),
                (
                    SimpleNamespace(id="value-out"),
                    SimpleNamespace(type=ActionConfigIOTypeEnum.VALUE),
                ),
            ]
        ),
    )
    abort_input = AsyncMock()
    monkeypatch.setattr(
        DebugOutputRuntimeService,
        "abort_input_for_node",
        abort_input,
    )

    assert await ActionInstanceService.finish_node(
        source.id,
        SDKResultRequest(
            result_id="result-1",
            attempt=1,
            status="success",
            outputs={},
        ),
    )

    assert target_updates == [
        [
            {
                "$set": {
                    "delivered_dependencies": {
                        "$setUnion": [
                            {"$ifNull": ["$delivered_dependencies", []]},
                            {"$literal": [source.node_id]},
                        ]
                    },
                    "aborted_input_edge_ids": {
                        "$setUnion": [
                            {"$ifNull": ["$aborted_input_edge_ids", []]},
                            {"$literal": [edge.id]},
                        ]
                    },
                }
            }
        ]
    ]
    abort_input.assert_awaited_once_with(
        action.id,
        target.id,
        edge.id,
        "上游节点已完成，但没有产生该 Value 输出",
    )


@pytest.mark.asyncio
async def test_cascade_cancel_aborts_intermediate_reference_producer(
    monkeypatch,
) -> None:
    binding = ReferenceQueueBinding(
        edge_id="edge-middle-target",
        stream_id="stream-middle-target",
        queue_name="queue-middle-target",
        owner_action_id="action-1",
        source_node_id="middle",
        source_port_id="reference-out",
        target_node_id="target",
        target_port_id="reference-in",
        expected_producer_ids=["middle-producer"],
    )
    middle = SimpleNamespace(
        id="middle-instance",
        node_id="middle",
        status=ActionInstanceNodeStatusEnum.UNREADY,
        finished_at=None,
        extension_spec_snapshot=None,
        reference_queue_bindings={binding.edge_id: binding},
        save=AsyncMock(),
    )
    target = SimpleNamespace(
        id="target-instance",
        node_id="target",
        status=ActionInstanceNodeStatusEnum.RUNNING,
        extension_spec_snapshot=SimpleNamespace(
            execution_policy="debug.observer"
        ),
    )
    edge = SimpleNamespace(
        id=binding.edge_id,
        source=middle.node_id,
        target=target.node_id,
        data_type="reference",
    )
    action = SimpleNamespace(
        id="action-1",
        execution_plan_snapshot=SimpleNamespace(edges=[edge]),
    )
    target_updates = []

    async def next_nodes(_action_id, node_id):
        if node_id == "failed-source":
            return {middle.id: []}
        if node_id == middle.node_id:
            return {target.id: []}
        return {}

    def find_node(query):
        if query.get("_id") == middle.id:
            return _FindOne(
                middle,
                modified_count=1 if "status" in query else 0,
            )
        return _FindOne(target, updates=target_updates)

    monkeypatch.setattr(ActionInstanceService, "find_next_node", next_nodes)
    monkeypatch.setattr(
        ActionInstanceNodeModel,
        "find_one",
        staticmethod(find_node),
    )
    publish = AsyncMock()
    monkeypatch.setattr(action_service, "publish_reference_control", publish)
    claim, renew, release = _allow_reference_abort_publish(monkeypatch)

    await ActionInstanceService.cancel_following_nodes(
        action.id,
        "failed-source",
        _action=action,
    )

    assert middle.status == ActionInstanceNodeStatusEnum.CANCELLED
    assert middle.save.await_count == 1
    assert target.status == ActionInstanceNodeStatusEnum.RUNNING
    assert target_updates == [
        {"$addToSet": {"aborted_input_edge_ids": edge.id}}
    ]
    publish.assert_awaited_once_with(
        queue_names=[binding.queue_name],
        stream_id=binding.stream_id,
        producer_id="middle-producer",
        action_id=action.id,
        status="abort",
        reason="前置节点未成功完成，当前节点无法产生输出",
    )
    assert binding.control_status == "abort"
    claim.assert_awaited_once_with(action.id)
    renew.assert_awaited_once_with(action.id, "publish-token")
    release.assert_awaited_once_with(action.id, "publish-token")


@pytest.mark.asyncio
async def test_realtime_abort_updates_edge_but_does_not_publish_without_claim(
    monkeypatch,
) -> None:
    binding = ReferenceQueueBinding(
        edge_id="edge-reference",
        stream_id="stream-reference",
        queue_name="queue-reference",
        owner_action_id="action-terminal",
        source_node_id="source",
        source_port_id="out",
        target_node_id="target",
        target_port_id="in",
    )
    source = SimpleNamespace(
        id="source-instance",
        node_id="source",
        reference_queue_bindings={binding.edge_id: binding},
        save=AsyncMock(),
    )
    target = SimpleNamespace(id="target-instance")
    edge = SimpleNamespace(
        id=binding.edge_id,
        source="source",
        target="target",
        data_type="reference",
    )
    action = SimpleNamespace(
        id="action-terminal",
        status=ActionFlowStatusEnum.TIMEOUT,
        execution_plan_snapshot=SimpleNamespace(edges=[edge]),
    )
    target_updates = []

    def find_node(query):
        if query.get("node_id") == "target":
            return _FindOne(target)
        return _FindOne(updates=target_updates)

    monkeypatch.setattr(
        ActionInstanceNodeModel,
        "find_one",
        staticmethod(find_node),
    )
    collection = SimpleNamespace(
        update_one=AsyncMock(
            return_value=SimpleNamespace(modified_count=0)
        )
    )
    monkeypatch.setattr(
        ActionInstanceModel,
        "get_motor_collection",
        staticmethod(lambda: collection),
    )
    renew = AsyncMock(return_value=True)
    release = AsyncMock()
    monkeypatch.setattr(
        ActionInstanceService,
        "_renew_reference_abort_publish",
        renew,
    )
    monkeypatch.setattr(
        ActionInstanceService,
        "_release_reference_abort_publish",
        release,
    )
    publish = AsyncMock()
    monkeypatch.setattr(action_service, "publish_reference_control", publish)

    await ActionInstanceService._abort_outgoing_edges(
        action,
        source,
        "行动已进入终态",
    )

    assert target_updates == [
        {"$addToSet": {"aborted_input_edge_ids": binding.edge_id}}
    ]
    claim_query = collection.update_one.await_args.args[0]
    assert claim_query["_id"] == action.id
    assert claim_query["status"] == {
        "$in": [
            ActionFlowStatusEnum.RUNNING.value,
            ActionFlowStatusEnum.PAUSED.value,
        ]
    }
    assert claim_query[action_service.REFERENCE_ABORT_PUBLISH_CLOSED_FIELD] == {
        "$ne": True
    }
    renew.assert_not_awaited()
    publish.assert_not_awaited()
    release.assert_not_awaited()
    assert binding.control_status == "open"
    source.save.assert_not_awaited()


@pytest.mark.asyncio
async def test_queue_cleanup_retry_includes_all_recoverable_actions(monkeypatch):
    queries = []

    def find_actions(query):
        queries.append(query)
        return _FindMany(
            [
                SimpleNamespace(
                    id="terminal-pending",
                    status=ActionFlowStatusEnum.TIMEOUT,
                    reference_queue_lifecycle="closing",
                ),
                SimpleNamespace(
                    id="terminal-failed",
                    status=ActionFlowStatusEnum.FAILED,
                    reference_queue_lifecycle="cleanup_failed",
                ),
                SimpleNamespace(
                    id="second-terminal-failed",
                    status=ActionFlowStatusEnum.FAILED,
                    reference_queue_lifecycle="cleanup_failed",
                ),
                SimpleNamespace(
                    id="unready-pending",
                    status=ActionFlowStatusEnum.UNREADY,
                    reference_queue_lifecycle="closing",
                ),
                SimpleNamespace(
                    id="unready-failed",
                    status=ActionFlowStatusEnum.UNREADY,
                    reference_queue_lifecycle="cleanup_failed",
                ),
            ]
        )

    monkeypatch.setattr(
        ActionInstanceModel,
        "find",
        staticmethod(find_actions),
    )
    cleanup = AsyncMock(return_value=True)
    monkeypatch.setattr(
        ActionInstanceService,
        "cleanup_action_queues",
        cleanup,
    )

    threshold_before = datetime.now() - timedelta(seconds=60)
    assert await ActionInstanceService.retry_failed_queue_cleanup() == 5
    threshold_after = datetime.now() - timedelta(seconds=60)
    assert [call.args[0] for call in cleanup.await_args_list] == [
        "terminal-pending",
        "terminal-failed",
        "second-terminal-failed",
        "unready-pending",
        "unready-failed",
    ]
    assert queries == [
        {
            "$or": [
                {
                    "status": {
                            "$in": [
                                ActionFlowStatusEnum.COMPLETED,
                                ActionFlowStatusEnum.PARTIALLY_COMPLETED,
                                ActionFlowStatusEnum.FAILED,
                            ActionFlowStatusEnum.CANCELLED,
                            ActionFlowStatusEnum.TIMEOUT,
                            ActionFlowStatusEnum.STOPPED,
                        ]
                    },
                    "queue_cleanup_state": "failed",
                },
                {
                    "status": {
                            "$in": [
                                ActionFlowStatusEnum.COMPLETED,
                                ActionFlowStatusEnum.PARTIALLY_COMPLETED,
                                ActionFlowStatusEnum.FAILED,
                            ActionFlowStatusEnum.CANCELLED,
                            ActionFlowStatusEnum.TIMEOUT,
                            ActionFlowStatusEnum.STOPPED,
                        ]
                    },
                    "queue_cleanup_state": "pending",
                },
                {
                    "status": ActionFlowStatusEnum.UNREADY,
                    "reference_queue_lifecycle": {
                        "$in": ["closing", "cleanup_failed"]
                    },
                    "queue_cleanup_state": {
                        "$in": ["pending", "failed"]
                    },
                },
                {
                    "status": ActionFlowStatusEnum.READY,
                    "reference_queue_lifecycle": "provisioning",
                    "queue_cleanup_state": "pending",
                    "updated_at": {
                        "$lte": queries[0]["$or"][3]["updated_at"]["$lte"]
                    },
                    "$or": [
                        {
                            action_service.REFERENCE_QUEUE_PROVISION_TOKEN_FIELD: (
                                None
                            )
                        },
                        {
                            action_service.REFERENCE_QUEUE_PROVISION_TOKEN_FIELD: {
                                "$exists": False
                            }
                        },
                        {
                            action_service.REFERENCE_QUEUE_PROVISION_EXPIRES_FIELD: (
                                None
                            )
                        },
                        {
                            action_service.REFERENCE_QUEUE_PROVISION_EXPIRES_FIELD: {
                                "$exists": False
                            }
                        },
                        {
                            action_service.REFERENCE_QUEUE_PROVISION_EXPIRES_FIELD: {
                                "$lte": queries[0]["$or"][3]["$or"][4][
                                    action_service.REFERENCE_QUEUE_PROVISION_EXPIRES_FIELD
                                ]["$lte"]
                            }
                        },
                    ],
                },
            ],
        }
    ]
    threshold = queries[0]["$or"][3]["updated_at"]["$lte"]
    assert threshold_before <= threshold <= threshold_after


@pytest.mark.asyncio
async def test_queue_cleanup_recovers_only_stale_provisioning(monkeypatch):
    now = datetime.now()
    stale = SimpleNamespace(
        id="stale-provisioning",
        status=ActionFlowStatusEnum.READY,
        reference_queue_lifecycle="provisioning",
        queue_cleanup_state="pending",
        updated_at=now - timedelta(seconds=61),
    )
    fresh = SimpleNamespace(
        id="fresh-provisioning",
        status=ActionFlowStatusEnum.READY,
        reference_queue_lifecycle="provisioning",
        queue_cleanup_state="pending",
        updated_at=now - timedelta(seconds=30),
    )
    leased = SimpleNamespace(
        id="leased-provisioning",
        status=ActionFlowStatusEnum.READY,
        reference_queue_lifecycle="provisioning",
        queue_cleanup_state="pending",
        updated_at=now - timedelta(seconds=61),
    )
    setattr(
        leased,
        action_service.REFERENCE_QUEUE_PROVISION_TOKEN_FIELD,
        "active-token",
    )
    setattr(
        leased,
        action_service.REFERENCE_QUEUE_PROVISION_EXPIRES_FIELD,
        now + timedelta(seconds=30),
    )
    thresholds = []
    lease_cutoffs = []

    def find_actions(query):
        provisioning_query = query["$or"][3]
        threshold = provisioning_query["updated_at"]["$lte"]
        lease_cutoff = provisioning_query["$or"][4][
            action_service.REFERENCE_QUEUE_PROVISION_EXPIRES_FIELD
        ]["$lte"]
        thresholds.append(threshold)
        lease_cutoffs.append(lease_cutoff)
        return _FindMany(
            [
                action
                for action in [stale, fresh, leased]
                if action.updated_at <= threshold
                and (
                    getattr(
                        action,
                        action_service.REFERENCE_QUEUE_PROVISION_TOKEN_FIELD,
                        None,
                    )
                    is None
                    or getattr(
                        action,
                        action_service.REFERENCE_QUEUE_PROVISION_EXPIRES_FIELD,
                        None,
                    )
                    <= lease_cutoff
                )
            ]
        )

    collection = SimpleNamespace(
        update_one=AsyncMock(
            return_value=SimpleNamespace(modified_count=1)
        )
    )

    monkeypatch.setattr(
        ActionInstanceModel,
        "find",
        staticmethod(find_actions),
    )
    monkeypatch.setattr(
        ActionInstanceModel,
        "get_motor_collection",
        staticmethod(lambda: collection),
    )
    cleanup = AsyncMock(return_value=True)
    monkeypatch.setattr(
        ActionInstanceService,
        "cleanup_action_queues",
        cleanup,
    )

    assert await ActionInstanceService.retry_failed_queue_cleanup() == 1

    assert stale.updated_at <= thresholds[0] < fresh.updated_at
    assert lease_cutoffs[0] < getattr(
        leased,
        action_service.REFERENCE_QUEUE_PROVISION_EXPIRES_FIELD,
    )
    cleanup.assert_awaited_once_with(stale.id)
    claim_query, claim_update = collection.update_one.await_args.args
    assert claim_query["_id"] == stale.id
    assert claim_query["status"] == ActionFlowStatusEnum.READY.value
    assert claim_query["reference_queue_lifecycle"] == "provisioning"
    assert claim_query["queue_cleanup_state"] == "pending"
    assert claim_query["updated_at"] == {"$lte": thresholds[0]}
    expected_lease_filter = [
        {action_service.REFERENCE_QUEUE_PROVISION_TOKEN_FIELD: None},
        {
            action_service.REFERENCE_QUEUE_PROVISION_TOKEN_FIELD: {
                "$exists": False
            }
        },
        {action_service.REFERENCE_QUEUE_PROVISION_EXPIRES_FIELD: None},
        {
            action_service.REFERENCE_QUEUE_PROVISION_EXPIRES_FIELD: {
                "$exists": False
            }
        },
        {
            action_service.REFERENCE_QUEUE_PROVISION_EXPIRES_FIELD: {
                "$lte": lease_cutoffs[0]
            }
        },
    ]
    assert claim_query["$or"] == expected_lease_filter
    assert claim_update["$set"]["status"] == ActionFlowStatusEnum.UNREADY.value
    assert claim_update["$set"]["reference_queue_lifecycle"] == "closing"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("deleted", "expected_cleanup_state", "expected_lifecycle"),
    [
        (True, "completed", "cleaned"),
        (False, "failed", "cleanup_failed"),
    ],
)
async def test_cleanup_action_queues_updates_managed_lifecycle(
    monkeypatch,
    deleted,
    expected_cleanup_state,
    expected_lifecycle,
):
    binding = ReferenceQueueBinding(
        edge_id="edge-a",
        stream_id="stream-a",
        queue_name="queue-a",
        owner_action_id="action-1",
        source_node_id="source",
        source_port_id="out",
        target_node_id="target",
        target_port_id="in",
    )
    action = SimpleNamespace(id="action-1")
    node = SimpleNamespace(reference_queue_bindings={"edge-a": binding})
    updates = []
    find_results = iter(
        [
            _FindOne(action),
            _FindOne(updates=updates),
            _FindOne(updates=updates),
        ]
    )
    monkeypatch.setattr(
        ActionInstanceModel,
        "find_one",
        staticmethod(lambda _query: next(find_results)),
    )
    monkeypatch.setattr(
        ActionInstanceNodeModel,
        "find",
        staticmethod(lambda _query: _FindMany([node])),
    )
    delete = AsyncMock(return_value=deleted)
    monkeypatch.setattr(action_service, "delete_queue", delete)
    _mock_empty_reference_abort_publish_state(monkeypatch)

    assert (
        await ActionInstanceService.cleanup_action_queues("action-1")
        is deleted
    )

    delete.assert_awaited_once_with("queue-a")
    assert updates[0]["$set"]["reference_queue_lifecycle"] == "closing"
    assert updates[1]["$set"]["queue_cleanup_state"] == (
        expected_cleanup_state
    )
    assert updates[1]["$set"]["reference_queue_lifecycle"] == (
        expected_lifecycle
    )


@pytest.mark.asyncio
async def test_terminal_cleanup_waits_for_abort_publish_release_before_delete(
    monkeypatch,
):
    action = SimpleNamespace(
        id="action-1",
        status=ActionFlowStatusEnum.RUNNING,
        reference_queue_lifecycle="active",
        queue_cleanup_state="pending",
    )
    raw_action = {
        "_id": action.id,
        "status": ActionFlowStatusEnum.RUNNING.value,
    }
    binding = ReferenceQueueBinding(
        edge_id="edge-a",
        stream_id="stream-a",
        queue_name="queue-a",
        owner_action_id=action.id,
        source_node_id="source",
        source_port_id="out",
        target_node_id="target",
        target_port_id="in",
    )
    node = SimpleNamespace(
        id="source-instance",
        action_id=action.id,
        error_message="生产者失败",
        reference_queue_bindings={binding.edge_id: binding},
        save=AsyncMock(),
    )
    events = []
    publish_started = asyncio.Event()
    allow_publish = asyncio.Event()
    publish_closed = asyncio.Event()
    missing = object()

    def matches(document, query):
        for field, expected in query.items():
            if field == "$or":
                if not any(matches(document, branch) for branch in expected):
                    return False
                continue
            actual = document.get(field, missing)
            if not isinstance(expected, dict):
                if actual is missing or actual != expected:
                    return False
                continue
            for operator, value in expected.items():
                if operator == "$in" and actual not in value:
                    return False
                if operator == "$ne" and actual is not missing and actual == value:
                    return False
                if operator == "$exists" and (actual is not missing) != value:
                    return False
                if operator == "$lte" and (
                    actual is missing or actual is None or actual > value
                ):
                    return False
                if operator == "$gt" and (
                    actual is missing or actual is None or actual <= value
                ):
                    return False
        return True

    def update_action(payload):
        for field, value in payload.get("$set", {}).items():
            setattr(action, field, value)

    def find_actions(query):
        statuses = query["status"]["$in"]
        return _FindMany([action] if action.status in statuses else [])

    def find_action(_query):
        return _FindOne(
            action,
            modified_count=1,
            on_update=update_action,
        )

    async def update_raw_action(query, update):
        matched = matches(raw_action, query)
        if not matched:
            return SimpleNamespace(modified_count=0)
        previous_token = raw_action.get(
            action_service.REFERENCE_ABORT_PUBLISH_TOKEN_FIELD
        )
        raw_action.update(update.get("$set", {}))
        if update.get("$set", {}).get(
            action_service.REFERENCE_ABORT_PUBLISH_CLOSED_FIELD
        ) is True:
            events.append("close")
            publish_closed.set()
        for field in update.get("$unset", {}):
            raw_action.pop(field, None)
        current_token = raw_action.get(
            action_service.REFERENCE_ABORT_PUBLISH_TOKEN_FIELD
        )
        if previous_token is None and current_token is not None:
            events.append("claim")
        if previous_token is not None and current_token is None:
            events.append("release")
        return SimpleNamespace(modified_count=1)

    async def find_raw_action(query, _projection=None):
        return dict(raw_action) if matches(raw_action, query) else None

    collection = SimpleNamespace(
        update_one=update_raw_action,
        find_one=find_raw_action,
    )

    def find_nodes(query):
        action_filter = query.get("action_id")
        if action_filter == action.id or action_filter == {"$in": [action.id]}:
            return _FindMany([node])
        return _FindMany([])

    async def publish_control(**_kwargs):
        events.append("publish-start")
        publish_started.set()
        await allow_publish.wait()
        events.append("publish-finished")

    async def delete_queue(_queue_name):
        events.append("delete")
        return True

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
        ActionInstanceModel,
        "get_motor_collection",
        staticmethod(lambda: collection),
    )
    monkeypatch.setattr(
        ActionInstanceNodeModel,
        "find",
        staticmethod(find_nodes),
    )
    monkeypatch.setattr(
        action_service,
        "publish_reference_control",
        publish_control,
    )
    monkeypatch.setattr(action_service, "delete_queue", delete_queue)

    retry_task = asyncio.create_task(
        ActionInstanceService.retry_open_reference_aborts()
    )
    await asyncio.wait_for(publish_started.wait(), timeout=1)
    assert raw_action[action_service.REFERENCE_ABORT_PUBLISH_TOKEN_FIELD]

    action.status = ActionFlowStatusEnum.TIMEOUT
    action.reference_queue_lifecycle = "closing"
    raw_action["status"] = ActionFlowStatusEnum.TIMEOUT.value
    cleanup_task = asyncio.create_task(
        ActionInstanceService.cleanup_action_queues(action.id)
    )
    await asyncio.wait_for(publish_closed.wait(), timeout=1)
    assert "delete" not in events

    allow_publish.set()
    assert await asyncio.wait_for(retry_task, timeout=1) == 1
    assert await asyncio.wait_for(cleanup_task, timeout=1) is True

    assert events.index("close") < events.index("publish-finished")
    assert events.index("publish-finished") < events.index("release")
    assert events.index("release") < events.index("delete")
    assert binding.control_status == "abort"
    assert action_service.REFERENCE_ABORT_PUBLISH_TOKEN_FIELD not in raw_action
    assert action.reference_queue_lifecycle == "cleaned"
    assert action.queue_cleanup_state == "completed"
    assert raw_action[action_service.REFERENCE_ABORT_PUBLISH_CLOSED_FIELD] is True
    assert (
        await ActionInstanceService._claim_reference_abort_publish(action.id)
        is None
    )


@pytest.mark.asyncio
async def test_terminal_cleanup_waits_for_queue_provision_before_delete(
    monkeypatch,
):
    action = SimpleNamespace(
        id="action-provisioning",
        status=ActionFlowStatusEnum.READY,
        reference_queue_lifecycle="provisioning",
        queue_cleanup_state="pending",
    )
    bindings = {
        queue_name: ReferenceQueueBinding(
            edge_id=f"edge-{index}",
            stream_id=f"stream-{index}",
            queue_name=queue_name,
            owner_action_id=action.id,
            source_node_id="source",
            source_port_id=f"out-{index}",
            target_node_id="target",
            target_port_id=f"in-{index}",
        )
        for index, queue_name in enumerate(["queue-1", "queue-2"], start=1)
    }
    node = SimpleNamespace(reference_queue_bindings=bindings)
    raw_action = {
        "_id": action.id,
        "status": ActionFlowStatusEnum.READY.value,
        "reference_queue_lifecycle": "provisioning",
    }
    events = []
    declared_queues = set()
    first_declare_started = asyncio.Event()
    allow_first_declare = asyncio.Event()
    publish_closed = asyncio.Event()
    missing = object()

    def matches(document, query):
        for field, expected in query.items():
            if field == "$or":
                if not any(matches(document, branch) for branch in expected):
                    return False
                continue
            actual = document.get(field, missing)
            if not isinstance(expected, dict):
                if actual is missing or actual != expected:
                    return False
                continue
            for operator, value in expected.items():
                if operator == "$in" and actual not in value:
                    return False
                if operator == "$ne" and actual is not missing and actual == value:
                    return False
                if operator == "$exists" and (actual is not missing) != value:
                    return False
                if operator == "$lte" and (
                    actual is missing or actual is None or actual > value
                ):
                    return False
                if operator == "$gt" and (
                    actual is missing or actual is None or actual <= value
                ):
                    return False
        return True

    async def update_raw_action(query, update):
        if not matches(raw_action, query):
            return SimpleNamespace(modified_count=0)
        previous_token = raw_action.get(
            action_service.REFERENCE_QUEUE_PROVISION_TOKEN_FIELD
        )
        raw_action.update(update.get("$set", {}))
        if update.get("$set", {}).get(
            action_service.REFERENCE_ABORT_PUBLISH_CLOSED_FIELD
        ) is True:
            events.append("close")
            publish_closed.set()
        for field in update.get("$unset", {}):
            raw_action.pop(field, None)
        current_token = raw_action.get(
            action_service.REFERENCE_QUEUE_PROVISION_TOKEN_FIELD
        )
        if previous_token is None and current_token is not None:
            events.append("provision-claim")
        if previous_token is not None and current_token is None:
            events.append("provision-release")
        return SimpleNamespace(modified_count=1)

    async def find_raw_action(query, _projection=None):
        return dict(raw_action) if matches(raw_action, query) else None

    collection = SimpleNamespace(
        update_one=update_raw_action,
        find_one=find_raw_action,
    )

    def update_action(payload):
        for field, value in payload.get("$set", {}).items():
            setattr(action, field, value)

    def find_action(_query):
        return _FindOne(
            action,
            modified_count=1,
            on_update=update_action,
        )

    async def declare_queue(queue_name, **_kwargs):
        events.append(f"declare-start:{queue_name}")
        if queue_name == "queue-1":
            first_declare_started.set()
            await allow_first_declare.wait()
        declared_queues.add(queue_name)
        events.append(f"declare-finished:{queue_name}")

    async def close_channel():
        events.append("channel-close")

    channel = SimpleNamespace(
        declare_queue=declare_queue,
        close=close_channel,
        is_closed=False,
    )
    connection = SimpleNamespace(channel=AsyncMock(return_value=channel))
    monkeypatch.setattr(rabbit_mod, "rabbitmq_connection", connection)
    monkeypatch.setattr(
        ActionInstanceModel,
        "get_motor_collection",
        staticmethod(lambda: collection),
    )
    monkeypatch.setattr(
        ActionInstanceModel,
        "find_one",
        staticmethod(find_action),
    )
    monkeypatch.setattr(
        ActionInstanceNodeModel,
        "find",
        staticmethod(lambda _query: _FindMany([node])),
    )

    async def delete_queue(queue_name):
        events.append(f"delete:{queue_name}")
        declared_queues.discard(queue_name)
        return True

    monkeypatch.setattr(action_service, "delete_queue", delete_queue)

    async def run_provision():
        token = await ActionInstanceService._claim_reference_queue_provision(
            action.id
        )
        assert token is not None
        try:
            return await action_service.provision_reference_queues(
                list(bindings),
                before_declare=lambda: (
                    ActionInstanceService._renew_reference_queue_provision(
                        action.id,
                        token,
                    )
                ),
                declare_timeout_seconds=1,
            )
        finally:
            await ActionInstanceService._release_reference_queue_provision(
                action.id,
                token,
            )

    provision_task = asyncio.create_task(run_provision())
    await asyncio.wait_for(first_declare_started.wait(), timeout=1)
    action.status = ActionFlowStatusEnum.TIMEOUT
    action.reference_queue_lifecycle = "closing"
    raw_action["status"] = ActionFlowStatusEnum.TIMEOUT.value
    raw_action["reference_queue_lifecycle"] = "closing"

    cleanup_task = asyncio.create_task(
        ActionInstanceService.cleanup_action_queues(action.id)
    )
    await asyncio.wait_for(publish_closed.wait(), timeout=1)
    assert not any(event.startswith("delete:") for event in events)

    allow_first_declare.set()
    with pytest.raises(RuntimeError, match="预声明租约已失效"):
        await asyncio.wait_for(provision_task, timeout=1)
    assert await asyncio.wait_for(cleanup_task, timeout=1) is True

    assert "declare-start:queue-2" not in events
    assert events.index("close") < events.index("provision-release")
    first_delete = min(
        index for index, event in enumerate(events) if event.startswith("delete:")
    )
    assert events.index("provision-release") < first_delete
    assert declared_queues == set()
    assert raw_action[action_service.REFERENCE_ABORT_PUBLISH_CLOSED_FIELD] is True
    assert action.reference_queue_lifecycle == "cleaned"
    assert action.queue_cleanup_state == "completed"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "renew_method_name",
    [
        "_renew_reference_queue_provision",
        "_renew_reference_abort_publish",
    ],
)
async def test_reference_lease_renew_rejects_stale_mongo_response(
    monkeypatch,
    renew_method_name,
):
    """验证慢 Mongo 续租响应不会授权后续 RabbitMQ 操作。"""
    started_at = datetime.now()
    clock = SimpleNamespace(
        now=MagicMock(
            side_effect=[
                started_at,
                started_at + timedelta(seconds=20),
            ]
        )
    )
    collection = SimpleNamespace(
        update_one=AsyncMock(
            return_value=SimpleNamespace(modified_count=1)
        )
    )
    monkeypatch.setattr(action_service, "datetime", clock)
    monkeypatch.setattr(
        ActionInstanceModel,
        "get_motor_collection",
        staticmethod(lambda: collection),
    )

    renew = getattr(ActionInstanceService, renew_method_name)
    assert await renew("action-1", "lease-token") is False
    collection.update_one.assert_awaited_once()


@pytest.mark.asyncio
async def test_cleanup_does_not_wait_for_expired_abort_publish_token(
    monkeypatch,
):
    action = SimpleNamespace(
        id="action-1",
    )
    collection = SimpleNamespace(
        find_one=AsyncMock(
            return_value={
                action_service.REFERENCE_ABORT_PUBLISH_TOKEN_FIELD: (
                    "expired-token"
                ),
                action_service.REFERENCE_ABORT_PUBLISH_EXPIRES_FIELD: (
                    datetime.now() - timedelta(seconds=1)
                ),
            }
        ),
        update_one=AsyncMock(
            return_value=SimpleNamespace(modified_count=1)
        ),
    )
    monkeypatch.setattr(
        ActionInstanceModel,
        "get_motor_collection",
        staticmethod(lambda: collection),
    )

    await ActionInstanceService._wait_for_reference_abort_publish(action)

    collection.find_one.assert_awaited_once_with(
        {"_id": action.id},
        {
            action_service.REFERENCE_ABORT_PUBLISH_TOKEN_FIELD: 1,
            action_service.REFERENCE_ABORT_PUBLISH_EXPIRES_FIELD: 1,
        },
    )
    collection.update_one.assert_awaited_once_with(
        {
            "_id": action.id,
            action_service.REFERENCE_ABORT_PUBLISH_TOKEN_FIELD: (
                "expired-token"
            ),
        },
        {
            "$unset": {
                action_service.REFERENCE_ABORT_PUBLISH_TOKEN_FIELD: "",
                action_service.REFERENCE_ABORT_PUBLISH_EXPIRES_FIELD: "",
            }
        },
    )


@pytest.mark.asyncio
async def test_start_accepts_action_with_active_reference_queues(monkeypatch):
    action = SimpleNamespace(
        id="action-1",
        implementation_period=60,
        reference_queue_lifecycle="active",
    )
    updates = []
    find_results = iter(
        [
            _FindOne(action),
            _FindOne(modified_count=1, updates=updates),
            _FindOne(action),
        ]
    )
    monkeypatch.setattr(
        ActionInstanceModel,
        "find_one",
        staticmethod(lambda _query: next(find_results)),
    )
    monkeypatch.setattr(
        ActionInstanceNodeModel,
        "find",
        staticmethod(lambda _query: _FindMany([])),
    )
    monkeypatch.setattr(
        action_service,
        "publish_action_status_observation",
        AsyncMock(),
    )
    monkeypatch.setattr(
        ActionInstanceService,
        "check_action_finished",
        AsyncMock(return_value=False),
    )

    await ActionInstanceService.start("action-1")

    assert updates[0]["$set"]["status"] == ActionFlowStatusEnum.RUNNING


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "lifecycle",
    ["provisioning", "closing", "cleanup_failed", "cleaned"],
)
async def test_start_rejects_action_until_queues_are_active(
    monkeypatch,
    lifecycle,
):
    action = SimpleNamespace(
        id="action-1",
        implementation_period=60,
        reference_queue_lifecycle=lifecycle,
    )
    find_one = MagicMock(return_value=_FindOne(action))
    monkeypatch.setattr(
        ActionInstanceModel,
        "find_one",
        staticmethod(find_one),
    )
    node_find = MagicMock(return_value=_FindMany([]))
    monkeypatch.setattr(
        ActionInstanceNodeModel,
        "find",
        staticmethod(node_find),
    )

    await ActionInstanceService.start("action-1")

    find_one.assert_called_once_with(
        {"_id": "action-1", "status": ActionFlowStatusEnum.READY}
    )
    node_find.assert_not_called()


@pytest.mark.asyncio
async def test_reference_public_output_is_not_written_as_value(monkeypatch):
    node_instance = SimpleNamespace(
        id="output-instance",
        action_id="action-1",
        node_id="output",
        status=ActionInstanceNodeStatusEnum.RUNNING,
        start_at=None,
        outputs={},
        current_execution_id=None,
        progress=0,
        save=AsyncMock(),
    )
    action = SimpleNamespace(
        id="action-1",
        status=ActionFlowStatusEnum.PAUSED,
        execution_plan_snapshot=SimpleNamespace(
            public_interface_snapshot={
                "outputs": [
                    {
                        "id": "public.reference",
                        "data_type": "reference",
                    }
                ]
            }
        ),
        finished_nodes_instance=[],
        invocation_outputs={},
        save=AsyncMock(),
    )
    monkeypatch.setattr(
        ActionInstanceNodeModel,
        "find_one",
        AsyncMock(return_value=node_instance),
    )
    monkeypatch.setattr(
        ActionInstanceModel,
        "find_one",
        AsyncMock(return_value=action),
    )
    monkeypatch.setattr(
        ActionInstanceService,
        "get_instance_node_definition",
        AsyncMock(return_value=SimpleNamespace(handles=[])),
    )
    monkeypatch.setattr(
        ActionInstanceService,
        "get_handle_definition_by_name",
        AsyncMock(return_value=None),
    )
    monkeypatch.setattr(
        ActionInstanceService,
        "find_next_node",
        AsyncMock(return_value={}),
    )

    assert await ActionInstanceService.finish_node(
        node_instance.id,
            SDKResultRequest(
                result_id="result-1",
                attempt=1,
                status="success",
                outputs={"public.reference": "child-queue"},
            ),
    )

    assert node_instance.outputs == {}
    assert action.invocation_outputs == {}


@pytest.mark.asyncio
async def test_native_missing_reference_binding_fails_execution(
    monkeypatch,
) -> None:
    extension_spec = NativeNodeExtensionSpec()
    execution_spec = NodeExecutionSpec(
        driver=ActionExecutionDriverEnum.BACKEND_NATIVE,
        handler="entity.content_analysis",
    )
    plan_node = SimpleNamespace(
        id="target-node",
        extension_spec=extension_spec,
        effective_in_degree=0,
    )
    edge = SimpleNamespace(
        id="edge-missing",
        source="source-node",
        target="target-node",
        target_port_id="data-in-port",
        data_type="reference",
    )
    action = SimpleNamespace(
        id="action-1",
        status=ActionFlowStatusEnum.RUNNING,
        blueprint_id="blueprint-1",
        execution_plan_snapshot=SimpleNamespace(
            nodes=[plan_node],
            edges=[edge],
        ),
        invocation_mode=ActionInvocationModeEnum.STANDALONE,
        invocation_inputs={},
        initiator_user_id=None,
    )
    node_instance = SimpleNamespace(
        id="node-instance-1",
        node_id="target-node",
        status=ActionInstanceNodeStatusEnum.RUNNING,
        start_at=datetime.now(),
        delivered_dependencies=[],
        execution_spec_snapshot=execution_spec,
        extension_spec_snapshot=extension_spec,
        inputs={},
        instance_config={},
        reference_queue_bindings={},
    )
    source_instance = SimpleNamespace(
        node_id="source-node",
        reference_queue_bindings={},
    )
    node_definition = SimpleNamespace(
        node_kind=ActionNodeKindEnum.BACKEND_NATIVE,
        handles=[
            SimpleNamespace(
                id="data-in-port",
                port_id="data-in-port",
                handle_name="data_in",
            )
        ],
        related_components=[],
    )
    execution = SimpleNamespace(
        status=ActionInstanceNodeStatusEnum.RUNNING,
        provider_run_id=None,
        update=AsyncMock(),
    )

    def find_node(query):
        if "status" in query:
            return _FindOne(modified_count=1)
        return _FindOne(node_instance)

    def find_nodes(query):
        if "node_id" in query:
            return _FindMany([])
        return _FindMany([source_instance, node_instance])

    executor = SimpleNamespace(start=AsyncMock())
    finalize = AsyncMock(return_value=False)
    monkeypatch.setattr(
        ActionInstanceNodeModel,
        "find_one",
        staticmethod(find_node),
    )
    monkeypatch.setattr(
        ActionInstanceNodeModel,
        "find",
        staticmethod(find_nodes),
    )
    monkeypatch.setattr(
        ActionInstanceModel,
        "find_one",
        AsyncMock(return_value=action),
    )
    monkeypatch.setattr(
        ActionInstanceService,
        "get_instance_node_definition",
        AsyncMock(return_value=node_definition),
    )
    monkeypatch.setattr(
        ActionInstanceService,
        "find_all_previous_nodes",
        AsyncMock(return_value=[]),
    )
    monkeypatch.setattr(
        ActionInstanceService,
        "get_action_blueprint",
        AsyncMock(return_value=object()),
    )
    monkeypatch.setattr(
        ActionInstanceService,
        "_ensure_node_execution",
        AsyncMock(return_value=execution),
    )
    monkeypatch.setattr(
        ActionInstanceService,
        "_finalize_execution_group",
        finalize,
    )
    monkeypatch.setattr(
        action_service.node_executors,
        "require",
        lambda _driver: executor,
    )

    assert not await ActionInstanceService.run_node(
        node_instance.id,
        action.id,
    )

    executor.start.assert_not_awaited()
    error_update = execution.update.await_args.args[0]["$set"]
    assert error_update["status"] == ActionInstanceNodeStatusEnum.FAILED
    assert error_update["error_message"] == (
        "原生节点Reference输入缺少执行边队列: edge-missing"
    )
    finalize.assert_awaited_once_with(node_instance.id)


@pytest.mark.asyncio
async def test_finish_node_resolves_value_output_from_current_node_first(
    monkeypatch,
) -> None:
    node_instance = SimpleNamespace(
        id="node-instance-1",
        action_id="action-1",
        node_id="analysis-node",
        status=ActionInstanceNodeStatusEnum.RUNNING,
        start_at=None,
        outputs={},
        current_execution_id=None,
        progress=0,
        save=AsyncMock(),
    )
    action = SimpleNamespace(
        id="action-1",
        status=ActionFlowStatusEnum.PAUSED,
        execution_plan_snapshot=SimpleNamespace(
            public_interface_snapshot={"outputs": []},
        ),
        finished_nodes_instance=[],
        invocation_outputs={},
        save=AsyncMock(),
    )
    output_handle = SimpleNamespace(
        id="node.dict_out",
        port_id="dict-out-port",
        handle_config_id="right-config",
        handle_name="dict_out",
        type="source",
    )
    node_definition = SimpleNamespace(handles=[output_handle])
    correct_definition = SimpleNamespace(
        id="right-config",
        type=ActionConfigIOTypeEnum.VALUE,
    )
    global_lookup = AsyncMock(
        return_value=SimpleNamespace(
            id="wrong-config",
            type=ActionConfigIOTypeEnum.VALUE,
        )
    )
    resolve = AsyncMock(
        return_value=(output_handle, correct_definition)
    )
    monkeypatch.setattr(
        ActionInstanceNodeModel,
        "find_one",
        AsyncMock(return_value=node_instance),
    )
    monkeypatch.setattr(
        ActionInstanceModel,
        "find_one",
        AsyncMock(return_value=action),
    )
    monkeypatch.setattr(
        ActionInstanceService,
        "get_instance_node_definition",
        AsyncMock(return_value=node_definition),
    )
    monkeypatch.setattr(
        ActionInstanceService,
        "get_handle_definition_by_name",
        global_lookup,
    )
    monkeypatch.setattr(
        ActionInstanceService,
        "resolve_node_handle_definition",
        resolve,
    )
    monkeypatch.setattr(
        ActionInstanceService,
        "find_next_node",
        AsyncMock(return_value={}),
    )

    assert await ActionInstanceService.finish_node(
        node_instance.id,
        SDKResultRequest(
            result_id="result-1",
            attempt=1,
            status="success",
            outputs={"dict_out": {"uuid": "entity-1"}},
        ),
    )

    assert set(node_instance.outputs) == {"dict-out-port"}
    assert node_instance.outputs["dict-out-port"].value == {
        "uuid": "entity-1"
    }
    resolve.assert_awaited_once_with(node_definition, output_handle.id)
    global_lookup.assert_not_awaited()
