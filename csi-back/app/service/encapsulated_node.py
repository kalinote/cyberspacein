from __future__ import annotations

from collections import defaultdict
from datetime import datetime

from app.models.action.blueprint import ActionBlueprintModel
from app.models.action.configs import ActionNodesHandleConfigModel
from app.models.action.node import ActionNodeModel
from app.schemas.action.node import (
    EncapsulatedNodeDeleteResponse,
    EncapsulatedNodeDetailResponse,
    EncapsulatedNodeFamilyResponse,
    EncapsulatedNodeReferenceResponse,
    EncapsulatedNodeSourceBlueprintResponse,
    EncapsulatedNodeVersionResponse,
)
from app.schemas.constants import (
    ActionNodeDefinitionOriginEnum,
    ActionNodeKindEnum,
)
from app.schemas.general import PageResponseSchema


class EncapsulatedNodeReferencedError(ValueError):
    """封装节点版本仍被可编辑蓝图引用。"""

    def __init__(self, references: list[EncapsulatedNodeReferenceResponse]):
        super().__init__("该封装节点版本仍被可编辑蓝图引用，请先升级或移除引用")
        self.references = references


async def collect_draft_references(
    node_ids: set[str],
) -> dict[str, list[EncapsulatedNodeReferenceResponse]]:
    """收集未删除可编辑蓝图对指定节点定义的引用。"""
    if not node_ids:
        return {}
    blueprints = await ActionBlueprintModel.find(
        {
            "is_deleted": False,
            "graph.nodes.data.definition_id": {"$in": sorted(node_ids)},
        }
    ).to_list()
    references: dict[str, list[EncapsulatedNodeReferenceResponse]] = defaultdict(list)
    for blueprint in blueprints:
        instance_ids_by_definition: dict[str, list[str]] = defaultdict(list)
        for graph_node in blueprint.graph.nodes:
            definition_id = graph_node.data.definition_id
            if definition_id in node_ids:
                instance_ids_by_definition[definition_id].append(graph_node.id)
        for definition_id, instance_ids in instance_ids_by_definition.items():
            references[definition_id].append(
                EncapsulatedNodeReferenceResponse(
                    blueprint_id=blueprint.id,
                    blueprint_name=blueprint.name,
                    blueprint_version=blueprint.version,
                    instance_count=len(instance_ids),
                    instance_ids=sorted(instance_ids),
                )
            )
    for node_references in references.values():
        node_references.sort(key=lambda item: (item.blueprint_name, item.blueprint_id))
    return dict(references)


async def _load_source_blueprints(
    source_blueprint_ids: set[str],
) -> dict[str, ActionBlueprintModel]:
    """一次性加载封装节点关联的源蓝图。"""
    if not source_blueprint_ids:
        return {}
    blueprints = await ActionBlueprintModel.find(
        {"_id": {"$in": sorted(source_blueprint_ids)}}
    ).to_list()
    return {blueprint.id: blueprint for blueprint in blueprints}


def _source_blueprint_response(
    blueprint: ActionBlueprintModel | None,
) -> EncapsulatedNodeSourceBlueprintResponse | None:
    """将源蓝图转换为管理接口摘要。"""
    if blueprint is None:
        return None
    return EncapsulatedNodeSourceBlueprintResponse(
        id=blueprint.id,
        name=blueprint.name,
        version=blueprint.version,
        is_deleted=blueprint.is_deleted,
    )


