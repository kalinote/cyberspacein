import logging
import re
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query

from app.db.elasticsearch import get_es
from app.models.search_template import SearchTemplateModel
from app.schemas.general import PageParamsSchema, PageResponseSchema
from app.schemas.response import ApiResponseSchema
from app.schemas.search import (
    EntitySearchRequestSchema,
    SearchResultSchema,
    SearchTemplateCreateRequestSchema,
    SearchTemplateSchema,
    SearchTemplateUpdateRequestSchema,
)
from app.service.search import search_entity as search_entity_service
from app.utils.id_lib import generate_id

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


@router.post("/template", response_model=ApiResponseSchema[SearchTemplateSchema], summary="创建检索模板")
async def create_search_template(data: SearchTemplateCreateRequestSchema):
    template_id = generate_id(
        data.title + data.search_query + str(datetime.utcnow().timestamp())
    )
    existing = await SearchTemplateModel.find_one({"_id": template_id})
    if existing:
        return ApiResponseSchema.error(code=400, message="标题与检索词组合已存在，请稍作修改后重试")
    doc = SearchTemplateModel(
        id=template_id,
        title=data.title,
        description=data.description,
        search_query=data.search_query,
        rules=data.rules,
    )
    await doc.insert()
    logger.info(f"成功创建检索模板: {template_id} - {data.title}")
    return ApiResponseSchema.success(data=SearchTemplateSchema.from_doc(doc))


@router.get("/templates", response_model=PageResponseSchema[SearchTemplateSchema], summary="获取检索模板列表")
async def get_search_template_list(
    params: PageParamsSchema = Depends(),
    search: Optional[str] = Query(None, description="搜索关键词，模糊匹配标题或描述"),
):
    skip = (params.page - 1) * params.page_size
    query_filters = {}
    if search:
        pattern = re.compile(re.escape(search), re.IGNORECASE)
        query_filters["$or"] = [
            {"title": {"$regex": pattern}},
            {"description": {"$regex": pattern}},
        ]
    query = SearchTemplateModel.find(query_filters)
    total = await query.count()
    items = await query.skip(skip).limit(params.page_size).to_list()
    results = [SearchTemplateSchema.from_doc(t) for t in items]
    return PageResponseSchema.create(results, total, params.page, params.page_size)


@router.get("/template/{template_id}", response_model=ApiResponseSchema[SearchTemplateSchema], summary="获取检索模板详情")
async def get_search_template_detail(template_id: str):
    doc = await SearchTemplateModel.find_one({"_id": template_id})
    if not doc:
        return ApiResponseSchema.error(code=404, message=f"检索模板不存在，ID: {template_id}")
    return ApiResponseSchema.success(data=SearchTemplateSchema.from_doc(doc))


@router.put("/template/{template_id}", response_model=ApiResponseSchema[SearchTemplateSchema], summary="更新检索模板")
async def update_search_template(template_id: str, data: SearchTemplateUpdateRequestSchema):
    doc = await SearchTemplateModel.find_one({"_id": template_id})
    if not doc:
        return ApiResponseSchema.error(code=404, message=f"检索模板不存在，ID: {template_id}")
    update_data = data.model_dump(exclude_unset=True)
    if "title" in update_data:
        doc.title = update_data["title"]
    if "description" in update_data:
        doc.description = update_data["description"]
    if "search_query" in update_data:
        doc.search_query = update_data["search_query"]
    if "rules" in update_data:
        doc.rules = update_data["rules"]
    doc.updated_at = datetime.now()
    await doc.save()
    return ApiResponseSchema.success(data=SearchTemplateSchema.from_doc(doc))


@router.delete("/template/{template_id}", response_model=ApiResponseSchema[None], summary="删除检索模板")
async def delete_search_template(template_id: str):
    doc = await SearchTemplateModel.find_one({"_id": template_id})
    if not doc:
        return ApiResponseSchema.error(code=404, message=f"检索模板不存在，ID: {template_id}")
    await doc.delete()
    logger.info(f"已删除检索模板: {template_id}")
    return ApiResponseSchema.success()
