import re
from loguru import logger
from datetime import datetime
from typing import Any, Optional

from fastapi import APIRouter, Depends, Query, Request

from app.models.agent.configs import AgentModelConfigModel, AgentPromptTemplateModel
from app.schemas.agent.configs import ModelConfigListItemSchema
from app.schemas.general import PageParamsSchema, PageResponseSchema
from app.schemas.response import ApiResponseSchema
from app.schemas.agent.agent import (
    AgentCreateRequestSchema,
    AgentModelConfigCreateRequestSchema,
    AgentModelConfigSchema,
    AgentPromptTemplateCreateRequestSchema,
    AgentPromptTemplateSchema,
    ApproveRequestSchema,
    StartAgentRequestSchema,
)
import app.utils.status_codes as status_codes
from app.utils.id_lib import generate_id

logger = logger.bind(name=__name__)

router = APIRouter(
    prefix="/agent",
    tags=["分析引擎管理"],
)

PLACEHOLDER_MESSAGE = "Agent 系统正在使用 nanobot 重构中，该接口暂未实现"


@router.post("/configs/models", response_model=ApiResponseSchema[AgentModelConfigSchema], summary="新增模型配置")
async def create_agent_model_config(data: AgentModelConfigCreateRequestSchema):
    config_id = generate_id(data.name + data.base_url + data.model)
    existing = await AgentModelConfigModel.find_one({"_id": config_id})
    if existing:
        return ApiResponseSchema.error(code=status_codes.CONFLICT_EXISTS, message="同名且同基础URL、同模型ID的配置已存在")
    existing_by_name = await AgentModelConfigModel.find_one({"name": data.name})
    if existing_by_name:
        return ApiResponseSchema.error(code=status_codes.CONFLICT_NAME, message=f"模型名称已存在: {data.name}")
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
    return ApiResponseSchema.success(data=AgentModelConfigSchema.from_doc(doc))


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
    query = AgentModelConfigModel.find(query_filters)
    total = await query.count()
    items = await query.skip(skip).limit(params.page_size).to_list()
    results = [AgentModelConfigSchema.from_doc(m) for m in items]
    return PageResponseSchema.create(results, total, params.page, params.page_size)


@router.get("/configs/models-list", response_model=ApiResponseSchema[list[ModelConfigListItemSchema]], summary="查询模型配置名称列表")
async def get_agent_models_list():
    items = await AgentModelConfigModel.find_all().to_list()
    results = [ModelConfigListItemSchema(id=m.id, name=m.name) for m in items]
    return ApiResponseSchema.success(data=results)


@router.post("/configs/prompt-templates", response_model=ApiResponseSchema[AgentPromptTemplateSchema], summary="新增提示词模板")
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


@router.get("/configs/prompt-templates", response_model=PageResponseSchema[AgentPromptTemplateSchema], summary="查询提示词模板列表")
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


@router.get("/configs/prompt-template/{prompt_template_id}", response_model=ApiResponseSchema[AgentPromptTemplateSchema], summary="查询提示词模板详情")
async def get_agent_prompt_template_detail(prompt_template_id: str):
    doc = await AgentPromptTemplateModel.find_one({"_id": prompt_template_id})
    if not doc:
        return ApiResponseSchema.error(code=status_codes.NOT_FOUND_TEMPLATE, message="提示词模板不存在")
    return ApiResponseSchema.success(data=AgentPromptTemplateSchema.from_doc(doc))


@router.put("/configs/prompt-template/{prompt_template_id}", response_model=ApiResponseSchema[AgentPromptTemplateSchema], summary="编辑提示词模板")
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


@router.post("/agents", response_model=ApiResponseSchema[Any], summary="创建分析引擎")
async def create_agent(data: AgentCreateRequestSchema):
    return ApiResponseSchema.success(data=None, message=PLACEHOLDER_MESSAGE)


@router.get("/agents", response_model=ApiResponseSchema[Any], summary="查询分析引擎列表")
async def get_agent_list(
    params: PageParamsSchema = Depends(),
    search: Optional[str] = Query(None, description="搜索关键词，模糊匹配名称或描述"),
):
    return ApiResponseSchema.success(data=None, message=PLACEHOLDER_MESSAGE)


@router.get("/configs/agents-list", response_model=ApiResponseSchema[Any], summary="查询分析引擎名称列表")
async def get_agent_agents_list():
    return ApiResponseSchema.success(data=None, message=PLACEHOLDER_MESSAGE)


@router.get("/configs/tools", response_model=ApiResponseSchema[Any], summary="查询工具列表")
async def get_agent_tools():
    return ApiResponseSchema.success(data=None, message=PLACEHOLDER_MESSAGE)


@router.get("/configs/tools-list", response_model=ApiResponseSchema[Any], summary="查询工具名称列表")
async def get_agent_tools_list():
    return ApiResponseSchema.success(data=None, message=PLACEHOLDER_MESSAGE)


@router.get("/configs/statistics", response_model=ApiResponseSchema[Any], summary="配置资源数量统计")
async def get_configs_statistics():
    return ApiResponseSchema.success(data=None, message=PLACEHOLDER_MESSAGE)


@router.post("/start", response_model=ApiResponseSchema[Any], summary="启动分析引擎")
async def start_agent(data: StartAgentRequestSchema):
    return ApiResponseSchema.success(data=None, message=PLACEHOLDER_MESSAGE)


@router.get("/status", response_model=ApiResponseSchema[Any], summary="获取会话状态（SSE）")
async def get_agent_status(request: Request, thread_id: str = Query(..., description="会话ID")):
    return ApiResponseSchema.success(data=None, message=PLACEHOLDER_MESSAGE)


@router.post("/approve", response_model=ApiResponseSchema[Any], summary="提交行为批准")
async def approve_agent(data: ApproveRequestSchema):
    return ApiResponseSchema.success(data=None, message=PLACEHOLDER_MESSAGE)
