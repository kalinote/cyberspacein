from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from app.api.v1.endpoints.action import configs as configs_endpoint
from app.api.v1.endpoints.action import resource as resource_endpoint
from app.models.action.configs import ActionNodesHandleConfigModel
from app.models.action.node import ActionNodeInputModel, ActionNodeModel
from app.schemas.action.execution import NativeNodeExtensionSpec, NodeExecutionSpec
from app.schemas.action.node import ActionNode
from app.schemas.action.node import EncapsulatedNodeReferenceResponse
from app.schemas.constants import (
    ActionExecutionDriverEnum,
    ActionConfigIOTypeEnum,
    ActionNodeDefinitionOriginEnum,
    ActionNodeInputTypeEnum,
    ActionNodeKindEnum,
    ActionNodeTypeEnum,
)
from app.service.action import ActionInstanceService, node_model_to_response
from app.service.native_nodes.contracts import BackendNativeNodeDefinition
from app.service.native_nodes.registry import BackendNativeDefinitionRegistry
from app.service.encapsulated_node import EncapsulatedNodeReferencedError


def _native_request() -> ActionNode:
    return ActionNode(
        name="伪造原生节点",
        description="不允许通过通用接口创建",
        type=ActionNodeTypeEnum.PROCESSOR,
        node_kind=ActionNodeKindEnum.BACKEND_NATIVE,
        execution=NodeExecutionSpec(
            driver=ActionExecutionDriverEnum.BACKEND_NATIVE,
            handler="analysis.invoke",
        ),
        extension=NativeNodeExtensionSpec(),
        definition_origin=ActionNodeDefinitionOriginEnum.BACKEND_BUILTIN,
        version="1",
        handles=[],
        inputs=[],
        related_components=[],
    )


@pytest.mark.asyncio
async def test_key_value_input_can_serialize_for_native_resource(
    monkeypatch,
) -> None:
    query = SimpleNamespace(to_list=AsyncMock(return_value=[]))
    monkeypatch.setattr(
        ActionNodesHandleConfigModel,
        "find",
        lambda *_args, **_kwargs: query,
    )
    monkeypatch.setattr(
        ActionNodesHandleConfigModel,
        "id",
        "id",
        raising=False,
    )
    node = ActionNodeModel.model_construct(
        id="analysis-projection",
        name="分析节点",
        description="分析节点",
        type=ActionNodeTypeEnum.PROCESSOR.value,
        node_kind=ActionNodeKindEnum.BACKEND_NATIVE,
        execution=NodeExecutionSpec(
            driver=ActionExecutionDriverEnum.BACKEND_NATIVE,
            handler="analysis.invoke",
        ),
        extension=NativeNodeExtensionSpec(),
        definition_origin=ActionNodeDefinitionOriginEnum.BACKEND_BUILTIN,
        builtin_key="analysis",
        version="1",
        handles=[],
        inputs=[
            ActionNodeInputModel(
                id="input-mapping",
                name="input_mapping",
                type="key-value",
                position="center",
                label="输入映射",
                description="输入映射",
                required=False,
                default={},
                options=[],
                custom_style=[],
                custom_props=[],
            )
        ],
        default_configs=[],
        related_components=[],
    )

    response = await node_model_to_response(node)

    assert response.inputs[0].type == ActionNodeInputTypeEnum.KEY_VALUE


@pytest.mark.asyncio
async def test_handle_options_are_derived_from_active_node_usage(
    monkeypatch,
) -> None:
    nodes_query = SimpleNamespace(
        to_list=AsyncMock(
            return_value=[
                SimpleNamespace(
                    builtin_key=None,
                    handles=[
                        SimpleNamespace(
                            id="definition.input",
                            handle_config_id="data-in",
                            interface_type_id="custom.value",
                            compatible_interface_type_ids=["builtin.value"],
                            type="target",
                        )
                    ],
                )
            ]
        )
    )
    configs_query = SimpleNamespace(
        to_list=AsyncMock(
            return_value=[
                SimpleNamespace(
                    id="data-in",
                    handle_name="data_in",
                    label="通用数据输入",
                    type=ActionConfigIOTypeEnum.VALUE,
                    color="#409eff",
                    other_compatible_interfaces=[],
                )
            ]
        )
    )
    monkeypatch.setattr(
        ActionNodeModel,
        "find",
        staticmethod(lambda _query: nodes_query),
    )
    monkeypatch.setattr(
        ActionNodesHandleConfigModel,
        "find",
        staticmethod(lambda _query: configs_query),
    )

    response = await configs_endpoint.get_node_handle_options("target")

    assert response.code == 0
    assert response.data[0].id == "data-in"
    assert response.data[0].interface_type_id == "custom.value"
    assert response.data[0].direction == "target"


@pytest.mark.asyncio
async def test_handle_options_include_reference_configs(monkeypatch) -> None:
    nodes_query = SimpleNamespace(
        to_list=AsyncMock(
            return_value=[
                SimpleNamespace(
                    builtin_key=None,
                    handles=[
                        SimpleNamespace(
                            id="definition.reference",
                            handle_config_id="reference-in",
                            interface_type_id="custom.reference",
                            compatible_interface_type_ids=[],
                            type="target",
                        )
                    ],
                )
            ]
        )
    )
    configs_query = SimpleNamespace(
        to_list=AsyncMock(
            return_value=[
                SimpleNamespace(
                    id="reference-in",
                    handle_name="reference_in",
                    label="引用输入",
                    type=ActionConfigIOTypeEnum.REFERENCE,
                    color="#7c3aed",
                    other_compatible_interfaces=[],
                )
            ]
        )
    )
    monkeypatch.setattr(
        ActionNodeModel,
        "find",
        staticmethod(lambda _query: nodes_query),
    )
    monkeypatch.setattr(
        ActionNodesHandleConfigModel,
        "find",
        staticmethod(lambda _query: configs_query),
    )

    response = await configs_endpoint.get_node_handle_options("target")

    assert response.code == 0
    assert response.data[0].data_type == ActionConfigIOTypeEnum.REFERENCE


