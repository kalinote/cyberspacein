from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.models.action.action import ActionInstanceModel, ActionInstanceNodeModel
from app.schemas.action.execution import NodeExecutionContext, NodeExecutionSpec
from app.schemas.action.node import ActionNode
from app.schemas.action.sdk import SDKResultRequest
from app.schemas.constants import (
    ActionExecutionDriverEnum,
    ActionFlowStatusEnum,
    ActionInstanceNodeStatusEnum,
    ActionNodeKindEnum,
    ActionNodeTypeEnum,
    ComponentRunStatusEnum,
)
from app.schemas.action.reference import (
    ReferenceProducerKindEnum,
    ReferenceQueueBinding,
)
from app.service import action as action_service
from app.service.action import ActionInstanceService
from app.service.node_executors import component as component_executor
from app.service.node_executors.component import ComponentNodeExecutor


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
    def __init__(self, values):
        self.values = values

    def limit(self, _limit):
        return self

    async def to_list(self):
        return self.values


async def _node_definition(_definition_id):
    return SimpleNamespace(id="definition-1")


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
async def test_failed_queue_cleanup_is_retried(monkeypatch):
    monkeypatch.setattr(
        ActionInstanceModel,
        "find",
        staticmethod(
            lambda _query: _FindMany(
                [SimpleNamespace(id="action-a"), SimpleNamespace(id="action-b")]
            )
        ),
    )
    cleanup = AsyncMock(side_effect=[True, False])
    monkeypatch.setattr(
        ActionInstanceService,
        "cleanup_action_queues",
        cleanup,
    )

    assert await ActionInstanceService.retry_failed_queue_cleanup() == 1
    assert [call.args[0] for call in cleanup.await_args_list] == [
        "action-a",
        "action-b",
    ]


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
