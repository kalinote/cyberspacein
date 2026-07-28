from __future__ import annotations

from collections.abc import Iterable
from datetime import datetime
from typing import Any

from app.models.action.configs import ActionNodesHandleConfigModel
from app.models.action.node import (
    ActionNodeHandleModel,
    ActionNodeInputModel,
    ActionNodeModel,
)
from app.schemas.action.execution import NodeExecutionSpec
from app.schemas.constants import (
    ActionExecutionDriverEnum,
    ActionNodeDefinitionOriginEnum,
    ActionNodeKindEnum,
)
from app.service.native_nodes.contracts import (
    BackendNativeNodeDefinition,
    NativeNodeHandler,
)
from app.utils.dict_helper import pack_dict
from app.utils.id_lib import generate_id


class NativeHandlerRegistry:
    """按 Handler 键和业务 Schema 版本保存可信实现。"""

    def __init__(self):
        self._handlers: dict[tuple[str, int], NativeNodeHandler] = {}

    def register(
        self,
        key: str,
        handler: NativeNodeHandler,
        *,
        schema_versions: Iterable[int] = (1,),
    ) -> None:
        for version in schema_versions:
            registry_key = (key, version)
            current = self._handlers.get(registry_key)
            if current is not None and current is not handler:
                raise ValueError(f"原生节点 Handler 重复注册: {key}@{version}")
            self._handlers[registry_key] = handler

    def require(self, key: str, schema_version: int) -> NativeNodeHandler:
        handler = self._handlers.get((key, schema_version))
        if handler is None:
            raise ValueError(f"原生节点 Handler 未注册或版本不兼容: {key}@{schema_version}")
        return handler


class BackendNativeDefinitionRegistry:
    """保存原生节点权威定义并同步只读资源投影。"""

    def __init__(self):
        self._definitions: dict[tuple[str, int], BackendNativeNodeDefinition] = {}

    def register(self, definition: BackendNativeNodeDefinition) -> None:
        from app.service.native_nodes.compiler_registry import compiler_adapters
        from app.service.native_nodes.policy_registry import execution_policies

        native_handlers.require(
            definition.handler,
            definition.handler_schema_version,
        )
        compiler_adapters.require(
            definition.extension.compiler_adapter,
            definition.extension.contract_version,
        )
        execution_policies.require(
            definition.extension.execution_policy,
            definition.extension.contract_version,
        )
        registry_key = (definition.builtin_key, definition.definition_version)
        current = self._definitions.get(registry_key)
        if current is not None and current != definition:
            raise ValueError(
                f"原生节点定义重复注册且内容不一致: "
                f"{definition.builtin_key}@{definition.definition_version}"
            )
        self._definitions[registry_key] = definition

    def all(self) -> list[BackendNativeNodeDefinition]:
        return list(self._definitions.values())

    def require(
        self,
        builtin_key: str,
        definition_version: int | None = None,
    ) -> BackendNativeNodeDefinition:
        if definition_version is not None:
            definition = self._definitions.get((builtin_key, definition_version))
        else:
            candidates = [
                item
                for (key, _), item in self._definitions.items()
                if key == builtin_key
            ]
            definition = max(
                candidates,
                key=lambda item: item.definition_version,
                default=None,
            )
        if definition is None:
            suffix = f"@{definition_version}" if definition_version else ""
            raise ValueError(f"后端原生节点定义未注册: {builtin_key}{suffix}")
        return definition

    async def sync_projections(self) -> list[ActionNodeModel]:
        """幂等同步数据库投影，并保留管理员启用状态。"""
        projections = []
        latest_versions: dict[str, int] = {}
        for definition in self._definitions.values():
            latest_versions[definition.builtin_key] = max(
                latest_versions.get(definition.builtin_key, 0),
                definition.definition_version,
            )

        for definition in self._definitions.values():
            for handle in definition.handles:
                handle_model = await ActionNodesHandleConfigModel.find_one(
                    {"_id": handle.port_id}
                )
                handle_fields = {
                    "handle_name": handle.handle_name,
                    "type": handle.data_type,
                    "label": handle.label,
                    "color": handle.color,
                    "other_compatible_interfaces": handle.other_compatible_interfaces,
                    "custom_style": [],
                }
                if handle_model is None:
                    handle_model = ActionNodesHandleConfigModel(
                        id=handle.port_id,
                        **handle_fields,
                    )
                    await handle_model.insert()
                else:
                    await handle_model.update({"$set": handle_fields})

            node_id = generate_id(
                f"backend_builtin:{definition.builtin_key}:"
                f"{definition.definition_version}"
            )
            existing = await ActionNodeModel.find_one({"_id": node_id})
            handles = [
                ActionNodeHandleModel(
                    id=handle.port_id,
                    port_id=handle.port_id,
                    handle_config_id=handle.port_id,
                    interface_type_id=handle.interface_type_id,
                    compatible_interface_type_ids=(
                        handle.other_compatible_interfaces
                    ),
                    relabel=handle.label,
                    handle_name=handle.handle_name,
                    data_type=handle.data_type,
                    label=handle.label,
                    color=handle.color,
                    type=handle.direction,
                    position=handle.position,
                )
                for handle in definition.handles
            ]
            inputs = [
                ActionNodeInputModel(
                    id=item.id,
                    name=item.name,
                    type=item.type,
                    position=item.position,
                    label=item.label,
                    description=item.description,
                    required=item.required,
                    default=item.default,
                    options=item.options,
                    custom_style=pack_dict(item.custom_style),
                    custom_props=pack_dict(item.custom_props),
                )
                for item in definition.instance_input_schema
            ]
            definition_fields: dict[str, Any] = {
                "name": definition.name,
                "description": definition.description,
                "type": definition.category,
                "category": definition.category,
                "node_kind": ActionNodeKindEnum.BACKEND_NATIVE,
                "execution": NodeExecutionSpec(
                    driver=ActionExecutionDriverEnum.BACKEND_NATIVE,
                    handler=definition.handler,
                    schema_version=definition.handler_schema_version,
                ),
                "extension": definition.extension,
                "definition_origin": ActionNodeDefinitionOriginEnum.BACKEND_BUILTIN,
                "builtin_key": definition.builtin_key,
                "definition_version": definition.definition_version,
                "version": str(definition.definition_version),
                "handles": handles,
                "inputs": inputs,
                "default_configs": [],
                "related_components": [],
                "component_timeouts": {},
                "is_latest": (
                    latest_versions[definition.builtin_key]
                    == definition.definition_version
                ),
                "is_deleted": False,
                "updated_at": datetime.now(),
            }
            if existing is None:
                existing = ActionNodeModel(
                    id=node_id,
                    enabled=True,
                    **definition_fields,
                )
                await existing.insert()
            else:
                await existing.update({"$set": definition_fields})
                existing = await ActionNodeModel.find_one({"_id": node_id})
            projections.append(existing)
        return projections


native_handlers = NativeHandlerRegistry()
native_definitions = BackendNativeDefinitionRegistry()
