from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest

from app.models.action.action import (
    ActionConfigIOModel,
    ActionInstanceModel,
    ActionInstanceNodeModel,
)
from app.models.action.blueprint import (
    GraphEdgeModel,
    GraphModel,
    GraphNodeModel,
    NodeDataModel,
    PositionModel,
    ViewportModel,
    create_blueprint_snapshot,
)
from app.models.action.node import ActionNodeModel
from app.schemas.action.execution import (
    BlueprintExecutionPlan,
    ExecutionPlanEdge,
    ExecutionPlanNode,
    default_component_execution,
)
from app.schemas.action.reference import ReferenceQueueBinding
from app.schemas.constants import (
    ActionFlowStatusEnum,
    ActionConfigIOTypeEnum,
    ActionInstanceNodeStatusEnum,
    ActionInvocationModeEnum,
    ActionNodeKindEnum,
    ActionSchedulingModeEnum,
    ActionVisibilityEnum,
)
from app.schemas.general import DictModelSchema
from app.service.action import service as action_service
from app.service.action import ActionInstanceService
from app.utils.id_lib import generate_id


def blueprint_stub(*, name: str = "蓝图", edges=None):
    """构造不依赖数据库的蓝图测试对象。"""
    return SimpleNamespace(
        id="blueprint-1",
        name=name,
        version="1.0.0",
        description="描述",
        target="目标",
        implementation_period=60,
        resource={"key": "value"},
        graph=GraphModel(
            nodes=[],
            edges=edges or [],
            viewport=ViewportModel(x=0, y=0, zoom=1),
        ),
        is_template=False,
        template=None,
    )


def managed_binding() -> ReferenceQueueBinding:
    """构造后端托管的 Reference 队列绑定。"""
    return ReferenceQueueBinding(
        edge_id="edge-1",
        stream_id="stream-1",
        queue_name="managed-queue",
        owner_action_id="action-1",
        source_node_id="source",
        source_port_id="out",
        target_node_id="target",
        target_port_id="in",
    )


def replay_definition(definition_id: str, component_id: str) -> ActionNodeModel:
    """构造冻结重试测试使用的普通节点定义。"""
    return ActionNodeModel.model_construct(
        id=definition_id,
        name=definition_id,
        description="测试节点",
        type="test",
        execution=default_component_execution(),
        version="1.0.0",
        handles=[],
        inputs=[],
        related_components=[component_id],
    )


def allow_queue_provision_lease(monkeypatch):
    """为托管 Action 初始化提供成功的队列预声明租约。"""
    claim = AsyncMock(return_value="provision-token")
    renew = AsyncMock(return_value=True)
    release = AsyncMock()
    monkeypatch.setattr(
        ActionInstanceService,
        "_claim_reference_queue_provision",
        claim,
    )
    monkeypatch.setattr(
        ActionInstanceService,
        "_renew_reference_queue_provision",
        renew,
    )
    monkeypatch.setattr(
        ActionInstanceService,
        "_release_reference_queue_provision",
        release,
    )
    return claim, renew, release


@pytest.mark.asyncio
async def test_init_action_persists_blueprint_snapshot(monkeypatch):
    blueprint = blueprint_stub()
    action_instance = SimpleNamespace(insert=AsyncMock())
    action_factory = Mock(return_value=action_instance)
    action_factory.find_one = Mock(
        return_value=SimpleNamespace(
            update=AsyncMock(return_value=SimpleNamespace(modified_count=1))
        )
    )
    monkeypatch.setattr(action_service, "ActionInstanceModel", action_factory)
    monkeypatch.setattr(
        ActionInstanceService,
        "get_blueprint",
        AsyncMock(return_value=blueprint),
    )
    monkeypatch.setattr(
        action_service,
        "provision_reference_queues",
        AsyncMock(return_value=[]),
    )
    monkeypatch.setattr(
        action_service,
        "publish_action_status_observation",
        AsyncMock(),
    )
    allow_queue_provision_lease(monkeypatch)

    result, action_id = await ActionInstanceService.init("blueprint-1")

    assert result is True
    assert action_id
    snapshot = action_factory.call_args.kwargs["blueprint_snapshot"]
    assert snapshot.blueprint_id == "blueprint-1"
    assert snapshot.name == "蓝图"
    assert snapshot.resource == {"key": "value"}
    action_instance.insert.assert_awaited_once()


