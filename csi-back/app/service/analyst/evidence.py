"""Agent 证据链的权限、分页解析与保存前校验。"""

import re
from datetime import datetime, timezone

from elasticsearch.exceptions import NotFoundError

from app.core.exceptions import (
    ApiException,
    BadRequestException,
    ForbiddenException,
    InternalServerException,
    NotFoundException,
)
from app.models.auth.user import UserModel
from app.schemas.evidence import EvidenceEntityRef, EvidenceGraph, EvidenceNode
from app.service import evidence
from app.service.analyst.context import get_current_initiator_user_id
from app.service.auth.service import has_backend_permissions
from app.service.evidence_graph import graph_diff


async def require_evidence_user(action: str):
    """以任务发起人的实时账号状态和权限执行，不借用系统账号。"""
    user_id = get_current_initiator_user_id()
    if not user_id:
        raise ForbiddenException("证据链工具缺少任务发起用户，无法确认权限")
    user = await UserModel.find_one({"_id": user_id, "is_deleted": False})
    if not user or not user.enabled:
        raise ForbiddenException("任务发起用户已停用或不存在")
    expires = user.expired_at
    if expires and (
        expires.replace(tzinfo=timezone.utc) if expires.tzinfo is None else expires
    ) <= datetime.now(timezone.utc):
        raise ForbiddenException("任务发起用户已到期")
    permissions = ["operation:evidence:chain:read"]
    if action != "read":
        permissions.append(f"operation:evidence:chain:{action}")
    if not await has_backend_permissions(user, permissions):
        raise ForbiddenException("没有执行该证据链操作的权限")
    return user


async def require_graph_content_access(graph: dict, user) -> None:
    """读取引用、摘录前检查其源数据类型的权限。"""
    types = set()
    for node in graph.get("nodes", []):
        for ref in [
            node.get("entity"),
            node.get("version_source"),
            *node.get("members", []),
        ]:
            if ref:
                types.add(ref["entity_type"])
    for edge in graph.get("edges", []):
        types.update(
            anchor["entity"]["entity_type"] for anchor in edge.get("anchors", [])
        )
    for entity_type in types:
        await evidence.require_content_access(user, entity_type)


def read_graph_page(chain: dict, scope: str, page: int, page_size: int) -> dict:
    """分别分页图中的节点和关系，返回完整数量及后续页标识。"""
    result = evidence.chain_summary(chain)
    if scope == "summary":
        return result
    result.update(
        relation_types=chain.get("relation_types", []), page=page, page_size=page_size
    )
    start = (page - 1) * page_size
    for kind in ("nodes", "edges"):
        if scope in {"graph", kind}:
            items = chain.get(kind, [])
            result[kind] = items[start : start + page_size]
            result[f"{kind}_has_more"] = start + page_size < len(items)
    return result


async def find_path_node(
    chain: dict, path: str, user, cache: dict
) -> tuple[EvidenceNode, dict]:
    """沿实时子链指针定位节点，返回所属链而非父链中的副本。"""
    parts = path.split("/")
    if len(parts) > 33 or any(not part for part in parts):
        raise BadRequestException("节点路径无效或嵌套层数超过 32")
    owner = chain
    for index, part in enumerate(parts):
        raw = next((node for node in owner["nodes"] if node["id"] == part), None)
        if raw is None:
            raise BadRequestException(f"节点路径已失效：{path}")
        node = EvidenceNode.model_validate(raw)
        if index == len(parts) - 1:
            return node, owner
        if node.kind != "chain":
            raise BadRequestException("只有子链引用能够包含内部节点路径")
        if node.chain_id not in cache:
            child = await evidence.get_chain(node.chain_id)
            await require_graph_content_access(child, user)
            cache[node.chain_id] = child
        owner = cache[node.chain_id]
    raise BadRequestException("节点路径不能为空")


