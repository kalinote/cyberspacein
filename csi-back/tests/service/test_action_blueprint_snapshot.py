from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest

from app.models.action.action import ActionInstanceModel
from app.models.action.blueprint import (
    GraphEdgeModel,
    GraphModel,
    ViewportModel,
    create_blueprint_snapshot,
)
from app.schemas.action.reference import ReferenceQueueBinding
from app.schemas.constants import ActionFlowStatusEnum
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