@pytest.mark.asyncio
async def test_init_managed_action_provisions_queues_before_active(monkeypatch):
    blueprint = blueprint_stub()
    action_instance = SimpleNamespace(insert=AsyncMock())
    action_factory = Mock(return_value=action_instance)
    update = AsyncMock(return_value=SimpleNamespace(modified_count=1))
    action_factory.find_one = Mock(
        return_value=SimpleNamespace(update=update)
    )
    monkeypatch.setattr(action_service, "ActionInstanceModel", action_factory)
    monkeypatch.setattr(
        ActionInstanceService,
        "get_blueprint",
        AsyncMock(return_value=blueprint),
    )
    build_bindings = Mock(
        return_value={"source": {"edge-1": managed_binding()}}
    )
    monkeypatch.setattr(
        ActionInstanceService,
        "_build_reference_queue_bindings",
        build_bindings,
    )
    provision = AsyncMock(return_value=["managed-queue"])
    monkeypatch.setattr(
        action_service,
        "provision_reference_queues",
        provision,
    )
    monkeypatch.setattr(
        action_service,
        "publish_action_status_observation",
        AsyncMock(),
    )
    claim, _, release = allow_queue_provision_lease(monkeypatch)

    result, action_id = await ActionInstanceService.init("blueprint-1")

    assert result is True
    assert action_id
    assert action_factory.call_args.kwargs["reference_queue_lifecycle"] == (
        "provisioning"
    )
    assert len(build_bindings.call_args.args) == 4
    provision.assert_awaited_once()
    assert provision.await_args.args == (["managed-queue"],)
    assert callable(provision.await_args.kwargs["before_declare"])
    assert provision.await_args.kwargs["declare_timeout_seconds"] == (
        action_service.REFERENCE_QUEUE_PROVISION_DECLARE_TIMEOUT_SECONDS
    )
    claim.assert_awaited_once_with(action_id)
    release.assert_awaited_once_with(action_id, "provision-token")
    action_factory.find_one.assert_called_once_with(
        {
            "_id": action_id,
            "status": ActionFlowStatusEnum.READY,
            "reference_queue_lifecycle": "provisioning",
        }
    )
    assert update.await_args.args[0]["$set"][
        "reference_queue_lifecycle"
    ] == "active"


@pytest.mark.asyncio
async def test_init_managed_action_cleans_up_when_activation_cas_fails(
    monkeypatch,
):
    blueprint = blueprint_stub()
    action_instance = SimpleNamespace(insert=AsyncMock())
    action_factory = Mock(return_value=action_instance)
    update = AsyncMock(return_value=SimpleNamespace(modified_count=0))
    action_factory.find_one = Mock(
        return_value=SimpleNamespace(update=update)
    )
    monkeypatch.setattr(action_service, "ActionInstanceModel", action_factory)
    monkeypatch.setattr(
        ActionInstanceService,
        "get_blueprint",
        AsyncMock(return_value=blueprint),
    )
    monkeypatch.setattr(
        ActionInstanceService,
        "_build_reference_queue_bindings",
        Mock(return_value={"source": {"edge-1": managed_binding()}}),
    )
    provision = AsyncMock(return_value=["managed-queue"])
    monkeypatch.setattr(
        action_service,
        "provision_reference_queues",
        provision,
    )
    cleanup = AsyncMock(return_value=True)
    monkeypatch.setattr(
        ActionInstanceService,
        "cleanup_action_queues",
        cleanup,
    )
    monkeypatch.setattr(
        action_service,
        "publish_action_status_observation",
        AsyncMock(),
    )
    claim, _, release = allow_queue_provision_lease(monkeypatch)

    result, message = await ActionInstanceService.init("blueprint-1")
    action_id = action_factory.call_args.kwargs["id"]

    assert result is False
    assert message == (
        f"行动状态在 Reference 队列预声明期间发生变化: {action_id}"
    )
    provision.assert_awaited_once()
    assert provision.await_args.args == (["managed-queue"],)
    claim.assert_awaited_once_with(action_id)
    release.assert_awaited_once_with(action_id, "provision-token")
    action_factory.find_one.assert_called_once_with(
        {
            "_id": action_id,
            "status": ActionFlowStatusEnum.READY,
            "reference_queue_lifecycle": "provisioning",
        }
    )
    cleanup.assert_awaited_once_with(action_id)


