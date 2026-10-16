from fastapi import APIRouter, Depends, Query

from app.dependencies.auth import get_current_user
from app.models.evidence import EvidenceChainModel
from app.schemas.evidence import EvidenceGraph, EvidenceResolve, EvidenceSave
from app.schemas.response import ApiResponseSchema
from app.service import evidence


router = APIRouter(prefix="/evidence", tags=["证据链"])


@router.get("/overview")
async def overview():
    """统计真实图数据并返回最近编辑的证据链。"""
    collection = EvidenceChainModel.get_motor_collection()
    stats = await collection.aggregate(
        [
            {"$match": {"deleted": False}},
            {
                "$group": {
                    "_id": None,
                    "chains": {"$sum": 1},
                    "nodes": {"$sum": {"$size": "$nodes"}},
                    "edges": {"$sum": {"$size": "$edges"}},
                    "active": {
                        "$sum": {"$cond": [{"$eq": ["$status", "active"]}, 1, 0]}
                    },
                }
            },
        ]
    ).to_list(length=1)
    counts = {
        key: (stats[0].get(key, 0) if stats else 0)
        for key in ("chains", "nodes", "edges", "active")
    }
    recent = await evidence.list_chains("", None, 1, 6)
    return ApiResponseSchema.success(data={**counts, "recent": recent["items"]})


@router.get("/chains")
async def list_chains(
    q: str = Query(default="", max_length=300),
    status: str | None = Query(default=None, pattern="^(draft|active|archived)$"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
):
    """查询证据链列表。"""
    return ApiResponseSchema.success(
        data=await evidence.list_chains(q, status, page, page_size)
    )


@router.post("/chains")
async def create_chain(data: EvidenceGraph, user=Depends(get_current_user)):
    """创建人工构建的证据链。"""
    return ApiResponseSchema.success(
        data=await evidence.write_chain(data, str(user.id))
    )


@router.get("/chains/{chain_id}")
async def get_chain(chain_id: str):
    """获取当前图定义。"""
    return ApiResponseSchema.success(data=await evidence.get_chain(chain_id))


@router.put("/chains/{chain_id}")
async def save_chain(chain_id: str, data: EvidenceSave, user=Depends(get_current_user)):
    """保存图定义并检查并发修订。"""
    graph = EvidenceGraph.model_validate(data.model_dump(exclude={"expected_revision"}))
    return ApiResponseSchema.success(
        data=await evidence.write_chain(
            graph, str(user.id), chain_id, data.expected_revision
        )
    )


@router.delete("/chains/{chain_id}")
async def delete_chain(chain_id: str, expected_revision: int = Query(ge=1)):
    """删除证据链，存在父链引用时拒绝删除。"""
    await evidence.delete_chain(chain_id, expected_revision)
    return ApiResponseSchema.success(data={"deleted": True})


@router.post("/resolve")
async def resolve(data: EvidenceResolve, user=Depends(get_current_user)):
    """实时读取实体、集合或子链，也支持尚未保存的节点。"""
    return ApiResponseSchema.success(
        data=await evidence.resolve_node(data.node, user, data.page, data.page_size)
    )
