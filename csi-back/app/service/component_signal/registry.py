from collections.abc import Awaitable, Callable
from typing import Any

from app.schemas.alert.source import AlertSourceDescriptor
from app.schemas.component_signal import (
    ComponentSignalDefinition,
    ComponentSignalResourceRef,
    ResolvedComponentSignalResource,
)

ComponentSignalResourceResolver = Callable[
    [Any, ComponentSignalResourceRef],
    Awaitable[ResolvedComponentSignalResource],
]


class ComponentSignalDefinitionRegistry:
    """维护服务端允许组件上报的受控信号定义。"""

    def __init__(self) -> None:
        self._definitions: dict[str, ComponentSignalDefinition] = {}
        self._resource_resolvers: dict[
            str,
            ComponentSignalResourceResolver,
        ] = {}

    def register(
        self,
        definition: ComponentSignalDefinition,
        *,
        resource_resolver: ComponentSignalResourceResolver | None = None,
    ) -> None:
        """注册定义并拒绝键冲突或告警源契约冲突。"""
        existing = self._definitions.get(definition.definition_key)
        if existing is not None:
            if (
                existing == definition
                and self._resource_resolvers.get(definition.definition_key)
                is resource_resolver
            ):
                return
            raise ValueError(f"组件信号定义已注册: {definition.definition_key}")
        for registered in self._definitions.values():
            if registered.source_key != definition.source_key:
                continue
            if (
                registered.module_key != definition.module_key
                or registered.module_name != definition.module_name
                or registered.resource_type != definition.resource_type
                or registered.resource_name != definition.resource_name
                or registered.source_schema_version
                != definition.source_schema_version
            ):
                raise ValueError(
                    f"组件信号告警源契约不一致: {definition.source_key}"
                )
            if registered.field_key == definition.field_key:
                raise ValueError(
                    f"组件信号字段已注册: {definition.source_key}.{definition.field_key}"
                )
        self._definitions[definition.definition_key] = definition
        if resource_resolver is not None:
            self._resource_resolvers[definition.definition_key] = resource_resolver

    def get(self, definition_key: str) -> ComponentSignalDefinition:
        """读取指定组件信号定义。"""
        definition = self._definitions.get(definition_key)
        if definition is None:
            raise KeyError(f"组件信号定义未注册: {definition_key}")
        return definition

    def list_definitions(self) -> list[ComponentSignalDefinition]:
        """按稳定键返回全部组件信号定义。"""
        return [
            self._definitions[key]
            for key in sorted(self._definitions)
        ]

    def list_source_keys(self) -> list[str]:
        """按稳定键返回定义产生的告警源。"""
        return sorted({item.source_key for item in self._definitions.values()})

    def get_source_descriptor(self, source_key: str) -> AlertSourceDescriptor:
        """聚合同一告警源下的组件信号字段。"""
        definitions = [
            item
            for item in self.list_definitions()
            if item.source_key == source_key
        ]
        if not definitions:
            raise KeyError(f"组件信号告警源未注册: {source_key}")
        first = definitions[0]
        modes = []
        for definition in definitions:
            for mode in definition.supported_evaluation_modes:
                if mode not in modes:
                    modes.append(mode)
        return AlertSourceDescriptor(
            source_key=source_key,
            module_key=first.module_key,
            module_name=first.module_name,
            resource_type=first.resource_type,
            resource_name=first.resource_name,
            schema_version=first.source_schema_version,
            fields=[
                item.to_field_descriptor()
                for item in sorted(definitions, key=lambda value: value.field_key)
            ],
            supported_evaluation_modes=modes,
        )

    async def resolve_resource(
        self,
        definition_key: str,
        context: Any,
        resource: ComponentSignalResourceRef,
    ) -> ResolvedComponentSignalResource:
        """通过模块注册的解析器校验资源并生成服务端地址。"""
        self.get(definition_key)
        resolver = self._resource_resolvers.get(definition_key)
        if resolver is None:
            return ResolvedComponentSignalResource(
                resource_id=resource.resource_id,
                resource_name=resource.resource_name,
            )
        return ResolvedComponentSignalResource.model_validate(
            await resolver(context, resource)
        )

    def clear(self) -> None:
        """清空注册表，仅供测试隔离。"""
        self._definitions.clear()
        self._resource_resolvers.clear()


component_signal_definition_registry = ComponentSignalDefinitionRegistry()
