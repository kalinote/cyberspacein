import re
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, Query
from loguru import logger

from app.models.agent.configs import AgentPromptTemplateModel
from app.schemas.agent.agent import AgentPromptTemplateCreateRequestSchema, AgentPromptTemplateSchema
from app.schemas.general import PageParamsSchema, PageResponseSchema
from app.schemas.response import ApiResponseSchema
from app.utils.id_lib import generate_id
import app.utils.status_codes as status_codes

logger = logger.bind(name=__name__)

router = APIRouter(prefix="/configs")


@router.post("/prompt-templates", response_model=ApiResponseSchema[AgentPromptTemplateSchema], summary="新增提示词模板")
async def create_agent_prompt_template(data: AgentPromptTemplateCreateRequestSchema):
    template_id = generate_id(data.name + data.system_prompt + data.user_prompt)
    existing = await AgentPromptTemplateModel.find_one({"_id": template_id})
    if existing:
        return ApiResponseSchema.error(code=status_codes.CONFLICT_EXISTS, message="同名且同内容的模板已存在")
    existing_by_name = await AgentPromptTemplateModel.find_one({"name": data.name})
    if existing_by_name:
        return ApiResponseSchema.error(code=status_codes.CONFLICT_NAME, message=f"提示词模板名称已存在: {data.name}")
    doc = AgentPromptTemplateModel(
        id=template_id,
        name=data.name,
        description=data.description,
        system_prompt=data.system_prompt,
        user_prompt=data.user_prompt,
    )
    await doc.insert()
    logger.info(f"成功创建提示词模板: {template_id} - {data.name}")
    return ApiResponseSchema.success(data=AgentPromptTemplateSchema.from_doc(doc))


@router.get("/prompt-templates", response_model=PageResponseSchema[AgentPromptTemplateSchema], summary="查询提示词模板列表")
async def get_agent_prompt_template_list(
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
    query = AgentPromptTemplateModel.find(query_filters)
    total = await query.count()
    items = await query.skip(skip).limit(params.page_size).to_list()
    results = [AgentPromptTemplateSchema.from_doc(t) for t in items]
    return PageResponseSchema.create(results, total, params.page, params.page_size)


@router.get("/prompt-template/{prompt_template_id}", response_model=ApiResponseSchema[AgentPromptTemplateSchema], summary="查询提示词模板详情")
async def get_agent_prompt_template_detail(prompt_template_id: str):
    doc = await AgentPromptTemplateModel.find_one({"_id": prompt_template_id})
    if not doc:
        return ApiResponseSchema.error(code=status_codes.NOT_FOUND_TEMPLATE, message="提示词模板不存在")
    return ApiResponseSchema.success(data=AgentPromptTemplateSchema.from_doc(doc))


@router.put("/prompt-template/{prompt_template_id}", response_model=ApiResponseSchema[AgentPromptTemplateSchema], summary="编辑提示词模板")
async def update_agent_prompt_template(prompt_template_id: str, data: AgentPromptTemplateCreateRequestSchema):
    doc = await AgentPromptTemplateModel.find_one({"_id": prompt_template_id})
    if not doc:
        return ApiResponseSchema.error(code=status_codes.NOT_FOUND_TEMPLATE, message="提示词模板不存在")
    if data.name != doc.name:
        existing_by_name = await AgentPromptTemplateModel.find_one({"name": data.name})
        if existing_by_name and existing_by_name.id != prompt_template_id:
            return ApiResponseSchema.error(code=status_codes.CONFLICT_NAME, message=f"提示词模板名称已存在: {data.name}")
    doc.name = data.name
    doc.description = data.description
    doc.system_prompt = data.system_prompt
    doc.user_prompt = data.user_prompt
    doc.updated_at = datetime.now()
    await doc.save()
    return ApiResponseSchema.success(data=AgentPromptTemplateSchema.from_doc(doc))