async def list_encapsulated_node_families(
    *,
    page: int,
    page_size: int,
    keyword: str | None,
) -> PageResponseSchema[EncapsulatedNodeFamilyResponse]:
    """按资源族分页返回封装节点有效版本，并保留历史最大版本。"""
    all_versions = await ActionNodeModel.find(
        {
            "node_kind": ActionNodeKindEnum.ENCAPSULATED,
            "definition_origin": ActionNodeDefinitionOriginEnum.BLUEPRINT,
        }
    ).to_list()
    source_blueprints = await _load_source_blueprints(
        {
            node.source_blueprint_id
            for node in all_versions
            if node.source_blueprint_id
        }
    )
    active_node_ids = {
        node.id for node in all_versions if not node.is_deleted
    }
    references = await collect_draft_references(active_node_ids)
    versions_by_family: dict[str, list[ActionNodeModel]] = defaultdict(list)
    for node in all_versions:
        versions_by_family[node.node_family_id or node.id].append(node)

    normalized_keyword = (keyword or "").strip().lower()
    families: list[EncapsulatedNodeFamilyResponse] = []
    for family_id, history in versions_by_family.items():
        active_versions = sorted(
            (node for node in history if not node.is_deleted),
            key=lambda node: node.definition_version,
            reverse=True,
        )
        if not active_versions:
            continue
        latest = next((node for node in active_versions if node.is_latest), active_versions[0])
        source_blueprint = source_blueprints.get(latest.source_blueprint_id or "")
        if normalized_keyword:
            searchable = " ".join(
                [
                    family_id,
                    latest.source_blueprint_id or "",
                    source_blueprint.name if source_blueprint else "",
                    *(
                        value
                        for node in active_versions
                        for value in (node.name, node.description, node.id)
                    ),
                ]
            ).lower()
            if normalized_keyword not in searchable:
                continue
        max_history_version = max(node.definition_version for node in history)
        families.append(
            EncapsulatedNodeFamilyResponse(
                node_family_id=family_id,
                name=latest.name,
                source_blueprint=_source_blueprint_response(source_blueprint),
                latest_node_id=latest.id,
                latest_definition_version=latest.definition_version,
                active_version_count=len(active_versions),
                max_history_version=max_history_version,
                next_definition_version=max_history_version + 1,
                latest_created_at=max(node.created_at for node in active_versions),
                versions=[
                    EncapsulatedNodeVersionResponse(
                        id=node.id,
                        name=node.name,
                        description=node.description,
                        definition_version=node.definition_version,
                        source_revision_id=node.source_revision_id or "",
                        is_latest=node.id == latest.id,
                        created_at=node.created_at,
                        draft_reference_count=len(references.get(node.id, [])),
                    )
                    for node in active_versions
                ],
            )
        )
    families.sort(key=lambda family: family.latest_created_at, reverse=True)
    total = len(families)
    start = (page - 1) * page_size
    return PageResponseSchema.create(
        families[start:start + page_size],
        total,
        page,
        page_size,
    )


async def _require_encapsulated_node(node_id: str) -> ActionNodeModel:
    """读取一个可管理的有效封装节点版本。"""
    node = await ActionNodeModel.find_one({"_id": node_id, "is_deleted": False})
    if node is None:
        raise LookupError(f"封装节点版本不存在，ID: {node_id}")
    if (
        node.node_kind != ActionNodeKindEnum.ENCAPSULATED
        or node.definition_origin != ActionNodeDefinitionOriginEnum.BLUEPRINT
    ):
        raise TypeError("该节点不是蓝图生成的封装节点")
    return node


async def get_encapsulated_node_detail(
    node_id: str,
) -> EncapsulatedNodeDetailResponse:
    """返回封装节点定义、源蓝图和草稿引用。"""
    from app.service.action import node_model_to_response

    node = await _require_encapsulated_node(node_id)
    source_blueprints = await _load_source_blueprints(
        {node.source_blueprint_id} if node.source_blueprint_id else set()
    )
    references = await collect_draft_references({node.id})
    return EncapsulatedNodeDetailResponse(
        node=await node_model_to_response(node),
        source_blueprint=_source_blueprint_response(
            source_blueprints.get(node.source_blueprint_id or "")
        ),
        references=references.get(node.id, []),
    )