@pytest.mark.asyncio
async def test_init_managed_action_provision_failure_marks_unready_and_cleans_up(
    monkeypatch,
):
    blueprint = blueprint_stub()
    action_instance = SimpleNamespace(insert=AsyncMock())
    action_factory = Mock(return_value=action_instance)
    update = AsyncMock()
    action_factory.find_one = Mock(
        return_value=SimpleNamespace(update=update)
    )
    monkeypatch.setattr(action_service, "ActionInstanceModel", action_factory)
    monkeypatch.setattr(
        ActionInstanceService,
        "get_blueprint",
        AsyncMock(return_value=blueprint),
    )
    monkeypatch.setattr(
        ActionInstanceService,
        "_build_reference_queue_bindings",
        Mock(return_value={"source": {"edge-1": managed_binding()}}),
    )
    provision = AsyncMock(side_effect=RuntimeError("RabbitMQ不可用"))
    monkeypatch.setattr(
        action_service,
        "provision_reference_queues",
        provision,
    )
    cleanup = AsyncMock(return_value=True)
    monkeypatch.setattr(
        ActionInstanceService,
        "cleanup_action_queues",
        cleanup,
    )
    monkeypatch.setattr(
        action_service,
        "publish_action_status_observation",
        AsyncMock(),
    )
    claim, _, release = allow_queue_provision_lease(monkeypatch)

    result, message = await ActionInstanceService.init("blueprint-1")

    assert result is False
    assert message.startswith("行动 Reference 队列预声明失败:")
    provision.assert_awaited_once()
    assert provision.await_args.args == (["managed-queue"],)
    action_id = action_factory.call_args.kwargs["id"]
    claim.assert_awaited_once_with(action_id)
    release.assert_awaited_once_with(action_id, "provision-token")
    cleanup.assert_awaited_once()
    assert update.await_args.args[0]["$set"]["status"] == (
        ActionFlowStatusEnum.UNREADY
    )
    assert update.await_args.args[0]["$set"][
        "reference_queue_lifecycle"
    ] == "closing"


@pytest.mark.asyncio
async def test_init_child_action_provisions_backend_owned_queues(monkeypatch):
    blueprint = blueprint_stub()
    action_instance = SimpleNamespace(insert=AsyncMock())
    action_factory = Mock(return_value=action_instance)
    action_factory.find_one = Mock(
        return_value=SimpleNamespace(
            update=AsyncMock(return_value=SimpleNamespace(modified_count=1))
        )
    )
    monkeypatch.setattr(action_service, "ActionInstanceModel", action_factory)
    monkeypatch.setattr(
        ActionInstanceService,
        "get_blueprint",
        AsyncMock(return_value=blueprint),
    )
    monkeypatch.setattr(
        action_service,
        "publish_action_status_observation",
        AsyncMock(),
    )
    monkeypatch.setattr(
        ActionInstanceService,
        "_build_reference_queue_bindings",
        Mock(return_value={"source": {"edge-1": managed_binding()}}),
    )
    provision = AsyncMock(return_value=["managed-queue"])
    monkeypatch.setattr(
        action_service,
        "provision_reference_queues",
        provision,
    )
    allow_queue_provision_lease(monkeypatch)

    result, action_id = await ActionInstanceService.init(
        "blueprint-1",
        parent_action_id="parent-action",
    )

    assert result is True
    assert action_id
    assert action_factory.call_args.kwargs["reference_queue_lifecycle"] == (
        "provisioning"
    )
    assert action_factory.call_args.kwargs["parent_action_id"] == "parent-action"
    provision.assert_awaited_once()
    assert provision.await_args.args == (["managed-queue"],)


