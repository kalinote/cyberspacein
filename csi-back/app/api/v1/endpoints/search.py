import logging
from fastapi import APIRouter, HTTPException

from app.schemas.search import EntitySearchRequestSchema, SearchResultSchema
from app.schemas.general import PageResponseSchema
from app.schemas.response import ApiResponseSchema
from app.db.elasticsearch import get_es
from app.service.search import search_entity as search_entity_service

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/search",
    tags=["搜索"],
)


@router.post("/entity", response_model=PageResponseSchema[SearchResultSchema], summary="搜索实体")
async def search_entity(params: EntitySearchRequestSchema):
    """
    搜索实体接口，支持关键词/向量/融合三种搜索模式，多种过滤条件
    """
    es = get_es()
    if not es:
        return ApiResponseSchema.error(code=500, message="Elasticsearch连接未初始化")

    try:
        return await search_entity_service(es, params, instruct="Given a web search query, retrieve relevant passages that answer the query")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"搜索实体失败: {e}", exc_info=True)
        return ApiResponseSchema.error(code=500, message=f"搜索实体失败: {str(e)}")
