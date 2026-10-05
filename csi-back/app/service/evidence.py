import asyncio
import re
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from bson.codec_options import CodecOptions
from elasticsearch.exceptions import NotFoundError
from pymongo import ReturnDocument
from pymongo.errors import DuplicateKeyError

from app.core.exceptions import (
    ApiException,
    BadRequestException,
    ForbiddenException,
    InternalServerException,
    NotFoundException,
)
from app.db.elasticsearch import get_es
from app.db.mongodb import get_mongodb
from app.models.evidence import EvidenceChainModel
from app.models.wiki import WikiPageModel
from app.schemas.evidence import (
    EvidenceEntityRef,
    EvidenceGraph,
    EvidenceNode,
    EvidenceVersionSource,
)
from app.service.auth.service import has_backend_permissions


CONTENT_PERMISSIONS = {
    "article": "operation:content:article:read",
    "forum": "operation:content:forum:read",
    "wiki": "operation:target:wiki:read",
}
ENTITY_FIELDS = [
    "uuid",
    "entity_type",
    "title",
    "clean_content",
    "source_id",
    "platform",
    "url",
    "crawled_at",
    "last_edit_at",
    "publish_at",
    "data_version",
]


def chain_summary(doc: dict) -> dict:
    """生成不包含图正文的列表记录。"""
    return {
        "id": str(doc.get("_id", doc.get("id", ""))),
        **{
            key: doc.get(key)
            for key in (
                "title",
                "description",
                "purpose",
                "template",
                "status",
                "tags",
                "revision",
                "created_at",
                "updated_at",
            )
        },
        "node_count": len(doc.get("nodes", [])),
        "edge_count": len(doc.get("edges", [])),
        "subchain_count": sum(n["kind"] == "chain" for n in doc.get("nodes", [])),
    }


async def get_chain(chain_id: str) -> dict:
    """读取子链当前图，不固定到历史修订。"""
    collection = EvidenceChainModel.get_motor_collection().with_options(
        codec_options=CodecOptions(tz_aware=True)
    )
    doc = await collection.find_one(
        {"_id": chain_id, "deleted": False}
    )
    if doc is None:
        raise NotFoundException("证据链不存在或已删除")
    doc["id"] = str(doc.pop("_id"))
    doc.pop("deleted", None)
    return doc


@asynccontextmanager
async def graph_write_lock():
    """串行校验跨链引用，防止多个服务进程同时写入递归引用。

    锁持有期间只执行数据库操作，限制为 20 秒；租约在 60 秒后可恢复。
    使用随机所有者标识释放，避免误释放其他请求获得的锁。
    """
    locks = get_mongodb()["evidence_graph_locks"]
    owner = uuid4().hex
    deadline = asyncio.get_running_loop().time() + 5
    while True:
        now = datetime.now(timezone.utc)
        try:
            await locks.find_one_and_update(
                {"_id": "topology", "expires_at": {"$lte": now}},
                {"$set": {"owner": owner, "expires_at": now + timedelta(seconds=60)}},
                upsert=True,
                return_document=ReturnDocument.AFTER,
            )
            break
        except DuplicateKeyError:
            if asyncio.get_running_loop().time() >= deadline:
                raise ApiException(240409, "其他证据链正在保存，请稍后重试")
            await asyncio.sleep(0.05)
    try:
        async with asyncio.timeout(20):
            yield
    finally:
        await locks.delete_one({"_id": "topology", "owner": owner})


async def validate_references(chain_id: str, graph: EvidenceGraph) -> None:
    """遍历子链引用验证无递归，普通实体关系不参与此项校验。"""
    pending = {node.chain_id for node in graph.nodes if node.kind == "chain"}
    visited = set()
    collection = EvidenceChainModel.get_motor_collection()
    while pending:
        if chain_id in pending:
            raise BadRequestException("子链不能直接或间接引用自身")
        current = pending - visited
        if not current:
            return
        visited.update(current)
        docs = await collection.find(
            {"_id": {"$in": list(current)}, "deleted": False}, {"nodes.chain_id": 1}
        ).to_list(length=None)
        if len(docs) != len(current):
            raise BadRequestException("引用的子链不存在或已删除")
        pending = {
            node["chain_id"]
            for doc in docs
            for node in doc.get("nodes", [])
            if node.get("chain_id")
        }