@pytest.mark.asyncio
async def test_retry_replays_frozen_context_with_fresh_reference_queues(
    monkeypatch,
):
    source_definition = replay_definition("source-definition", "source-component")
    target_definition = replay_definition("target-definition", "target-component")
    graph = GraphModel(
        nodes=[
            GraphNodeModel(
                id="source",
                type="test",
                position=PositionModel(x=0, y=0),
                data=NodeDataModel(
                    definition_id=source_definition.id,
                    version="1.0.0",
                    form_data=[DictModelSchema(key="limit", value=1)],
                ),
            ),
            GraphNodeModel(
                id="target",
                type="test",
                position=PositionModel(x=100, y=0),
                data=NodeDataModel(
                    definition_id=target_definition.id,
                    version="1.0.0",
                    form_data=[],
                ),
            ),
        ],
        edges=[
            GraphEdgeModel(
                id="edge-1",
                source="source",
                sourceHandle="out",
                target="target",
                targetHandle="in",
                source_port_id="out",
                target_port_id="in",
            )
        ],
        viewport=ViewportModel(x=0, y=0, zoom=1),
    )
    frozen_blueprint = create_blueprint_snapshot(
        SimpleNamespace(
            id="blueprint-1",
            name="冻结蓝图",
            version="1.0.0",
            description="描述",
            target="目标",
            implementation_period=60,
            resource=None,
            graph=graph,
            is_template=True,
            template={
                "params": [{"name": "limit", "required": True}],
                "bindings": {"source": {"limit": "limit"}},
            },
        )
    )
    execution_plan = BlueprintExecutionPlan(
        plan_schema_version=3,
        revision_id="revision-1",
        invocation_mode=ActionInvocationModeEnum.STANDALONE,
        scheduling_mode=ActionSchedulingModeEnum.STREAMING,
        debug=True,
        nodes=[
            ExecutionPlanNode(
                id="source",
                definition_id=source_definition.id,
                node_kind=ActionNodeKindEnum.ORDINARY,
                execution=source_definition.execution,
                instance_config={"limit": 1},
                effective_out_degree=1,
            ),
            ExecutionPlanNode(
                id="target",
                definition_id=target_definition.id,
                node_kind=ActionNodeKindEnum.ORDINARY,
                execution=target_definition.execution,
                effective_in_degree=1,
            ),
        ],
        edges=[
            ExecutionPlanEdge(
                id="edge-1",
                source="source",
                source_port_id="out",
                target="target",
                target_port_id="in",
                data_type="reference",
                reference_protocol="eos-v1",
            )
        ],
    )
    source_action = ActionInstanceModel.model_construct(
        id="source-action",
        blueprint_id="blueprint-1",
        blueprint_snapshot=frozen_blueprint,
        blueprint_revision_id="revision-1",
        execution_plan_snapshot=execution_plan,
        invocation_mode=ActionInvocationModeEnum.STANDALONE,
        debug=True,
        scheduling_mode_override=None,
        visibility=ActionVisibilityEnum.NORMAL,
        status=ActionFlowStatusEnum.FAILED,
        implementation_period=60,
        nodes_id=["source", "target"],
    )
    old_binding = managed_binding().model_copy(
        update={
            "queue_name": "old-reference-queue",
            "owner_action_id": source_action.id,
            "expected_producer_ids": ["old-component-run"],
        }
    )
    source_nodes = [
        ActionInstanceNodeModel.model_construct(
            id="old-source-node",
            action_id=source_action.id,
            node_id="source",
            definition_id=source_definition.id,
            definition_snapshot=source_definition.model_dump(
                mode="python", by_alias=True
            ),
            status=ActionInstanceNodeStatusEnum.FAILED,
            configs=[DictModelSchema(key="limit", value=17)],
            reference_queue_bindings={"edge-1": old_binding},
            execution_spec_snapshot=source_definition.execution,
            instance_config={"limit": 17},
        ),
        ActionInstanceNodeModel.model_construct(
            id="old-target-node",
            action_id=source_action.id,
            node_id="target",
            definition_id=target_definition.id,
            definition_snapshot=target_definition.model_dump(
                mode="python", by_alias=True
            ),
            status=ActionInstanceNodeStatusEnum.CANCELLED,
            configs=[],
            inputs={
                "in": ActionConfigIOModel(
                    type=ActionConfigIOTypeEnum.REFERENCE,
                    key="frozen_data_in",
                    value=old_binding.queue_name,
                )
            },
            execution_spec_snapshot=target_definition.execution,
        ),
    ]

    created_actions = []
    action_factory = Mock()

    def create_action(**kwargs):
        action = SimpleNamespace(
            **kwargs,
            insert=AsyncMock(),
            updated_at=None,
        )
        created_actions.append(action)
        return action

    action_factory.side_effect = create_action
    action_factory.find_one = Mock(
        return_value=SimpleNamespace(
            update=AsyncMock(return_value=SimpleNamespace(modified_count=1))
        )
    )
    created_nodes = []
    node_factory = Mock()

    def create_node(**kwargs):
        node = SimpleNamespace(**kwargs, insert=AsyncMock())
        created_nodes.append(node)
        return node

    node_factory.side_effect = create_node
    node_factory.find = Mock(
        return_value=SimpleNamespace(to_list=AsyncMock(return_value=source_nodes))
    )
    monkeypatch.setattr(action_service, "ActionInstanceModel", action_factory)
    monkeypatch.setattr(action_service, "ActionInstanceNodeModel", node_factory)
    frozen_definitions = {
        source_definition.id: source_definition,
        target_definition.id: target_definition,
    }
    monkeypatch.setattr(
        action_service.ActionNodeModel,
        "model_validate",
        Mock(
            side_effect=lambda value: frozen_definitions[value["_id"]].model_copy(
                deep=True
            )
        ),
    )
    get_blueprint = AsyncMock()
    monkeypatch.setattr(ActionInstanceService, "get_blueprint", get_blueprint)
    monkeypatch.setattr(
        action_service.BlueprintCompiler,
        "validate_encapsulated_dependencies",
        AsyncMock(),
    )
    resolve_handle = AsyncMock(side_effect=AssertionError("重试不应查询当前Handle"))
    monkeypatch.setattr(
        ActionInstanceService,
        "resolve_node_handle_definition",
        resolve_handle,
    )
    monkeypatch.setattr(
        ActionInstanceService,
        "set_node_status",
        AsyncMock(),
    )
    provision = AsyncMock(return_value=[])
    monkeypatch.setattr(
        action_service,
        "provision_reference_queues",
        provision,
    )
    monkeypatch.setattr(
        action_service,
        "publish_action_status_observation",
        AsyncMock(),
    )
    allow_queue_provision_lease(monkeypatch)

    result, new_action_id = await ActionInstanceService.init(
        source_action.blueprint_id,
        initiator_user_id="retry-user",
        _replay_source=source_action,
    )

    assert result is True
    get_blueprint.assert_not_awaited()
    created_action = created_actions[0]
    assert created_action.id == new_action_id
    assert created_action.id != source_action.id
    assert created_action.blueprint_snapshot == source_action.blueprint_snapshot
    assert created_action.execution_plan_snapshot == source_action.execution_plan_snapshot
    assert created_action.execution_plan_snapshot is not source_action.execution_plan_snapshot
    assert created_action.debug is True
    assert created_action.scheduling_mode_override is None
    assert created_action.initiator_user_id == "retry-user"
    assert created_action.retry_of_action_id == source_action.id
    assert created_action.trigger_type == "manual"
    assert created_action.trigger_key is None
    assert created_action.schedule_id is None

    new_source = next(node for node in created_nodes if node.node_id == "source")
    new_target = next(node for node in created_nodes if node.node_id == "target")
    assert new_source.status == ActionInstanceNodeStatusEnum.PENDING
    assert new_source.configs == source_nodes[0].configs
    assert new_source.configs[0].value == 17
    new_binding = new_source.reference_queue_bindings["edge-1"]
    assert new_binding.owner_action_id == new_action_id
    assert new_binding.queue_name != old_binding.queue_name
    assert new_binding.expected_producer_ids != old_binding.expected_producer_ids
    assert new_binding.expected_producer_ids == [
        generate_id(
            f"{generate_id(new_action_id + 'source')}:source-component:1"
        )
    ]
    assert new_target.inputs["in"].value == new_binding.queue_name
    assert new_target.inputs["in"].key == "frozen_data_in"
    resolve_handle.assert_not_awaited()
    assert provision.await_args.args == ([new_binding.queue_name],)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "status",
    [
        ActionFlowStatusEnum.FAILED,
        ActionFlowStatusEnum.TIMEOUT,
        ActionFlowStatusEnum.COMPLETED,
        ActionFlowStatusEnum.PARTIALLY_COMPLETED,
    ],
)
async def test_retry_accepts_replayable_normal_standalone_actions(
    monkeypatch,
    status,
):
    source = SimpleNamespace(
        id="source-action",
        blueprint_id="blueprint-1",
        invocation_mode=ActionInvocationModeEnum.STANDALONE,
        visibility=ActionVisibilityEnum.NORMAL,
        status=status,
        is_deleted=False,
    )
    monkeypatch.setattr(
        ActionInstanceModel,
        "find_one",
        AsyncMock(return_value=source),
    )
    init = AsyncMock(return_value=(True, "new-action"))
    monkeypatch.setattr(ActionInstanceService, "init", init)

    result = await ActionInstanceService.retry(
        source.id,
        initiator_user_id="retry-user",
    )

    assert result == (True, "new-action")
    assert init.await_args.args == (source.blueprint_id,)
    assert init.await_args.kwargs == {
        "initiator_user_id": "retry-user",
        "_replay_source": source,
    }


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("invocation_mode", "visibility", "status"),
    [
        (
            ActionInvocationModeEnum.SUBFLOW,
            ActionVisibilityEnum.NORMAL,
            ActionFlowStatusEnum.FAILED,
        ),
        (
            ActionInvocationModeEnum.STANDALONE,
            ActionVisibilityEnum.EMBEDDED,
            ActionFlowStatusEnum.FAILED,
        ),
        (
            ActionInvocationModeEnum.STANDALONE,
            ActionVisibilityEnum.NORMAL,
            ActionFlowStatusEnum.STOPPED,
        ),
        (
            ActionInvocationModeEnum.STANDALONE,
            ActionVisibilityEnum.NORMAL,
            ActionFlowStatusEnum.CANCELLED,
        ),
    ],
)
async def test_retry_rejects_non_retryable_source_actions(
    monkeypatch,
    invocation_mode,
    visibility,
    status,
):
    source = SimpleNamespace(
        id="source-action",
        blueprint_id="blueprint-1",
        invocation_mode=invocation_mode,
        visibility=visibility,
        status=status,
        is_deleted=False,
    )
    monkeypatch.setattr(
        ActionInstanceModel,
        "find_one",
        AsyncMock(return_value=source),
    )
    init = AsyncMock()
    monkeypatch.setattr(ActionInstanceService, "init", init)

    success, _ = await ActionInstanceService.retry(source.id)

    assert success is False
    init.assert_not_awaited()


