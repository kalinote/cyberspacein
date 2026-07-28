from __future__ import annotations

from collections import defaultdict
from typing import Any

from app.models.action.blueprint import GraphModel
from app.models.action.node import ActionNodeModel
from app.schemas.action.interface import BlueprintValidationIssue
from app.utils.dict_helper import unpack_dict


_BOUNDARY_DIRECTION_BY_ADAPTER = {
    "blueprint.input": "input",
    "blueprint.output": "output",
}


class BlueprintBindingValidationError(ValueError):
    """携带全部结构化问题的蓝图绑定校验异常。"""

    def __init__(self, issues: list[BlueprintValidationIssue]):
        self.issues = issues
        message = issues[0].message if issues else "蓝图绑定校验失败"
        super().__init__(message)


def validate_boundary_bindings(
    graph: GraphModel,
    definitions: dict[str, ActionNodeModel],
) -> None:
    """整体校验 IO 绑定声明、目标角色和可替换端口覆盖。"""
    issues: list[BlueprintValidationIssue] = []

    def add_issue(
        code: str,
        message: str,
        *,
        node_id: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        """追加一条带上下文的绑定校验问题。"""
        issues.append(
            BlueprintValidationIssue(
                code=code,
                message=message,
                node_id=node_id,
                details=details or {},
            )
        )

    node_by_id = {node.id: node for node in graph.nodes}
    direction_by_node_id: dict[str, str] = {}
    for node in graph.nodes:
        definition = definitions.get(node.data.definition_id)
        adapter = getattr(
            getattr(definition, "extension", None),
            "compiler_adapter",
            "default",
        )
        direction = _BOUNDARY_DIRECTION_BY_ADAPTER.get(adapter)
        if direction:
            direction_by_node_id[node.id] = direction

    incoming_edges: dict[str, list] = defaultdict(list)
    outgoing_edges: dict[str, list] = defaultdict(list)
    for edge in graph.edges:
        incoming_edges[edge.target].append(edge)
        outgoing_edges[edge.source].append(edge)

    claims_by_target: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for node in graph.nodes:
        direction = direction_by_node_id.get(node.id)
        if direction is None:
            continue
        definition = definitions.get(node.data.definition_id)
        if definition is None:
            continue
        instance_config = {
            **(unpack_dict(node.data.form_data) or {}),
            **node.data.instance_config,
        }
        interface_name = str(instance_config.get("interface_name") or "").strip()
        if not interface_name:
            add_issue(
                "binding_interface_invalid",
                f"边界节点 {node.id} 的 interface_name 不能为空",
                node_id=node.id,
            )
        interface_port_id = node.data.interface_port_id
        if not interface_port_id:
            add_issue(
                "binding_interface_invalid",
                f"边界节点 {node.id} 缺少稳定 interface_port_id",
                node_id=node.id,
            )

        boundary_handle = next(
            (
                handle
                for handle in definition.handles
                if handle.type == ("source" if direction == "input" else "target")
            ),
            None,
        )
        if boundary_handle is None:
            add_issue(
                "binding_interface_invalid",
                f"边界节点 {node.id} 缺少 {direction} 方向端口",
                node_id=node.id,
            )
            continue

        binding = node.data.boundary_binding
        if binding is None:
            continue
        incident_edges = [
            *incoming_edges.get(node.id, []),
            *outgoing_edges.get(node.id, []),
        ]
        if incident_edges:
            add_issue(
                "binding_boundary_has_data_edge",
                f"已绑定边界节点 {node.id} 不能保留普通数据边",
                node_id=node.id,
                details={
                    "edge_ids": sorted({edge.id for edge in incident_edges}),
                },
            )

        target = node_by_id.get(binding.bound_node_id)
        if target is None:
            add_issue(
                "binding_target_not_found",
                f"边界节点 {node.id} 绑定的目标节点不存在",
                node_id=node.id,
                details={"target_node_id": binding.bound_node_id},
            )
            continue
        if target.id in direction_by_node_id:
            add_issue(
                "binding_target_is_boundary",
                "输入输出边界节点不能绑定另一个边界节点",
                node_id=node.id,
                details={"target_node_id": target.id},
            )
            continue
        target_definition = definitions.get(target.data.definition_id)
        if target_definition is None:
            add_issue(
                "binding_target_not_found",
                f"边界节点 {node.id} 绑定的目标定义不存在",
                node_id=node.id,
                details={"target_node_id": target.id},
            )
            continue
        if not binding.port_mappings:
            add_issue(
                "binding_empty_mapping",
                f"边界节点 {node.id} 必须至少映射一个目标端口",
                node_id=node.id,
                details={"target_node_id": target.id},
            )
            continue

        expected_direction = "source" if direction == "input" else "target"
        target_handles = {}
        for handle in target_definition.handles:
            if handle.type != expected_direction:
                continue
            target_handles[handle.id] = handle
            if handle.port_id:
                target_handles[handle.port_id] = handle

        target_port_ids = []
        for mapping in binding.port_mappings:
            if mapping.interface_port_id != interface_port_id:
                add_issue(
                    "binding_interface_invalid",
                    f"边界节点 {node.id} 的映射引用了其他公开端口",
                    node_id=node.id,
                    details={
                        "target_node_id": target.id,
                        "target_port_id": mapping.target_port_id,
                    },
                )
                continue
            target_handle = target_handles.get(mapping.target_port_id)
            if target_handle is None:
                add_issue(
                    "binding_port_direction_invalid",
                    (
                        f"边界节点 {node.id} 映射的目标端口不存在或方向错误: "
                        f"{mapping.target_port_id}"
                    ),
                    node_id=node.id,
                    details={
                        "target_node_id": target.id,
                        "target_port_id": mapping.target_port_id,
                    },
                )
                continue
            target_port_ids.append(target_handle.port_id or target_handle.id)

        if len(target_port_ids) != len(set(target_port_ids)):
            add_issue(
                "binding_duplicate_target_port",
                f"边界节点 {node.id} 包含重复目标端口映射",
                node_id=node.id,
                details={"target_node_id": target.id},
            )
        if target_port_ids:
            claims_by_target[target.id].append(
                {
                    "boundary_node_id": node.id,
                    "direction": direction,
                    "target_port_ids": set(target_port_ids),
                    "target_definition": target_definition,
                }
            )

    for target_id, claims in claims_by_target.items():
        directions = {claim["direction"] for claim in claims}
        boundary_node_ids = sorted(
            claim["boundary_node_id"] for claim in claims
        )
        if len(directions) > 1:
            add_issue(
                "binding_mixed_direction",
                f"节点 {target_id} 不能同时绑定蓝图输入和蓝图输出",
                node_id=boundary_node_ids[0],
                details={
                    "target_node_id": target_id,
                    "related_boundary_node_ids": boundary_node_ids,
                },
            )

        occupied_ports: set[tuple[str, str]] = set()
        for claim in claims:
            for target_port_id in sorted(claim["target_port_ids"]):
                key = (claim["direction"], target_port_id)
                if key in occupied_ports:
                    add_issue(
                        "binding_duplicate_target_port",
                        (
                            f"目标端口 {target_port_id} "
                            "被多个同方向边界重复替换"
                        ),
                        node_id=claim["boundary_node_id"],
                        details={
                            "target_node_id": target_id,
                            "target_port_id": target_port_id,
                            "direction": claim["direction"],
                        },
                    )
                occupied_ports.add(key)

        target_definition = claims[0]["target_definition"]
        handle_by_alias = {}
        for handle in target_definition.handles:
            canonical_port_id = handle.port_id or handle.id
            handle_by_alias[handle.id] = canonical_port_id
            if handle.port_id:
                handle_by_alias[handle.port_id] = canonical_port_id

        for direction in sorted(directions):
            direction_claims = [
                claim for claim in claims if claim["direction"] == direction
            ]
            mapped_ports = set().union(
                *(
                    claim["target_port_ids"]
                    for claim in direction_claims
                )
            )
            if direction == "input":
                if incoming_edges.get(target_id):
                    add_issue(
                        "binding_target_not_start",
                        f"输入绑定目标节点 {target_id} 必须是起始节点",
                        node_id=direction_claims[0]["boundary_node_id"],
                        details={"target_node_id": target_id},
                    )
                connected_ports = {
                    handle_by_alias.get(
                        edge.source_port_id or edge.sourceHandle,
                        edge.source_port_id or edge.sourceHandle,
                    )
                    for edge in outgoing_edges.get(target_id, [])
                }
            else:
                if outgoing_edges.get(target_id):
                    add_issue(
                        "binding_target_not_end",
                        f"输出绑定目标节点 {target_id} 必须是结束节点",
                        node_id=direction_claims[0]["boundary_node_id"],
                        details={"target_node_id": target_id},
                    )
                connected_ports = {
                    handle_by_alias.get(
                        edge.target_port_id or edge.targetHandle,
                        edge.target_port_id or edge.targetHandle,
                    )
                    for edge in incoming_edges.get(target_id, [])
                }

            for target_port_id in sorted(mapped_ports - connected_ports):
                add_issue(
                    "binding_port_not_connected",
                    f"目标端口 {target_port_id} 没有可替换的普通数据边",
                    node_id=direction_claims[0]["boundary_node_id"],
                    details={
                        "target_node_id": target_id,
                        "target_port_id": target_port_id,
                        "direction": direction,
                    },
                )
            missing_ports = sorted(connected_ports - mapped_ports)
            if missing_ports:
                add_issue(
                    "binding_port_coverage_incomplete",
                    f"目标节点 {target_id} 的已连接端口未被完整映射",
                    node_id=direction_claims[0]["boundary_node_id"],
                    details={
                        "target_node_id": target_id,
                        "target_port_ids": missing_ports,
                        "direction": direction,
                    },
                )

    if issues:
        raise BlueprintBindingValidationError(issues)
