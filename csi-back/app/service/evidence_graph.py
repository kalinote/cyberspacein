"""证据链模板、批量编辑与布局的纯计算，不访问或修改源数据。"""

from collections import deque
from copy import deepcopy
from uuid import uuid4

from app.schemas.agent.evidence import EvidenceCreateInput, EvidenceOperation
from app.schemas.evidence import EvidenceEdge, EvidenceGraph, EvidenceNode


TEMPLATES = {
    "blank": ([], [], ["关联", "支持", "反驳", "补充", "引用", "先于"]),
    "proof": (
        ["支持材料", "待验证判断", "反证与疑点"],
        [(0, 1, "支持"), (2, 1, "反驳")],
        ["支持", "反驳", "补充", "引用", "关联"],
    ),
    "expansion": (
        ["核心线索", "相关背景", "外部影响"],
        [(1, 0, "补充"), (0, 2, "关联")],
        ["补充", "关联", "引用", "影响"],
    ),
    "trace": (
        ["事件起点", "后续变化", "当前状态"],
        [(0, 1, "先于"), (1, 2, "先于")],
        ["先于", "演变为", "导致", "补充", "引用"],
    ),
}


def create_graph(data: EvidenceCreateInput) -> EvidenceGraph:
    """按与画布一致的场景模板初始化草稿。"""
    labels, links, relations = TEMPLATES[data.template]
    nodes = [
        EvidenceNode(
            id=uuid4().hex,
            kind="note",
            label=label,
            position={"x": 80 + i * 340, "y": 160},
        )
        for i, label in enumerate(labels)
    ]
    return EvidenceGraph(
        **data.model_dump(exclude={"reason", "request_id"}),
        relation_types=relations,
        nodes=nodes,
        edges=[
            EvidenceEdge(
                id=uuid4().hex, source=nodes[a].id, target=nodes[b].id, label=label
            )
            for a, b, label in links
        ],
    )


def apply_operations(
    previous: dict, operations: list[EvidenceOperation]
) -> tuple[EvidenceGraph, dict]:
    """在副本上顺序执行整批操作，任一错误均不产生写入。

    Args:
        previous: 当前图定义及其元数据。
        operations: 严格校验后的操作；新增对象通过 $client_key 引用。

    Returns:
        待保存的完整图和临时名称到正式 ID 的映射。
    """
    graph = deepcopy(
        {key: previous[key] for key in EvidenceGraph.model_fields if key in previous}
    )
    nodes = {node["id"]: node for node in graph.get("nodes", [])}
    edges = {edge["id"]: edge for edge in graph.get("edges", [])}
    ids = {}
    for operation in operations:
        if operation.client_key:
            if operation.client_key in ids:
                raise ValueError(f"临时名称重复：{operation.client_key}")
            ids[operation.client_key] = uuid4().hex
    for operation in operations:
        op = operation.op
        node_id = (
            resolve_temporary_id(operation.node_id, ids) if operation.node_id else None
        )
        edge_id = (
            resolve_temporary_id(operation.edge_id, ids) if operation.edge_id else None
        )
        if node_id is not None and node_id not in nodes:
            raise ValueError(
                f"当前图中不存在节点 {node_id}；修改子链内部请保存子链本体"
            )
        if edge_id is not None and edge_id not in edges:
            raise ValueError(f"当前图中不存在关系 {edge_id}")
        if op == "set_metadata":
            graph.update(operation.metadata.model_dump(exclude_unset=True))
        elif op in {"add_node", "reference_subchain"}:
            values = (
                operation.node.model_dump()
                if op == "add_node"
                else {
                    "kind": "chain",
                    "chain_id": operation.chain_id,
                    "label": operation.label,
                    "position": operation.position.model_dump()
                    if operation.position
                    else {"x": 0, "y": 0},
                }
            )
            node = EvidenceNode(id=ids[operation.client_key], **values).model_dump()
            nodes[node["id"]] = node
        elif op == "update_node":
            nodes[node_id] = EvidenceNode.model_validate(
                {**nodes[node_id], **operation.patch.model_dump(exclude_unset=True)}
            ).model_dump()
        elif op in {"remove_node", "remove_subchain_reference"}:
            if (nodes[node_id]["kind"] == "chain") != (
                op == "remove_subchain_reference"
            ):
                raise ValueError(
                    "子链引用请使用 remove_subchain_reference，普通节点请使用 remove_node"
                )
            remove_connected_edges(edges, {node_id}, operation.edge_policy)
            del nodes[node_id]
        elif op == "update_collection_members":
            node = nodes[node_id]
            if node["kind"] != "collection":
                raise ValueError("仅固定集合允许修改成员；动态版本只保存检索规则")
            old = {(ref["entity_type"], ref["uuid"]): ref for ref in node["members"]}
            members = {
                (ref.entity_type, ref.uuid): ref.model_dump()
                for ref in operation.members
            }
            if len(members) != len(operation.members):
                raise ValueError("成员引用不能重复")
            updated = (
                members
                if operation.member_mode == "set"
                else (
                    {**old, **members}
                    if operation.member_mode == "add"
                    else {key: ref for key, ref in old.items() if key not in members}
                )
            )
            removed = {
                f"{node_id}/@{kind}:{uuid}"
                for kind, uuid in old.keys() - updated.keys()
            }
            remove_connected_edges(edges, removed, operation.edge_policy)
            node["members"] = list(updated.values())
        elif op in {"add_edge", "update_edge"}:
            values = (
                operation.edge.model_dump()
                if op == "add_edge"
                else {
                    **edges[edge_id],
                    **operation.edge_patch.model_dump(exclude_unset=True),
                }
            )
            for key in ("source", "target"):
                values[key] = resolve_temporary_id(values[key], ids)
            values["id"] = ids[operation.client_key] if op == "add_edge" else edge_id
            edge = EvidenceEdge.model_validate(values).model_dump()
            edges[edge["id"]] = edge
        elif op == "remove_edge":
            del edges[edge_id]
        elif op == "move_nodes":
            moved = set()
            for position in operation.positions:
                target = resolve_temporary_id(position.node_id, ids)
                if target not in nodes or target in moved:
                    raise ValueError("移动节点必须属于当前图，且不能重复指定")
                moved.add(target)
                nodes[target]["position"] = {"x": position.x, "y": position.y}
        elif op == "auto_layout":
            selected = (
                [resolve_temporary_id(value, ids) for value in operation.node_ids]
                if operation.node_ids
                else list(nodes)
            )
            locked = {
                resolve_temporary_id(value, ids) for value in operation.locked_node_ids
            }
            if (
                len(set(selected)) != len(selected)
                or not set(selected).issubset(nodes)
                or not locked.issubset(nodes)
            ):
                raise ValueError("布局范围和锁定节点必须属于当前图，且范围不能重复")
            layout_nodes(nodes, edges, selected, locked, operation.layout)
    graph.update(nodes=list(nodes.values()), edges=list(edges.values()))
    return EvidenceGraph.model_validate(graph), ids