async def validate_endpoints(
    graph: EvidenceGraph, previous: dict | None = None
) -> None:
    """验证新建的内部端点，已有失效引用保留以供人工修复。"""
    old_endpoints = {
        edge[key]
        for edge in (previous or {}).get("edges", [])
        for key in ("source", "target")
    }
    children = {}
    for endpoint in {
        getattr(edge, key) for edge in graph.edges for key in ("source", "target")
    }:
        parts = endpoint.split("/")
        if len(parts) == 1 or endpoint in old_endpoints:
            continue
        nodes = {node.id: node.model_dump() for node in graph.nodes}
        for index, part in enumerate(parts):
            node = nodes.get(part)
            if node is None:
                raise BadRequestException("关系引用的内部节点不存在，请重新选择端点")
            if index == len(parts) - 1:
                break
            if node["kind"] == "chain":
                child_id = node["chain_id"]
                if child_id not in children:
                    children[child_id] = await get_chain(child_id)
                nodes = {child["id"]: child for child in children[child_id]["nodes"]}
                continue
            member = parts[index + 1]
            if (
                node["kind"] not in {"collection", "versions"}
                or index + 2 != len(parts)
                or not member.startswith("@")
                or ":" not in member
            ):
                raise BadRequestException("关系端点的引用路径无效")
            entity_type, entity_id = member[1:].split(":", 1)
            if not entity_id or not re.fullmatch(r"[\w.:-]+", entity_id):
                raise BadRequestException("集合成员引用无效")
            if node["kind"] == "collection" and not any(
                ref["entity_type"] == entity_type and ref["uuid"] == entity_id
                for ref in node["members"]
            ):
                raise BadRequestException("关系引用的实体不在固定集合内")
            if (
                node["kind"] == "versions"
                and entity_type != node["version_source"]["entity_type"]
            ):
                raise BadRequestException("版本端点的实体类型与集合不一致")
            break


async def write_chain(
    graph: EvidenceGraph,
    operator: str,
    chain_id: str | None = None,
    expected_revision: int | None = None,
) -> dict:
    """校验并原子保存图，修订冲突时保留服务器已有内容。

    Args:
        graph: 不包含检索结果的节点和关系定义。
        operator: 当前操作者标识。
        chain_id: 为空时创建新图。
        expected_revision: 更新时必须匹配的修订号。
    """
    creating = chain_id is None
    chain_id = chain_id or uuid4().hex
    collection = EvidenceChainModel.get_motor_collection()
    async with graph_write_lock():
        previous = None
        if not creating:
            previous = await get_chain(chain_id)
            if previous["revision"] != expected_revision:
                raise ApiException(
                    240409, "证据链已被其他用户修改，请保留当前编辑并重新加载后合并"
                )
        await validate_references(chain_id, graph)
        await validate_endpoints(graph, previous)
        now = datetime.now(timezone.utc)
        payload = graph.model_dump()
        payload.update(updated_at=now, updated_by=operator)
        if creating:
            await collection.insert_one(
                {
                    "_id": chain_id,
                    **payload,
                    "revision": 1,
                    "created_at": now,
                    "created_by": operator,
                    "deleted": False,
                }
            )
        else:
            result = await collection.update_one(
                {"_id": chain_id, "revision": expected_revision, "deleted": False},
                {"$set": payload, "$inc": {"revision": 1}},
            )
            if result.matched_count != 1:
                raise ApiException(240409, "证据链已变化，请重新加载后合并")
        return await get_chain(chain_id)


async def delete_chain(chain_id: str, expected_revision: int) -> None:
    """仅删除没有被其他证据链引用的图，不删除原始实体。"""
    collection = EvidenceChainModel.get_motor_collection()
    async with graph_write_lock():
        await get_chain(chain_id)
        parent = await collection.find_one(
            {"deleted": False, "nodes.chain_id": chain_id}, {"title": 1}
        )
        if parent:
            raise BadRequestException(
                f"仍被证据链「{parent['title']}」引用，请先解除引用"
            )
        result = await collection.update_one(
            {"_id": chain_id, "revision": expected_revision, "deleted": False},
            {
                "$set": {"deleted": True, "updated_at": datetime.now(timezone.utc)},
                "$inc": {"revision": 1},
            },
        )
        if result.matched_count != 1:
            raise ApiException(240409, "证据链已变化，请刷新列表后重试")


