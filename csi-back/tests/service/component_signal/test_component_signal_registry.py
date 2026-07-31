import pytest

from app.schemas.alert.constants import (
    AlertEvaluationModeEnum,
    AlertOperatorEnum,
    AlertValueTypeEnum,
)
from app.schemas.component_signal import (
    ComponentSignalDefinition,
    ComponentSignalResourceRef,
    ResolvedComponentSignalResource,
)
from app.service.component_signal.definitions import (
    register_builtin_component_signals,
)
from app.service.component_signal.registry import ComponentSignalDefinitionRegistry


def definition(
    *,
    definition_key: str = "test.health",
    field_key: str = "health",
    component_ids: set[str] | None = None,
) -> ComponentSignalDefinition:
    """构造测试组件信号定义。"""
    return ComponentSignalDefinition(
        definition_key=definition_key,
        source_key="test.component",
        module_key="test",
        module_name="测试组件",
        resource_type="test_resource",
        resource_name="测试资源",
        field_key=field_key,
        field_name=field_key,
        signal_key=f"{field_key}_signal",
        value_type=AlertValueTypeEnum.BOOLEAN,
        supported_operators=[
            AlertOperatorEnum.EQ,
            AlertOperatorEnum.NE,
        ],
        supported_evaluation_modes=[
            AlertEvaluationModeEnum.REALTIME,
            AlertEvaluationModeEnum.HYBRID,
        ],
        allowed_component_ids=component_ids or {"component-a"},
    )


def test_registry_aggregates_definitions_into_alert_source() -> None:
    registry = ComponentSignalDefinitionRegistry()
    registry.register(definition())
    registry.register(
        definition(
            definition_key="test.ready",
            field_key="ready",
        )
    )

    descriptor = registry.get_source_descriptor("test.component")

    assert descriptor.source_key == "test.component"
    assert descriptor.resource_type == "test_resource"
    assert [item.field_key for item in descriptor.fields] == [
        "health",
        "ready",
    ]


def test_registry_rejects_duplicate_source_field() -> None:
    registry = ComponentSignalDefinitionRegistry()
    registry.register(definition())

    with pytest.raises(ValueError, match="字段已注册"):
        registry.register(
            definition(
                definition_key="test.health.v2",
                field_key="health",
            )
        )


def test_builtin_demo_signal_is_idempotent_and_generic() -> None:
    registry = ComponentSignalDefinitionRegistry()

    register_builtin_component_signals(registry)
    register_builtin_component_signals(registry)

    current = registry.get("component.demo.health")
    assert current.allowed_component_ids == {"*"}
    assert current.source_key == "component.demo"


@pytest.mark.asyncio
async def test_registry_uses_module_resource_resolver() -> None:
    registry = ComponentSignalDefinitionRegistry()

    async def resolve(context, resource):
        assert context == "component-context"
        return ResolvedComponentSignalResource(
            resource_id=f"resolved:{resource.resource_id}",
            resource_name="已解析资源",
            resource_url="/resource/resource-1",
        )

    registry.register(definition(), resource_resolver=resolve)

    resolved = await registry.resolve_resource(
        "test.health",
        "component-context",
        ComponentSignalResourceRef(resource_id="resource-1"),
    )

    assert resolved.resource_id == "resolved:resource-1"
    assert resolved.resource_url == "/resource/resource-1"