@pytest.mark.asyncio
async def test_generic_create_rejects_backend_native_node() -> None:
    response = await resource_endpoint.create_node(_native_request())

    assert response.code == 240425
    assert "只能创建普通节点" in response.message


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("operation", "message"),
    [
        ("update", "不能通过通用接口修改"),
        ("delete", "不能通过通用接口删除"),
    ],
)
async def test_generic_mutations_reject_system_resources(
    monkeypatch,
    operation,
    message,
) -> None:
    node = SimpleNamespace(
        definition_origin=ActionNodeDefinitionOriginEnum.BACKEND_BUILTIN,
        update=AsyncMock(),
    )
    monkeypatch.setattr(ActionNodeModel, "find_one", AsyncMock(return_value=node))

    if operation == "update":
        response = await resource_endpoint.update_node(
            "builtin-1",
            _native_request(),
        )
    else:
        response = await resource_endpoint.delete_node("builtin-1")

    assert response.code == 240425
    assert message in response.message
    node.update.assert_not_awaited()


@pytest.mark.asyncio
async def test_enabled_endpoint_only_accepts_backend_builtin(monkeypatch) -> None:
    node = SimpleNamespace(
        definition_origin=ActionNodeDefinitionOriginEnum.USER,
        update=AsyncMock(),
    )
    monkeypatch.setattr(ActionNodeModel, "find_one", AsyncMock(return_value=node))

    response = await resource_endpoint.set_native_node_enabled(
        "ordinary-1",
        resource_endpoint.NativeNodeEnabledRequest(enabled=False),
        SimpleNamespace(state=SimpleNamespace(auth_context=None)),
    )

    assert response.code == 240425
    node.update.assert_not_awaited()


@pytest.mark.asyncio
async def test_encapsulated_delete_returns_structured_references(
    monkeypatch,
) -> None:
    reference = EncapsulatedNodeReferenceResponse(
        blueprint_id="parent-1",
        blueprint_name="父蓝图",
        blueprint_version="1.0",
        instance_count=2,
        instance_ids=["node-a", "node-b"],
    )
    monkeypatch.setattr(
        resource_endpoint,
        "delete_encapsulated_node_version",
        AsyncMock(side_effect=EncapsulatedNodeReferencedError([reference])),
    )

    response = await resource_endpoint.delete_encapsulated_node("encapsulated-v2")

    assert response.code == 240423
    assert response.data.references[0].blueprint_id == "parent-1"
    assert response.data.references[0].instance_count == 2


@pytest.mark.asyncio
async def test_definition_sync_preserves_disabled_projection(monkeypatch) -> None:
    existing = SimpleNamespace(
        id="projection-1",
        enabled=False,
        update=AsyncMock(),
    )
    monkeypatch.setattr(
        ActionNodeModel,
        "find_one",
        AsyncMock(side_effect=[existing, existing]),
    )
    registry = BackendNativeDefinitionRegistry()
    definition = BackendNativeNodeDefinition(
        builtin_key="test.sync.disabled",
        definition_version=1,
        name="禁用投影",
        description="测试同步保留禁用状态",
        handler="test.handler",
        category="processor",
        extension=NativeNodeExtensionSpec(),
    )
    registry._definitions[(definition.builtin_key, 1)] = definition

    projections = await registry.sync_projections()

    update_fields = existing.update.await_args.args[0]["$set"]
    assert "enabled" not in update_fields
    assert projections == [existing]
    assert existing.enabled is False


@pytest.mark.asyncio
async def test_native_toggle_records_operator_and_clears_cache(monkeypatch) -> None:
    node = SimpleNamespace(
        definition_origin=ActionNodeDefinitionOriginEnum.BACKEND_BUILTIN,
        update=AsyncMock(),
    )
    updated = SimpleNamespace(id="builtin-1")
    clear_cache = AsyncMock()
    monkeypatch.setattr(ActionNodeModel, "find_one", AsyncMock(return_value=node))
    monkeypatch.setattr(ActionNodeModel, "get", AsyncMock(return_value=updated))
    monkeypatch.setattr(ActionNodeModel, "enabled", "enabled", raising=False)
    monkeypatch.setattr(ActionNodeModel, "disabled_at", "disabled_at", raising=False)
    monkeypatch.setattr(ActionNodeModel, "disabled_by", "disabled_by", raising=False)
    monkeypatch.setattr(ActionNodeModel, "updated_at", "updated_at", raising=False)
    monkeypatch.setattr(ActionInstanceService, "_clear_cache", clear_cache)
    monkeypatch.setattr(
        resource_endpoint,
        "node_model_to_response",
        AsyncMock(return_value={"id": "builtin-1", "enabled": False}),
    )

    response = await resource_endpoint.set_native_node_enabled(
        "builtin-1",
        resource_endpoint.NativeNodeEnabledRequest(enabled=False),
        SimpleNamespace(
            state=SimpleNamespace(
                auth_context=SimpleNamespace(user=SimpleNamespace(id="user-1"))
            )
        ),
    )

    fields = node.update.await_args.args[0].query["$set"]
    assert fields["enabled"] is False
    assert fields["disabled_by"] == "user-1"
    assert fields["disabled_at"] is not None
    clear_cache.assert_awaited_once_with("node", "builtin-1")
    assert response.code == 0