async def list_chains(q: str, status: str | None, page: int, page_size: int) -> dict:
    """搜索证据链元数据并分页。"""
    filters = {"deleted": False}
    if q.strip():
        pattern = re.compile(re.escape(q.strip()), re.IGNORECASE)
        filters["$or"] = [
            {key: pattern} for key in ("title", "description", "purpose", "tags")
        ]
    if status:
        filters["status"] = status
    collection = EvidenceChainModel.get_motor_collection().with_options(
        codec_options=CodecOptions(tz_aware=True)
    )
    total = await collection.count_documents(filters)
    docs = (
        await collection.find(filters)
        .sort("updated_at", -1)
        .skip((page - 1) * page_size)
        .limit(page_size)
        .to_list(length=page_size)
    )
    return {
        "items": [chain_summary(doc) for doc in docs],
        "total": total,
        "page": page,
        "page_size": page_size,
    }


async def require_content_access(user, entity_type: str) -> None:
    """保持实体原有的读取权限，避免通过图引用绕过限制。"""
    permission = CONTENT_PERMISSIONS.get(entity_type)
    if not permission or not await has_backend_permissions(user, [permission]):
        raise ForbiddenException("没有读取该类型实体的权限")


async def read_entity(ref: EvidenceEntityRef, user) -> dict:
    """读取一个确定版本，源数据缺失时保留引用状态。"""
    await require_content_access(user, ref.entity_type)
    if ref.entity_type == "wiki":
        doc = await WikiPageModel.get_motor_collection().find_one(
            {"_id": ref.uuid}, {"title": 1, "source_note": 1, "updated_at": 1}
        )
        if not doc:
            return {**ref.model_dump(), "missing": True, "title": "专题事件已不可用"}
        return {
            **ref.model_dump(),
            "title": doc["title"],
            "clean_content": doc.get("source_note", ""),
            "last_edit_at": doc.get("updated_at"),
        }
    es = get_es()
    if es is None:
        raise InternalServerException("实体检索服务尚未连接")
    try:
        hit = await es.get(
            index=ref.entity_type, id=ref.uuid, _source_includes=ENTITY_FIELDS
        )
    except NotFoundError:
        return {**ref.model_dump(), "missing": True, "title": "原始实体已不可用"}
    source = hit.get("_source", {})
    return {
        **source,
        **ref.model_dump(),
        "clean_content": (source.get("clean_content") or "")[:2000],
    }


async def query_versions(
    source: EvidenceVersionSource, user, page: int, page_size: int
) -> dict:
    """按来源身份即时检索版本；不会向证据链写入成员。"""
    await require_content_access(user, source.entity_type)
    es = get_es()
    if es is None:
        raise InternalServerException("实体检索服务尚未连接")
    offset = (page - 1) * page_size
    if offset + page_size > 10000:
        raise BadRequestException("版本分页超出检索窗口，请缩小每页数量")
    result = await es.search(
        index=source.entity_type,
        body={
            "query": {
                "bool": {
                    "filter": [
                        {"term": {"source_id.keyword": source.source_id}},
                        {"term": {"platform.keyword": source.platform}},
                    ]
                }
            },
            "sort": [
                {"crawled_at": {"order": "asc", "missing": "_last"}},
                {"uuid.keyword": "asc"},
            ],
            "track_total_hits": True,
            "_source": ENTITY_FIELDS,
            "from": offset,
            "size": page_size,
        },
    )
    items = []
    for hit in result["hits"]["hits"]:
        data = hit.get("_source", {})
        items.append(
            {
                **data,
                "uuid": data.get("uuid") or hit["_id"],
                "entity_type": source.entity_type,
                "clean_content": (data.get("clean_content") or "")[:2000],
            }
        )
    return {
        "items": items,
        "total": result["hits"]["total"]["value"],
        "page": page,
        "page_size": page_size,
    }


async def resolve_node(node: EvidenceNode, user, page: int, page_size: int) -> dict:
    """按节点类型解析当前内容，不将结果写回节点定义。"""
    result = {
        "node_id": node.id,
        "kind": node.kind,
        "resolved_at": datetime.now(timezone.utc),
    }
    if node.kind == "chain":
        if not await has_backend_permissions(user, ["operation:evidence:chain:read"]):
            raise ForbiddenException("没有读取子链的权限")
        result["chain"] = await get_chain(node.chain_id)
    elif node.kind == "versions":
        result.update(await query_versions(node.version_source, user, page, page_size))
    elif node.kind in {"entity", "collection"}:
        refs = [node.entity] if node.kind == "entity" else node.members
        selected = refs[(page - 1) * page_size : page * page_size]
        result.update(
            items=await asyncio.gather(*(read_entity(ref, user) for ref in selected)),
            total=len(refs),
            page=page,
            page_size=page_size,
        )
    return result
