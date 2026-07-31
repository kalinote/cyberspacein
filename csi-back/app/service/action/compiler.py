"""行动蓝图编译服务。"""

from __future__ import annotations

from collections import defaultdict, deque

from app.models.action.blueprint import GraphEdgeModel, GraphModel
from app.models.action.configs import ActionNodesHandleConfigModel
from app.models.action.node import ActionNodeModel
from app.schemas.action.execution import (
    BlueprintExecutionPlan,
    ExecutionPlanEdge,
    ExecutionPlanNode,
    NodeDefinitionContract,
    SkippedNode,
)
from app.schemas.action.interface import BlueprintInterfaceSpec
from app.schemas.constants import ActionInvocationModeEnum
from app.schemas.constants import ActionExecutionDriverEnum
from app.schemas.constants import ActionNodeKindEnum
from app.service.boundary_binding_validator import validate_boundary_bindings
from app.service.native_nodes.compiler_registry import (
    CompilerContext,
    compiler_adapters,
)
from app.service.native_nodes.policy_registry import execution_policies
from app.service.native_nodes.registry import native_handlers
from app.utils.dict_helper import unpack_dict


class BlueprintCompiler:
    """把可编辑蓝图确定性编译为不可变执行计划。"""

    @staticmethod
    async def load_definitions(graph: GraphModel) -> dict[str, ActionNodeModel]:
        """一次性加载设计图引用的全部节点定义。"""
        definition_ids = {node.data.definition_id for node in graph.nodes}
        if not definition_ids:
            return {}
        definitions = await ActionNodeModel.find(
            {"_id": {"$in": sorted(definition_ids)}, "is_deleted": False}
        ).to_list()
        handle_ids = {
            handle.handle_config_id or handle.id
            for definition in definitions
            for handle in definition.handles
        }
        handle_configs = (
            await ActionNodesHandleConfigModel.find(
                {"_id": {"$in": sorted(handle_ids)}}
            ).to_list()
            if handle_ids
            else []
        )
        configs_by_id = {config.id: config for config in handle_configs}
        for definition in definitions:
            for handle in definition.handles:
                config = configs_by_id.get(handle.handle_config_id or handle.id)
                if config is None:
                    continue
                handle.handle_config_id = config.id
                handle.handle_name = handle.handle_name or config.handle_name
                handle.data_type = handle.data_type or config.type
                handle.label = handle.label or config.label
                handle.color = handle.color or config.color
                if not handle.compatible_interface_type_ids:
                    handle.compatible_interface_type_ids = list(
                        config.other_compatible_interfaces
                    )
        return {definition.id: definition for definition in definitions}

    @staticmethod
    async def hydrate_interface_handle_selections(
        graph: GraphModel,
        definitions: dict[str, ActionNodeModel],
    ) -> None:
        """用数据库中的动态Handle配置规范化独立IO节点选择。"""
        selected_ids = {
            str(node.data.instance_config.get("public_handle_config_id") or "")
            for node in graph.nodes
            if node.data.instance_config.get("public_handle_config_id")
        }
        if not selected_ids:
            return
        configs = await ActionNodesHandleConfigModel.find(
            {"_id": {"$in": sorted(selected_ids)}}
        ).to_list()
        configs_by_id = {config.id: config for config in configs}
        usage_nodes = await ActionNodeModel.find(
            {
                "is_deleted": False,
                "enabled": True,
                "node_kind": {"$ne": ActionNodeKindEnum.ENCAPSULATED},
            }
        ).to_list()
        usages = {}
        for usage_node in usage_nodes:
            if usage_node.builtin_key in {"blueprint.input", "blueprint.output"}:
                continue
            for handle in usage_node.handles:
                config_id = handle.handle_config_id or handle.id
                if config_id in selected_ids:
                    usages.setdefault((config_id, handle.type), []).append(handle)

        for node in graph.nodes:
            definition = definitions.get(node.data.definition_id)
            if definition is None or definition.builtin_key not in {
                "blueprint.input",
                "blueprint.output",
            }:
                continue
            selected_id = str(
                node.data.instance_config.get("public_handle_config_id") or ""
            )
            if not selected_id:
                node.data.instance_config.pop("_interface_handle", None)
                continue
            config = configs_by_id.get(selected_id)
            if config is None:
                raise ValueError(f"IO节点选择的Handle配置不存在: {selected_id}")
            direction = (
                "target"
                if definition.builtin_key == "blueprint.input"
                else "source"
            )
            matching_usages = usages.get((selected_id, direction), [])
            if not matching_usages:
                raise ValueError(
                    f"Handle配置 {config.label} 不能用于"
                    f"{'蓝图输入' if direction == 'target' else '蓝图输出'}"
                )
            interface_types = {
                usage.interface_type_id or config.id
                for usage in matching_usages
            }
            if len(interface_types) != 1:
                raise ValueError(
                    f"Handle配置 {config.label} 在该方向对应多个接口类型，"
                    "不能作为独立IO接口"
                )
            usage = matching_usages[0]
            node.data.instance_config["_interface_handle"] = {
                "handle_config_id": config.id,
                "interface_type_id": next(iter(interface_types)),
                "data_type": config.type.value,
                "label": config.label,
                "color": config.color,
                "compatible_interface_type_ids": sorted(
                    {
                        *config.other_compatible_interfaces,
                        *usage.compatible_interface_type_ids,
                    }
                ),
            }

    @staticmethod
    async def validate_encapsulated_dependencies(
        definitions: dict[str, ActionNodeModel],
        *,
        ancestors: set[str] | None = None,
        depth: int = 0,
    ) -> None:
        """递归校验封装依赖、禁用资源和最大嵌套深度。"""
        from app.models.action.blueprint_revision import ActionBlueprintRevisionModel
        from app.service.blueprint_revision import BlueprintRevisionService

        if depth > 8:
            raise ValueError("封装蓝图超过最大嵌套深度 8")
        ancestors = set(ancestors or set())
        for definition in definitions.values():
            if definition.node_kind != ActionNodeKindEnum.ENCAPSULATED:
                continue
            revision_id = definition.source_revision_id
            if not revision_id:
                raise ValueError(f"封装节点 {definition.name} 缺少源Revision")
            if revision_id in ancestors:
                raise ValueError("封装蓝图依赖不能形成递归环")
            revision = await ActionBlueprintRevisionModel.find_one(
                {"_id": revision_id, "is_active": True}
            )
            if revision is None:
                raise ValueError(f"封装节点引用的Revision不存在: {revision_id}")
            child_definitions = await (
                BlueprintRevisionService.load_revision_definitions(revision)
            )
            BlueprintCompiler.compile(
                revision.graph_snapshot,
                child_definitions,
                ActionInvocationModeEnum.SUBFLOW,
                revision_id=revision.id,
            )
            await BlueprintCompiler.validate_encapsulated_dependencies(
                child_definitions,
                ancestors={*ancestors, revision_id},
                depth=depth + 1,
            )

    @staticmethod
    def compile(
        graph: GraphModel,
        definitions: dict[str, ActionNodeModel],
        invocation_mode: ActionInvocationModeEnum | str,
        *,
        revision_id: str | None = None,
    ) -> BlueprintExecutionPlan:
        """校验设计图并调用注册适配器生成执行计划。"""
        invocation_mode = ActionInvocationModeEnum(invocation_mode)
        BlueprintCompiler._validate_graph_identity(graph)
        node_by_id = {node.id: node for node in graph.nodes}

        for node in graph.nodes:
            definition = definitions.get(node.data.definition_id)
            if definition is None:
                raise ValueError(
                    f"节点 {node.id} 引用的定义不存在: {node.data.definition_id}"
                )
            if not definition.enabled:
                raise ValueError(
                    f"节点 {node.id} 引用的资源已禁用: "
                    f"{definition.name}({definition.builtin_key or definition.id})"
                )
            NodeDefinitionContract(
                node_kind=definition.node_kind,
                execution=definition.execution,
                extension=definition.extension,
            )
            if definition.extension is not None:
                native_handlers.require(
                    definition.execution.handler,
                    definition.execution.schema_version,
                )
                execution_policies.require(
                    definition.extension.execution_policy,
                    definition.extension.contract_version,
                )

        BlueprintCompiler._validate_edges(graph, node_by_id, definitions)
        if revision_id is None:
            validate_boundary_bindings(graph, definitions)
        context = CompilerContext(
            graph=graph.model_copy(deep=True),
            invocation_mode=invocation_mode,
            definitions=definitions,
        )
        skipped: dict[str, str] = {}
        remove_edge_ids: set[str] = set()
        added_edges: dict[str, GraphEdgeModel] = {}
        interface_ports = []
        node_extensions: dict[str, dict] = {}
        binding_claims: set[tuple[str, str, str]] = set()

        for node in graph.nodes:
            definition = definitions[node.data.definition_id]
            extension = definition.extension
            if extension is None:
                adapter_key = "default"
                contract_version = 1
            else:
                adapter_key = extension.compiler_adapter
                contract_version = extension.contract_version
            mutation = compiler_adapters.require(
                adapter_key,
                contract_version,
            ).transform(context, node, definition)
            for node_id, reason in mutation.skip_nodes.items():
                if node_id not in node_by_id:
                    raise ValueError(f"编译适配器试图跳过不存在的节点: {node_id}")
                previous = skipped.get(node_id)
                if previous is not None:
                    if previous != reason:
                        skipped[node_id] = "由多个边界节点替换"
                    continue
                skipped[node_id] = reason
            remove_edge_ids.update(mutation.remove_edge_ids)
            for edge in mutation.add_edges:
                current = added_edges.get(edge.id)
                if current is not None and current != edge:
                    raise ValueError(f"编译适配器生成冲突的边: {edge.id}")
                added_edges[edge.id] = edge
            interface_ports.extend(mutation.interface_ports)
            if mutation.node_extension:
                node_extensions[node.id] = mutation.node_extension
                boundary = mutation.node_extension.get("boundary", {})
                direction = boundary.get("direction")
                bound_node_id = boundary.get("bound_node_id")
                for target_port_id in boundary.get("target_port_ids", []):
                    claim = (direction, bound_node_id, target_port_id)
                    if claim in binding_claims:
                        raise ValueError(
                            f"目标端口 {target_port_id} 被多个同方向边界重复替换"
                        )
                    binding_claims.add(claim)

        BlueprintCompiler._validate_interfaces(interface_ports)
        effective_node_ids = set(node_by_id) - set(skipped)
        effective_edges = [
            edge.model_copy(deep=True)
            for edge in graph.edges
            if edge.id not in remove_edge_ids
            and edge.source in effective_node_ids
            and edge.target in effective_node_ids
        ]
        effective_edges.extend(
            edge.model_copy(deep=True)
            for edge in added_edges.values()
            if edge.source in effective_node_ids and edge.target in effective_node_ids
        )
        BlueprintCompiler._validate_effective_edges(
            effective_edges,
            effective_node_ids,
        )
        in_degree = {node_id: 0 for node_id in effective_node_ids}
        out_degree = {node_id: 0 for node_id in effective_node_ids}
        for edge in effective_edges:
            in_degree[edge.target] += 1
            out_degree[edge.source] += 1
        BlueprintCompiler._validate_acyclic(effective_node_ids, effective_edges)

        plan_nodes = []
        for node in graph.nodes:
            if node.id not in effective_node_ids:
                continue
            definition = definitions[node.data.definition_id]
            instance_config = {
                **(unpack_dict(node.data.form_data) or {}),
                **node.data.instance_config,
            }
            if node.id in node_extensions:
                instance_config["_compiler"] = node_extensions[node.id]
            execution = definition.execution.model_copy(deep=True)
            if execution.driver == ActionExecutionDriverEnum.COMPONENT:
                execution.config = {
                    **execution.config,
                    "component": {
                        "component_ids": list(definition.related_components),
                        "component_timeouts": dict(definition.component_timeouts),
                        "command": definition.command,
                        "command_args": list(definition.command_args),
                    },
                }
            plan_nodes.append(
                ExecutionPlanNode(
                    id=node.id,
                    definition_id=definition.id,
                    definition_version=definition.definition_version,
                    node_kind=definition.node_kind,
                    execution=execution,
                    extension_spec=(
                        definition.extension.model_copy(deep=True)
                        if definition.extension
                        else None
                    ),
                    instance_config=instance_config,
                    effective_in_degree=in_degree[node.id],
                    effective_out_degree=out_degree[node.id],
                    extension_contract_version=(
                        definition.extension.contract_version
                        if definition.extension
                        else None
                    ),
                    extension=node_extensions.get(node.id, {}),
                )
            )
        interface = BlueprintInterfaceSpec(
            inputs=[port for port in interface_ports if port.direction == "input"],
            outputs=[port for port in interface_ports if port.direction == "output"],
        )
        interface_by_boundary_node = {
            node_id: next(
                (
                    port
                    for port in interface_ports
                    if port.id
                    == extension.get("boundary", {}).get("interface_port_id")
                ),
                None,
            )
            for node_id, extension in node_extensions.items()
            if extension.get("boundary")
        }
        plan_edges = []
        for edge in sorted(effective_edges, key=lambda item: item.id):
            data_type, source_contract, target_contract = (
                BlueprintCompiler._resolve_edge_contract(
                    edge,
                    node_by_id,
                    definitions,
                    interface_by_boundary_node,
                )
            )
            plan_edges.append(
                ExecutionPlanEdge(
                    id=edge.id,
                    source=edge.source,
                    source_port_id=edge.source_port_id or edge.sourceHandle,
                    source_handle_config_id=source_contract["handle_config_id"],
                    source_interface_type_id=source_contract["interface_type_id"],
                    target=edge.target,
                    target_port_id=edge.target_port_id or edge.targetHandle,
                    target_handle_config_id=target_contract["handle_config_id"],
                    target_interface_type_id=target_contract["interface_type_id"],
                    data_type=data_type,
                    reference_protocol="eos-v1",
                )
            )
        return BlueprintExecutionPlan(
            plan_schema_version=2,
            revision_id=revision_id,
            invocation_mode=invocation_mode,
            nodes=plan_nodes,
            edges=plan_edges,
            skipped_nodes=[
                SkippedNode(node_id=node_id, reason=reason)
                for node_id, reason in sorted(skipped.items())
            ],
            public_interface_snapshot=interface.model_dump(mode="python"),
        )

    @staticmethod
    def _resolve_edge_contract(
        edge: GraphEdgeModel,
        node_by_id: dict,
        definitions: dict[str, ActionNodeModel],
        interface_by_boundary_node: dict,
    ) -> tuple[str, dict[str, str | None], dict[str, str | None]]:
        """根据执行图两端的有效Handle冻结边传输与接口契约。"""
        endpoint_contracts = []
        for node_id, port_id, direction in (
            (
                edge.source,
                edge.source_port_id or edge.sourceHandle,
                "source",
            ),
            (
                edge.target,
                edge.target_port_id or edge.targetHandle,
                "target",
            ),
        ):
            interface_port = interface_by_boundary_node.get(node_id)
            if interface_port is not None:
                endpoint_contracts.append(
                    {
                        "data_type": interface_port.data_type,
                        "handle_config_id": interface_port.handle_config_id,
                        "interface_type_id": interface_port.interface_type_id,
                    }
                )
                continue
            definition = definitions[node_by_id[node_id].data.definition_id]
            handle = next(
                (
                    item
                    for item in definition.handles
                    if item.type == direction
                    and port_id in {item.id, item.port_id}
                ),
                None,
            )
            if handle is None:
                raise ValueError(f"边 {edge.id} 的有效端口不存在: {port_id}")
            handle_config_id = handle.handle_config_id or handle.id
            endpoint_contracts.append(
                {
                    "data_type": (
                        handle.data_type.value
                        if hasattr(handle.data_type, "value")
                        else str(handle.data_type or "value")
                    ),
                    "handle_config_id": handle_config_id,
                    "interface_type_id": (
                        handle.interface_type_id or handle_config_id
                    ),
                }
            )
        endpoint_types = {
            contract["data_type"] for contract in endpoint_contracts
        }
        if len(endpoint_types) != 1:
            raise ValueError(f"边 {edge.id} 的端口数据类型不一致")
        return (
            str(endpoint_contracts[0]["data_type"]),
            endpoint_contracts[0],
            endpoint_contracts[1],
        )

    @staticmethod
    def _validate_graph_identity(graph: GraphModel) -> None:
        node_ids = [node.id for node in graph.nodes]
        edge_ids = [edge.id for edge in graph.edges]
        if len(node_ids) != len(set(node_ids)):
            raise ValueError("蓝图节点ID必须唯一")
        if len(edge_ids) != len(set(edge_ids)):
            raise ValueError("蓝图边ID必须唯一")

    @staticmethod
    def _validate_edges(
        graph: GraphModel,
        node_by_id: dict,
        definitions: dict[str, ActionNodeModel],
    ) -> None:
        target_connections: set[tuple[str, str]] = set()
        for edge in graph.edges:
            if edge.source not in node_by_id or edge.target not in node_by_id:
                raise ValueError(f"边 {edge.id} 引用了不存在的节点")
            source_definition = definitions[
                node_by_id[edge.source].data.definition_id
            ]
            target_definition = definitions[
                node_by_id[edge.target].data.definition_id
            ]
            source_port = edge.source_port_id or edge.sourceHandle
            target_port = edge.target_port_id or edge.targetHandle
            source_handle = next(
                (
                    handle
                    for handle in source_definition.handles
                    if source_port in {handle.id, handle.port_id}
                ),
                None,
            )
            target_handle = next(
                (
                    handle
                    for handle in target_definition.handles
                    if target_port in {handle.id, handle.port_id}
                ),
                None,
            )
            if source_handle is None or source_handle.type != "source":
                raise ValueError(f"边 {edge.id} 的源端口不存在或方向错误")
            if target_handle is None or target_handle.type != "target":
                raise ValueError(f"边 {edge.id} 的目标端口不存在或方向错误")
            source_type = source_handle.interface_type_id
            target_type = target_handle.interface_type_id
            source_config = {
                **(unpack_dict(node_by_id[edge.source].data.form_data) or {}),
                **node_by_id[edge.source].data.instance_config,
            }
            target_config = {
                **(unpack_dict(node_by_id[edge.target].data.form_data) or {}),
                **node_by_id[edge.target].data.instance_config,
            }
            source_type = source_config.get("interface_type_id") or source_type
            target_type = target_config.get("interface_type_id") or target_type
            target_compatible = set(
                target_handle.compatible_interface_type_ids
            )
            source_compatible = set(
                source_handle.compatible_interface_type_ids
            )
            if (
                source_type
                and target_type
                and source_type != target_type
                and "*" not in target_compatible
                and "*" not in source_compatible
                and source_type not in target_compatible
                and target_type not in source_compatible
            ):
                raise ValueError(f"边 {edge.id} 的端口接口类型不兼容")
            target_key = (edge.target, target_port)
            allow_multiple_inputs = bool(
                (
                    target_definition.extension.config.get("compiler", {})
                    if target_definition.extension
                    else {}
                ).get("allow_multiple_inputs", False)
            )
            if target_key in target_connections and not allow_multiple_inputs:
                raise ValueError(f"目标端口 {target_port} 只能连接一个上游")
            target_connections.add(target_key)

    @staticmethod
    def _validate_interfaces(interface_ports: list) -> None:
        ids = [port.id for port in interface_ports]
        if len(ids) != len(set(ids)):
            raise ValueError("蓝图公开端口ID必须唯一")
        for direction in ("input", "output"):
            names = [
                port.name
                for port in interface_ports
                if port.direction == direction
            ]
            if len(names) != len(set(names)):
                raise ValueError(f"蓝图{direction}接口名称必须唯一")

    @staticmethod
    def _validate_effective_edges(
        edges: list[GraphEdgeModel],
        node_ids: set[str],
    ) -> None:
        edge_ids = set()
        for edge in edges:
            if edge.id in edge_ids:
                raise ValueError(f"执行图边ID重复: {edge.id}")
            edge_ids.add(edge.id)
            if edge.source not in node_ids or edge.target not in node_ids:
                raise ValueError(f"执行图存在悬空边: {edge.id}")

    @staticmethod
    def _validate_acyclic(
        node_ids: set[str],
        edges: list[GraphEdgeModel],
    ) -> None:
        adjacency: dict[str, list[str]] = defaultdict(list)
        in_degree = {node_id: 0 for node_id in node_ids}
        for edge in edges:
            adjacency[edge.source].append(edge.target)
            in_degree[edge.target] += 1
        queue = deque(sorted(node_id for node_id, degree in in_degree.items() if degree == 0))
        visited = 0
        while queue:
            node_id = queue.popleft()
            visited += 1
            for target in adjacency[node_id]:
                in_degree[target] -= 1
                if in_degree[target] == 0:
                    queue.append(target)
        if visited != len(node_ids):
            raise ValueError("蓝图执行图不能包含循环依赖")