async def resolve_graph_node(
    chain: dict, node_path: str, user, page: int, page_size: int
) -> dict:
    """按需展开一个节点并返回可用于关系端点的稳定标识。"""
    node, owner = await find_path_node(chain, node_path, user, {chain["id"]: chain})
    result = {
        "chain_id": chain["id"],
        "revision": chain["revision"],
        "owner_chain_id": owner["id"],
        "owner_revision": owner["revision"],
        "node_id": node_path,
        "kind": node.kind,
        "resolved_at": datetime.now(timezone.utc),
        "page": page,
        "page_size": page_size,
    }
    if node.kind == "chain":
        child = await evidence.get_chain(node.chain_id)
        await require_graph_content_access(child, user)
        result["chain"] = read_graph_page(child, "graph", page, page_size)
        result["items"] = [
            {**item, "endpoint_id": f"{node_path}/{item['id']}"}
            for item in result["chain"].pop("nodes")
        ]
        result["chain"]["edges"] = [
            {
                **edge,
                "source": f"{node_path}/{edge['source']}",
                "target": f"{node_path}/{edge['target']}",
            }
            for edge in result["chain"]["edges"]
        ]
        result["total"] = len(child["nodes"])
    else:
        resolved = await evidence.resolve_node(node, user, page, page_size)
        result.update(
            {
                key: value
                for key, value in resolved.items()
                if key not in {"node_id", "kind"}
            }
        )
        result["items"] = [
            {
                **item,
                "endpoint_id": node_path
                if node.kind == "entity"
                else f"{node_path}/@{item['entity_type']}:{item['uuid']}",
            }
            for item in result.get("items", [])
        ]
        if node.kind == "note":
            result.update(node=node.model_dump(), total=0)
    result["has_more"] = page * page_size < result.get("total", 0)
    return result


async def read_source(ref: EvidenceEntityRef, user, cache: dict) -> dict:
    """读取完整原文校验摘录，缓存仅限本次调用，不持久化源内容。"""
    key = (ref.entity_type, ref.uuid)
    if key in cache:
        return cache[key]
    await evidence.require_content_access(user, ref.entity_type)
    if ref.entity_type == "wiki":
        source = await evidence.WikiPageModel.get_motor_collection().find_one(
            {"_id": ref.uuid}
        )
        if source:
            texts = [source.get("title", ""), source.get("source_note") or ""]
            pending = [source.get("content_tree", {})]
            while pending:
                section = pending.pop()
                texts.extend([section.get("title", ""), section.get("content", "")])
                pending.extend(section.get("children", []))
            texts.extend(
                item.get("text", "")
                for item in source.get("footnotes", []) + source.get("references", [])
            )
            source = {"clean_content": "\n".join(texts)}
    else:
        es = evidence.get_es()
        if es is None:
            raise InternalServerException("实体检索服务尚未连接")
        try:
            hit = await es.get(
                index=ref.entity_type,
                id=ref.uuid,
                _source_includes=evidence.ENTITY_FIELDS,
            )
            source = hit.get("_source", {})
        except NotFoundError:
            source = None
    cache[key] = source if source is not None else {"missing": True}
    return cache[key]


async def referencing_chains(chain_id: str) -> dict:
    """列出直接引用本链的父链和引用节点，限制返回大小。"""
    collection = evidence.EvidenceChainModel.get_motor_collection()
    query = {"deleted": False, "nodes.chain_id": chain_id}
    total = await collection.count_documents(query)
    docs = (
        await collection.find(query, {"title": 1, "nodes.id": 1, "nodes.chain_id": 1})
        .limit(100)
        .to_list(length=100)
    )
    return {
        "total": total,
        "truncated": total > len(docs),
        "items": [
            {
                "chain_id": str(doc["_id"]),
                "title": doc["title"],
                "node_ids": [
                    node["id"]
                    for node in doc.get("nodes", [])
                    if node.get("chain_id") == chain_id
                ],
            }
            for doc in docs
        ],
    }


