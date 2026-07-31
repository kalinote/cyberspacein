import pytest
from pydantic import ValidationError

from app.models.action.blueprint import (
    GraphModel,
    GraphNodeModel,
    NodeDataModel,
    PositionModel,
    ViewportModel,
)
from app.models.action.node import ActionNodeModel
from app.schemas.action.execution import (
    MAX_EXTENSION_PAYLOAD_BYTES,
    NativeNodeExtensionSpec,
    NodeDefinitionContract,
    NodeExecutionContext,
    NodeExecutionOutcome,
    NodeExecutionSpec,
    NodeStartResult,
)
from app.schemas.constants import (
    ActionExecutionDriverEnum,
    ActionInvocationModeEnum,
    ActionNodeDefinitionOriginEnum,
    ActionNodeKindEnum,
)
from app.service.action.compiler import BlueprintCompiler
from app.service.native_nodes.compiler_registry import (
    CompilerMutation,
    compiler_adapters,
)
from app.service.native_nodes.contracts import BackendNativeNodeDefinition
from app.service.native_nodes.policy_registry import execution_policies
from app.service.native_nodes.registry import native_definitions, native_handlers
from app.service.node_executors.native import BackendNativeNodeExecutor
from app.service.node_executors.registry import NodeExecutorRegistry


class _FixtureHandler:
    async def start(self, context, spec):
        return NodeStartResult(
            state="completed",
            outputs={"result": context.inputs.get("value")},
            progress=100,
            extension_state={"checkpoint": "done"},
            extension_result={"contract_version": 1},
        )

    async def reconcile(self, provider_run_id, extension_state):
        return NodeExecutionOutcome(status="completed", progress=100)

    async def cancel(self, provider_run_id, reason, extension_state):
        return True


class _FixtureAdapter:
    def transform(self, context, node, definition):
        return CompilerMutation(
            node_extension={
                "fixture": {
                    "mode": context.invocation_mode.value,
                    "node_id": node.id,
                }
            }
        )


class _FixturePolicy:
    def is_ready(self, node, completed_dependencies):
        return completed_dependencies >= node.effective_in_degree

    def execution_keys(self, node):
        return ["left", "right"]


def test_node_kind_and_driver_mapping_is_closed() -> None:
    assert {item.value for item in ActionNodeKindEnum} == {
        "ordinary",
        "backend_native",
        "encapsulated",
    }
    with pytest.raises(ValidationError, match="只能使用 component"):
        NodeDefinitionContract(
            node_kind=ActionNodeKindEnum.ORDINARY,
            execution=NodeExecutionSpec(
                driver=ActionExecutionDriverEnum.BACKEND_NATIVE,
                handler="invalid",
            ),
        )
    with pytest.raises(ValidationError, match="必须提供扩展契约"):
        NodeDefinitionContract(
            node_kind=ActionNodeKindEnum.BACKEND_NATIVE,
            execution=NodeExecutionSpec(
                driver=ActionExecutionDriverEnum.BACKEND_NATIVE,
                handler="invalid",
            ),
        )


def test_unregistered_driver_and_contract_versions_fail_clearly() -> None:
    with pytest.raises(ValueError, match="节点执行器未注册"):
        NodeExecutorRegistry().require("missing")
    with pytest.raises(ValueError, match="Handler 未注册或版本不兼容"):
        native_handlers.require("missing.handler", 99)
    with pytest.raises(ValueError, match="Compiler Adapter 未注册或版本不兼容"):
        compiler_adapters.require("missing.adapter", 99)
    with pytest.raises(ValueError, match="Execution Policy 未注册或版本不兼容"):
        execution_policies.require("missing.policy", 99)


@pytest.mark.parametrize("result_type", [NodeStartResult, NodeExecutionOutcome])
def test_extension_payload_size_is_bounded(result_type) -> None:
    payload = {"value": "测" * MAX_EXTENSION_PAYLOAD_BYTES}

    with pytest.raises(ValidationError, match="节点扩展载荷超过"):
        if result_type is NodeStartResult:
            result_type(state="completed", extension_state=payload)
        else:
            result_type(status="completed", extension_state=payload)


@pytest.mark.asyncio
async def test_fixture_extension_uses_registered_protocols_end_to_end() -> None:
    handler_key = "test.fixture.handler"
    adapter_key = "test.fixture.adapter"
    policy_key = "test.fixture.policy"
    definition_key = "test.fixture.node"
    handler = _FixtureHandler()
    adapter = _FixtureAdapter()
    policy = _FixturePolicy()
    native_handlers.register(handler_key, handler)
    compiler_adapters.register(adapter_key, adapter)
    execution_policies.register(policy_key, policy)
    definition = BackendNativeNodeDefinition(
        builtin_key=definition_key,
        definition_version=1,
        name="扩展契约测试节点",
        description="仅用于测试注册式扩展",
        handler=handler_key,
        category="processor",
        extension=NativeNodeExtensionSpec(
            compiler_adapter=adapter_key,
            execution_policy=policy_key,
            renderer_key="schema",
        ),
    )
    native_definitions.register(definition)
    projection = ActionNodeModel.model_construct(
        id="definition-1",
        name=definition.name,
        description=definition.description,
        type=definition.category,
        category=definition.category,
        node_kind=ActionNodeKindEnum.BACKEND_NATIVE,
        execution=NodeExecutionSpec(
            driver=ActionExecutionDriverEnum.BACKEND_NATIVE,
            handler=handler_key,
        ),
        extension=definition.extension,
        definition_origin=ActionNodeDefinitionOriginEnum.BACKEND_BUILTIN,
        builtin_key=definition_key,
        version="1",
        handles=[],
        inputs=[],
        related_components=[],
    )
    graph = GraphModel(
        nodes=[
            GraphNodeModel(
                id="fixture-node",
                type="processor",
                position=PositionModel(x=0, y=0),
                data=NodeDataModel(
                    definition_id=projection.id,
                    version="1",
                    form_data=[],
                ),
            )
        ],
        edges=[],
        viewport=ViewportModel(x=0, y=0, zoom=1),
    )

    first = BlueprintCompiler.compile(
        graph,
        {projection.id: projection},
        ActionInvocationModeEnum.STANDALONE,
    )
    second = BlueprintCompiler.compile(
        graph,
        {projection.id: projection},
        ActionInvocationModeEnum.STANDALONE,
    )
    plan_node = first.nodes[0]

    assert first.model_dump(mode="json") == second.model_dump(mode="json")
    assert plan_node.extension == {
        "fixture": {"mode": "standalone", "node_id": "fixture-node"}
    }
    assert policy.execution_keys(plan_node) == ["left", "right"]
    restored = type(plan_node).model_validate(plan_node.model_dump(mode="python"))
    assert restored.extension_spec == definition.extension
    assert restored.extension == plan_node.extension

    result = await BackendNativeNodeExecutor(native_handlers).start(
        NodeExecutionContext(
            action_id="action-1",
            node_instance_id="instance-node-1",
            node_id="fixture-node",
            inputs={"value": 42},
        ),
        projection.execution,
    )

    assert result.state == "completed"
    assert result.outputs == {"result": 42}
    assert result.extension_state == {"checkpoint": "done"}
    assert result.extension_result == {"contract_version": 1}
