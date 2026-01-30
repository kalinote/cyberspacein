import logging
import re
from typing import Optional

from fastapi import APIRouter, Depends, Query

from app.schemas.response import ApiResponseSchema
from app.schemas.general import PageParamsSchema, PageResponseSchema
from app.schemas.agent import AgentModelConfigCreateRequestSchema, AgentModelConfigSchema
from app.models.agent.configs import AgentModelConfigModel
from app.utils.id_lib import generate_id

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/agent",
    tags=["智能体管理"],
)


@router.post("/configs/models", response_model=ApiResponseSchema[AgentModelConfigSchema], summary="新增模型配置")
async def create_agent_model_config(data: AgentModelConfigCreateRequestSchema):
    config_id = generate_id(data.name + data.base_url + data.model)
    existing = await AgentModelConfigModel.find_one({"_id": config_id})
    if existing:
        return ApiResponseSchema.error(code=400, message="同名且同基础URL、同模型ID的配置已存在")
    existing_by_name = await AgentModelConfigModel.find_one({"name": data.name})
    if existing_by_name:
        return ApiResponseSchema.error(code=400, message=f"模型名称已存在: {data.name}")
    doc = AgentModelConfigModel(
        id=config_id,
        name=data.name,
        description=data.description,
        base_url=data.base_url,
        api_key=data.api_key,
        model=data.model,
    )
    await doc.insert()
    logger.info(f"成功创建模型配置: {config_id} - {data.name}")
    return ApiResponseSchema.success(data=AgentModelConfigSchema(
        id=doc.id,
        name=doc.name,
        description=doc.description,
        base_url=doc.base_url,
        api_key=doc.api_key,
        model=doc.model,
        created_at=doc.created_at,
        updated_at=doc.updated_at,
    ))


@router.get("/configs/models", response_model=PageResponseSchema[AgentModelConfigSchema], summary="查询模型配置列表")
async def get_agent_model_config_list(
    params: PageParamsSchema = Depends(),
    search: Optional[str] = Query(None, description="搜索关键词，模糊匹配名称或描述"),
):
    skip = (params.page - 1) * params.page_size
    query_filters = {}
    if search:
        pattern = re.compile(re.escape(search), re.IGNORECASE)
        query_filters["$or"] = [
            {"name": {"$regex": pattern}},
            {"description": {"$regex": pattern}},
        ]
    if query_filters:
        query = AgentModelConfigModel.find(query_filters)
    else:
        query = AgentModelConfigModel.find_all()
    total = await query.count()
    items = await query.skip(skip).limit(params.page_size).to_list()
    results = [
        AgentModelConfigSchema(
            id=m.id,
            name=m.name,
            description=m.description,
            base_url=m.base_url,
            api_key=m.api_key,
            model=m.model,
            created_at=m.created_at,
            updated_at=m.updated_at,
        )
        for m in items
    ]
    return PageResponseSchema.create(results, total, params.page, params.page_size)