@pytest.mark.asyncio
async def test_find_next_node_uses_execution_plan_snapshot(monkeypatch):
    old_edge = GraphEdgeModel(
        id="edge-old",
        source="node-1",
        sourceHandle="output",
        target="node-old",
        targetHandle="input",
    )
    new_edge = GraphEdgeModel(
        id="edge-new",
        source="node-1",
        sourceHandle="output",
        target="node-new",
        targetHandle="input",
    )
    action = SimpleNamespace(
        id="action-1",
        blueprint_id="blueprint-1",
        blueprint_snapshot=create_blueprint_snapshot(
            blueprint_stub(name="旧蓝图", edges=[old_edge])
        ),
        execution_plan_snapshot=SimpleNamespace(
            edges=[
                SimpleNamespace(
                    source="node-1",
                    source_port_id="output",
                    target="node-old",
                    target_port_id="input",
                )
            ]
        ),
    )
    monkeypatch.setattr(
        ActionInstanceModel,
        "find_one",
        AsyncMock(return_value=action),
    )
    get_blueprint = AsyncMock(return_value=blueprint_stub(name="新蓝图", edges=[new_edge]))
    monkeypatch.setattr(ActionInstanceService, "get_blueprint", get_blueprint)

    next_nodes = await ActionInstanceService.find_next_node("action-1", "node-1")

    assert generate_id("action-1node-old") in next_nodes
    assert generate_id("action-1node-new") not in next_nodes
    get_blueprint.assert_not_awaited()
