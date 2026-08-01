from __future__ import annotations

from collections.abc import Iterable
from typing import Any, Protocol

from pydantic import BaseModel, Field

from app.models.action.blueprint import GraphEdgeModel, GraphModel, GraphNodeModel
from app.models.action.node import ActionNodeModel
from app.schemas.action.interface import BlueprintInterfacePort
from app.schemas.constants import ActionInvocationModeEnum
from app.utils.dict_helper import unpack_dict


class CompilerContext(BaseModel):
    """Compiler Adapter 可读取的不可变编译上下文。"""

    graph: GraphModel
    invocation_mode: ActionInvocationModeEnum
    debug: bool = False
    definitions: dict[str, ActionNodeModel]

    model_config = {"arbitrary_types_allowed": True}


class CompilerMutation(BaseModel):
    """Compiler Adapter 返回的声明式图变更。"""

    skip_nodes: dict[str, str] = Field(default_factory=dict)
    remove_edge_ids: set[str] = Field(default_factory=set)
    add_edges: list[GraphEdgeModel] = Field(default_factory=list)
    interface_ports: list[BlueprintInterfacePort] = Field(default_factory=list)
    node_extension: dict[str, Any] = Field(default_factory=dict)


class CompilerAdapter(Protocol):
    """原生节点编译适配协议。"""

    def transform(
        self,
        context: CompilerContext,
        node: GraphNodeModel,
        definition: ActionNodeModel,
    ) -> CompilerMutation:
        ...


class CompilerAdapterRegistry:
    """按注册键和契约版本保存编译适配器。"""

    def __init__(self):
        self._adapters: dict[tuple[str, int], CompilerAdapter] = {}

    def register(
        self,
        key: str,
        adapter: CompilerAdapter,
        *,
        contract_versions: Iterable[int] = (1,),
    ) -> None:
        for version in contract_versions:
            registry_key = (key, version)
            current = self._adapters.get(registry_key)
            if current is not None and current is not adapter:
                raise ValueError(f"Compiler Adapter 重复注册: {key}@{version}")
            self._adapters[registry_key] = adapter

    def require(self, key: str, contract_version: int) -> CompilerAdapter:
        adapter = self._adapters.get((key, contract_version))
        if adapter is None:
            raise ValueError(
                f"Compiler Adapter 未注册或版本不兼容: {key}@{contract_version}"
            )
        return adapter


class DefaultCompilerAdapter:
    """保持普通 DAG 拓扑不变。"""

    def transform(
        self,
        context: CompilerContext,
        node: GraphNodeModel,
        definition: ActionNodeModel,
    ) -> CompilerMutation:
        return CompilerMutation()


class DebugOnlyCompilerAdapter:
    """仅在调试运行中保留节点。"""

    def transform(
        self,
        context: CompilerContext,
        node: GraphNodeModel,
        definition: ActionNodeModel,
    ) -> CompilerMutation:
        """普通运行时移除调试节点及关联边。"""
        if context.debug:
            return CompilerMutation()
        return CompilerMutation(
            skip_nodes={node.id: "调试节点仅在调试运行中启用"},
            remove_edge_ids={
                edge.id
                for edge in context.graph.edges
                if edge.source == node.id or edge.target == node.id
            },
        )