async def next_encapsulated_definition_version(node_family_id: str) -> int:
    """根据包含软删除墓碑的完整历史计算下一版本号。"""
    latest_history = await ActionNodeModel.find(
        {
            "node_family_id": node_family_id,
            "definition_origin": ActionNodeDefinitionOriginEnum.BLUEPRINT,
        }
    ).sort("-definition_version").first_or_none()
    return (latest_history.definition_version if latest_history else 0) + 1


async def normalize_encapsulated_latest(
    node_family_id: str,
    *,
    preferred_node_id: str | None = None,
) -> ActionNodeModel | None:
    """确保资源族内仅有一个有效最新版，并返回该版本。"""
    query = {
        "node_family_id": node_family_id,
        "definition_origin": ActionNodeDefinitionOriginEnum.BLUEPRINT,
        "node_kind": ActionNodeKindEnum.ENCAPSULATED,
        "is_deleted": False,
    }
    candidates = await ActionNodeModel.find(query).sort("-definition_version").to_list()
    if not candidates:
        return None
    latest = (
        next((node for node in candidates if node.id == preferred_node_id), None)
        or candidates[0]
    )
    await ActionNodeModel.find(query).update({"$set": {"is_latest": False}})
    await latest.update(
        {
            "$set": {
                "is_latest": True,
                "updated_at": datetime.now(),
            }
        }
    )
    return latest


async def delete_encapsulated_node_version(
    node_id: str,
) -> EncapsulatedNodeDeleteResponse:
    """删除封装节点版本；最后一个有效版本删除时清除整个资源族。"""
    from app.service.action import ActionInstanceService

    node = await _require_encapsulated_node(node_id)
    references = (await collect_draft_references({node.id})).get(node.id, [])
    if references:
        raise EncapsulatedNodeReferencedError(references)
    family_id = node.node_family_id or node.id
    await node.update(
        {
            "$set": {
                "is_deleted": True,
                "is_latest": False,
                "updated_at": datetime.now(),
            }
        }
    )
    promoted = await normalize_encapsulated_latest(family_id)
    await ActionInstanceService._clear_cache("node", node.id)
    if promoted is not None:
        await ActionInstanceService._clear_cache("node", promoted.id)
        return EncapsulatedNodeDeleteResponse(
            deleted_node_id=node.id,
            node_family_id=family_id,
            promoted_latest_node_id=promoted.id,
            promoted_latest_definition_version=promoted.definition_version,
            next_definition_version=await next_encapsulated_definition_version(
                family_id
            ),
        )

    family_nodes = await ActionNodeModel.find(
        {
            "node_family_id": family_id,
            "definition_origin": ActionNodeDefinitionOriginEnum.BLUEPRINT,
            "node_kind": ActionNodeKindEnum.ENCAPSULATED,
        }
    ).to_list()
    family_node_ids = [item.id for item in family_nodes]
    legacy_handle_ids = {
        handle.id
        for item in family_nodes
        for handle in item.handles
        if not handle.handle_config_id or handle.handle_config_id == handle.id
    }
    removable_handle_ids = []
    for handle_id in sorted(legacy_handle_ids):
        external_reference = await ActionNodeModel.find_one(
            {
                "_id": {"$nin": family_node_ids},
                "$or": [
                    {"handles.handle_config_id": handle_id},
                    {"handles.id": handle_id},
                ],
            }
        )
        if external_reference is None:
            removable_handle_ids.append(handle_id)

    if removable_handle_ids:
        await ActionNodesHandleConfigModel.find(
            {"_id": {"$in": removable_handle_ids}}
        ).delete()
    if family_node_ids:
        await ActionNodeModel.find({"_id": {"$in": family_node_ids}}).delete()
    for family_node_id in family_node_ids:
        await ActionInstanceService._clear_cache("node", family_node_id)
    for handle_id in removable_handle_ids:
        await ActionInstanceService._clear_cache("handle", handle_id)

    return EncapsulatedNodeDeleteResponse(
        deleted_node_id=node.id,
        node_family_id=family_id,
        family_deleted=True,
    )