async def validate_graph(
    chain_id: str, graph: EvidenceGraph, previous: dict | None, user
) -> dict:
    """检查候选图及来源，不把图结构或摘录匹配当作事实验证。

    Args:
        chain_id: 当前图 ID；创建时使用尚未落库的标识。
        graph: 整批操作计算后的候选图。
        previous: 保存前的图；原有失效依据返回警告，便于继续修复。
        user: 已确认权限的任务发起用户。

    Returns:
        错误、警告、图差异和直接引用本链的父链信息。
    """
    data = graph.model_dump()
    await require_graph_content_access(data, user)
    errors, warnings = [], []
    sources, children = {}, {}
    old_nodes = {node["id"]: node for node in (previous or {}).get("nodes", [])}
    old_edges = {edge["id"]: edge for edge in (previous or {}).get("edges", [])}
    binding_fields = ("kind", "entity", "members", "version_source", "chain_id")
    unchanged_nodes = {
        node.id
        for node in graph.nodes
        if node.id in old_nodes
        and all(
            old_nodes[node.id].get(key) == node.model_dump().get(key)
            for key in binding_fields
        )
    }
    try:
        await evidence.validate_references(chain_id, graph)
    except ApiException as exc:
        errors.append({"code": "invalid_subchain", "message": exc.message})
    for node in graph.nodes:
        refs = [node.entity] if node.kind == "entity" else node.members
        for ref in refs:
            source = await read_source(ref, user, sources)
            if source.get("missing"):
                issues = warnings if node.id in unchanged_nodes else errors
                issues.append(
                    {
                        "code": "missing_entity",
                        "node_id": node.id,
                        "message": f"原始实体不存在：{ref.entity_type}:{ref.uuid}",
                    }
                )
        if node.kind == "versions":
            versions = await evidence.query_versions(node.version_source, user, 1, 1)
            if not versions["total"]:
                warnings.append(
                    {
                        "code": "empty_versions",
                        "node_id": node.id,
                        "message": "动态来源暂未匹配版本，后续引用时仍会实时检索",
                    }
                )
    for edge in graph.edges:
        unchanged = old_edges.get(edge.id) == edge.model_dump() and all(
            node.id in unchanged_nodes
            for node in graph.nodes
            if node.id in {edge.source.split("/")[0], edge.target.split("/")[0]}
        )
        issues = warnings if unchanged else errors
        for endpoint in (edge.source, edge.target):
            path, separator, member = endpoint.rpartition("/@")
            try:
                node, _ = await find_path_node(
                    {**data, "id": chain_id},
                    path if separator else endpoint,
                    user,
                    children,
                )
                if not separator and node.kind == "entity":
                    source = await read_source(node.entity, user, sources)
                    if source.get("missing"):
                        raise BadRequestException("关系端点引用的原始实体已不存在")
                if separator:
                    entity_type, colon, entity_id = member.partition(":")
                    if not colon or node.kind not in {"collection", "versions"}:
                        raise BadRequestException(
                            "成员端点必须指向固定集合或动态版本中的实体"
                        )
                    ref = EvidenceEntityRef(entity_type=entity_type, uuid=entity_id)
                    if node.kind == "collection" and ref not in node.members:
                        raise BadRequestException("关系端点引用的实体不在固定集合中")
                    source = await read_source(ref, user, sources)
                    if source.get("missing"):
                        raise BadRequestException("关系端点引用的原始实体已不存在")
                    if node.kind == "versions" and (
                        ref.entity_type != node.version_source.entity_type
                        or str(source.get("source_id", ""))
                        != node.version_source.source_id
                        or source.get("platform") != node.version_source.platform
                    ):
                        raise BadRequestException("该实体不属于动态版本节点的来源")
            except (BadRequestException, NotFoundException, ValueError) as exc:
                issues.append(
                    {
                        "code": "invalid_endpoint",
                        "edge_id": edge.id,
                        "endpoint": endpoint,
                        "message": str(exc),
                    }
                )
        for anchor in edge.anchors:
            source = await read_source(anchor.entity, user, sources)
            quote = re.sub(r"\s+", " ", anchor.quote).strip()
            content = re.sub(
                r"\s+", " ", str(source.get("clean_content") or "")
            ).strip()
            if source.get("missing") or (quote and quote not in content):
                issues.append(
                    {
                        "code": "invalid_anchor",
                        "edge_id": edge.id,
                        "message": "依据实体不存在，或摘录无法在该实体原文中找到",
                        "entity": anchor.entity.model_dump(),
                    }
                )
        if not edge.anchors:
            warnings.append(
                {
                    "code": "no_anchor",
                    "edge_id": edge.id,
                    "message": "关系尚未附加具体实体依据",
                }
            )
    parents = (
        await referencing_chains(chain_id)
        if previous
        else {"total": 0, "items": [], "truncated": False}
    )
    if parents["total"]:
        warnings.append(
            {
                "code": "live_references",
                "message": "引用本链的父链会实时看到变更；父链中已有的内部连线不会自动改写",
            }
        )
    return {
        "valid": not errors,
        "errors": errors,
        "warnings": warnings,
        "diff": graph_diff(previous, graph),
        "affected_references": parents,
        "note": "仅检查结构、引用及摘录匹配，不代表事实、因果关系或分析判断已获证实",
    }