class BoundaryCompilerAdapter:
    """根据调用模式编译输入或输出边界节点。"""

    def __init__(self, direction: str):
        self.direction = direction

    def transform(
        self,
        context: CompilerContext,
        node: GraphNodeModel,
        definition: ActionNodeModel,
    ) -> CompilerMutation:
        """按重连后的相邻端口生成公开IO接口和执行图变更。"""
        instance_config = {
            **(unpack_dict(node.data.form_data) or {}),
            **node.data.instance_config,
        }
        interface_name = str(instance_config.get("interface_name") or "").strip()
        if not interface_name:
            raise ValueError(f"边界节点 {node.id} 的 interface_name 不能为空")
        interface_port_id = node.data.interface_port_id
        if not interface_port_id:
            raise ValueError(f"边界节点 {node.id} 缺少稳定 interface_port_id")

        handle = next(
            (
                item
                for item in definition.handles
                if item.type == ("source" if self.direction == "input" else "target")
            ),
            None,
        )
        if handle is None:
            raise ValueError(f"边界节点 {node.id} 缺少 {self.direction} 方向端口")
        mutation = CompilerMutation(
            node_extension={
                "boundary": {
                    "direction": self.direction,
                    "interface_port_id": interface_port_id,
                    "interface_name": interface_name,
                }
            }
        )

        incident_edges = [
            edge
            for edge in context.graph.edges
            if edge.source == node.id or edge.target == node.id
        ]
        binding = node.data.boundary_binding
        target = None
        target_handles = {}
        target_edges = []
        mapped_target_ports = set()
        exposed_handles = []
        if binding is not None:
            target = next(
                (
                    item
                    for item in context.graph.nodes
                    if item.id == binding.bound_node_id
                ),
                None,
            )
            if target is None:
                raise ValueError(f"边界节点 {node.id} 绑定的目标节点不存在")
            target_definition = context.definitions.get(target.data.definition_id)
            if target_definition is None:
                raise ValueError(f"边界节点 {node.id} 绑定的目标定义不存在")
            target_adapter = getattr(
                getattr(target_definition, "extension", None),
                "compiler_adapter",
                "default",
            )
            if target_adapter in {"blueprint.input", "blueprint.output"}:
                raise ValueError("输入输出边界节点不能绑定另一个边界节点")

            expected_direction = (
                "source" if self.direction == "input" else "target"
            )
            for item in target_definition.handles:
                if item.type != expected_direction:
                    continue
                target_handles[item.id] = item
                if item.port_id:
                    target_handles[item.port_id] = item
            if not binding.port_mappings:
                raise ValueError(f"边界节点 {node.id} 必须至少映射一个目标端口")
            target_port_ids = []
            for mapping in binding.port_mappings:
                if mapping.interface_port_id != interface_port_id:
                    raise ValueError(
                        f"边界节点 {node.id} 的映射引用了其他公开端口"
                    )
                target_handle = target_handles.get(mapping.target_port_id)
                if target_handle is None:
                    raise ValueError(
                        f"边界节点 {node.id} 映射的目标端口不存在或方向错误: "
                        f"{mapping.target_port_id}"
                    )
                target_port_ids.append(target_handle.port_id or target_handle.id)
                mapped_target_ports.add(target_handle.id)
                if target_handle.port_id:
                    mapped_target_ports.add(target_handle.port_id)
            if len(target_port_ids) != len(set(target_port_ids)):
                raise ValueError(f"边界节点 {node.id} 包含重复目标端口映射")
            mutation.node_extension["boundary"].update(
                {
                    "bound_node_id": target.id,
                    "target_port_ids": target_port_ids,
                }
            )
            target_edges = [
                edge
                for edge in context.graph.edges
                if edge.source == target.id or edge.target == target.id
            ]
            for edge in target_edges:
                source_port_id = edge.source_port_id or edge.sourceHandle
                target_port_id = edge.target_port_id or edge.targetHandle
                adjacent_node_id = None
                adjacent_port_id = None
                adjacent_direction = None
                if (
                    self.direction == "input"
                    and edge.source == target.id
                    and source_port_id in mapped_target_ports
                ):
                    adjacent_node_id = edge.target
                    adjacent_port_id = target_port_id
                    adjacent_direction = "target"
                elif (
                    self.direction == "output"
                    and edge.target == target.id
                    and target_port_id in mapped_target_ports
                ):
                    adjacent_node_id = edge.source
                    adjacent_port_id = source_port_id
                    adjacent_direction = "source"
                if adjacent_node_id is None:
                    continue
                adjacent_node = next(
                    (
                        item
                        for item in context.graph.nodes
                        if item.id == adjacent_node_id
                    ),
                    None,
                )
                adjacent_definition = (
                    context.definitions.get(adjacent_node.data.definition_id)
                    if adjacent_node
                    else None
                )
                adjacent_handle = next(
                    (
                        item
                        for item in adjacent_definition.handles
                        if item.type == adjacent_direction
                        and adjacent_port_id in {item.id, item.port_id}
                    ),
                    None,
                ) if adjacent_definition else None
                if adjacent_handle is not None:
                    exposed_handles.append(adjacent_handle)
            if not exposed_handles:
                raise ValueError(
                    f"边界节点 {node.id} 没有可继承的相邻Handle"
                )
        else:
            for edge in incident_edges:
                adjacent_node_id = None
                adjacent_port_id = None
                adjacent_direction = None
                if self.direction == "input" and edge.source == node.id:
                    adjacent_node_id = edge.target
                    adjacent_port_id = edge.target_port_id or edge.targetHandle
                    adjacent_direction = "target"
                elif self.direction == "output" and edge.target == node.id:
                    adjacent_node_id = edge.source
                    adjacent_port_id = edge.source_port_id or edge.sourceHandle
                    adjacent_direction = "source"
                if adjacent_node_id is None:
                    continue
                adjacent_node = next(
                    (
                        item
                        for item in context.graph.nodes
                        if item.id == adjacent_node_id
                    ),
                    None,
                )
                adjacent_definition = (
                    context.definitions.get(adjacent_node.data.definition_id)
                    if adjacent_node
                    else None
                )
                adjacent_handle = next(
                    (
                        item
                        for item in adjacent_definition.handles
                        if item.type == adjacent_direction
                        and adjacent_port_id in {item.id, item.port_id}
                    ),
                    None,
                ) if adjacent_definition else None
                if adjacent_handle is not None:
                    exposed_handles.append(adjacent_handle)

        selected_handle = instance_config.get("_interface_handle") or {}
        interface_type_id = (
            selected_handle.get("interface_type_id")
            or handle.interface_type_id
            or handle.id
        )
        handle_config_id = selected_handle.get("handle_config_id")
        data_type = selected_handle.get("data_type") or "value"
        color = selected_handle.get("color") or handle.color
        compatible_interface_type_ids = list(
            selected_handle.get("compatible_interface_type_ids") or []
        )
        if exposed_handles:
            signatures = {
                (
                    item.handle_config_id or item.id,
                    item.interface_type_id or item.id,
                    (
                        item.data_type.value
                        if hasattr(item.data_type, "value")
                        else str(item.data_type or "value")
                    ),
                )
                for item in exposed_handles
            }
            if len(signatures) != 1:
                raise ValueError(
                    f"边界节点 {node.id} 重连后的相邻Handle类型不一致，"
                    "请拆分为多个IO节点"
                )
            exposed = exposed_handles[0]
            handle_config_id = exposed.handle_config_id or exposed.id
            interface_type_id = exposed.interface_type_id or exposed.id
            data_type = (
                exposed.data_type.value
                if hasattr(exposed.data_type, "value")
                else str(exposed.data_type or "value")
            )
            color = exposed.color
            compatible_interface_type_ids = sorted(
                {
                    interface_id
                    for item in exposed_handles
                    for interface_id in item.compatible_interface_type_ids
                }
            )
        mutation.interface_ports.append(
            BlueprintInterfacePort(
                id=interface_port_id,
                name=interface_name,
                label=interface_name,
                direction=self.direction,
                handle_config_id=handle_config_id,
                interface_type_id=interface_type_id,
                data_type=data_type,
                color=color,
                compatible_interface_type_ids=compatible_interface_type_ids,
                required=bool(instance_config.get("required", False)),
                description=instance_config.get("description"),
            )
        )
        mutation.node_extension["boundary"].update(
            {
                "public_handle_config_id": handle_config_id,
                "interface_type_id": interface_type_id,
                "data_type": data_type,
            }
        )

        if context.invocation_mode == ActionInvocationModeEnum.STANDALONE:
            mutation.skip_nodes[node.id] = "边界节点在蓝图独立运行时跳过"
            mutation.remove_edge_ids.update(edge.id for edge in incident_edges)
            return mutation
        if binding is None:
            return mutation

        mutation.skip_nodes[target.id] = f"由边界节点 {node.id} 替换"
        mutation.remove_edge_ids.update(edge.id for edge in target_edges)
        for edge in target_edges:
            source_port_id = edge.source_port_id or edge.sourceHandle
            target_port_id = edge.target_port_id or edge.targetHandle
            if (
                self.direction == "input"
                and edge.source == target.id
                and source_port_id in mapped_target_ports
            ):
                mutation.add_edges.append(
                    GraphEdgeModel(
                        id=f"boundary:{node.id}:{edge.id}",
                        source=node.id,
                        sourceHandle=handle.id,
                        source_port_id=handle.port_id or handle.id,
                        target=edge.target,
                        targetHandle=edge.targetHandle,
                        target_port_id=target_port_id,
                    )
                )
            elif (
                self.direction == "output"
                and edge.target == target.id
                and target_port_id in mapped_target_ports
            ):
                mutation.add_edges.append(
                    GraphEdgeModel(
                        id=f"boundary:{node.id}:{edge.id}",
                        source=edge.source,
                        sourceHandle=edge.sourceHandle,
                        source_port_id=source_port_id,
                        target=node.id,
                        targetHandle=handle.id,
                        target_port_id=handle.port_id or handle.id,
                    )
                )
        return mutation


compiler_adapters = CompilerAdapterRegistry()
compiler_adapters.register("default", DefaultCompilerAdapter())
compiler_adapters.register("debug.only", DebugOnlyCompilerAdapter())
compiler_adapters.register("blueprint.input", BoundaryCompilerAdapter("input"))
compiler_adapters.register("blueprint.output", BoundaryCompilerAdapter("output"))