def resolve_temporary_id(value: str, ids: dict) -> str:
    """替换端点根节点的临时名称，保留子链和版本路径。"""
    root, separator, suffix = value.partition("/")
    if root.startswith("$"):
        if root[1:] not in ids:
            raise ValueError(f"未定义的临时名称：{root}")
        root = ids[root[1:]]
    return root + separator + suffix


def remove_connected_edges(edges: dict, endpoints: set[str], policy: str) -> None:
    """检查或移除指向被删除节点及内部成员的关系。"""
    connected = [
        key
        for key, edge in edges.items()
        if any(
            edge[side] == endpoint or edge[side].startswith(endpoint + "/")
            for side in ("source", "target")
            for endpoint in endpoints
        )
    ]
    if connected and policy == "reject":
        raise ValueError(
            f"仍有 {len(connected)} 条关系连接待移除的节点/成员；先移除关系或设置 edge_policy=remove_connected"
        )
    for key in connected:
        del edges[key]


def layout_nodes(
    nodes: dict, edges: dict, selected: list[str], locked: set[str], mode: str
) -> None:
    """仅调整本链节点；层级布局容许关系环路，锁定位置保持不变。"""
    levels = {}
    if mode == "tree":
        children = {node_id: [] for node_id in selected}
        incoming = {node_id: 0 for node_id in selected}
        for edge in edges.values():
            source, target = edge["source"].split("/")[0], edge["target"].split("/")[0]
            if source != target and source in children and target in children:
                children[source].append(target)
                incoming[target] += 1
        roots = [node_id for node_id in selected if not incoming[node_id]]
        queue = deque((node_id, 0) for node_id in roots)
        for seed in selected:
            if not queue and seed not in levels:
                queue.append((seed, 0))
            while queue:
                node_id, level = queue.popleft()
                if node_id in levels:
                    continue
                levels[node_id] = level
                queue.extend(
                    (child, level + 1)
                    for child in children[node_id]
                    if child not in levels
                )
    rows = {}
    occupied = [
        node["position"]
        for key, node in nodes.items()
        if key not in selected or key in locked
    ]
    for index, node_id in enumerate(selected):
        if node_id in locked:
            continue
        column = levels[node_id] if mode == "tree" else index % 3
        row = rows.get(column, 0) if mode == "tree" else index // 3
        x, y = 80 + column * 340, 80 + row * 190
        while any(
            abs(x - pos["x"]) < 300 and abs(y - pos["y"]) < 160 for pos in occupied
        ):
            y += 190
        nodes[node_id]["position"] = {"x": x, "y": y}
        occupied.append(nodes[node_id]["position"])
        rows[column] = (y - 80) // 190 + 1


def graph_diff(previous: dict | None, graph: EvidenceGraph) -> dict:
    """给审批和校验返回可核对的字段及对象变更。"""
    before = previous or {}
    after = graph.model_dump()
    result = {
        "metadata": {
            key: {"before": before.get(key), "after": value}
            for key, value in after.items()
            if key not in {"nodes", "edges"} and before.get(key) != value
        }
    }
    for kind in ("nodes", "edges"):
        old = {item["id"]: item for item in before.get(kind, [])}
        new = {item["id"]: item for item in after[kind]}
        result[kind] = {
            "added": [item for key, item in new.items() if key not in old],
            "removed": [item for key, item in old.items() if key not in new],
            "updated": [
                {
                    "id": key,
                    "label": item.get("label", ""),
                    "changes": {
                        field: {"before": old[key].get(field), "after": value}
                        for field, value in item.items()
                        if old[key].get(field) != value
                    },
                }
                for key, item in new.items()
                if key in old and old[key] != item
            ],
        }
    return result
