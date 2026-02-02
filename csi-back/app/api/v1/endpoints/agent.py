import logging
import re
from typing import Optional

from fastapi import APIRouter, Depends, Query

from app.schemas.agent.configs import AgentToolsParameterSchema, AgentToolsResponseSchema
from app.schemas.response import ApiResponseSchema
from app.schemas.general import PageParamsSchema, PageResponseSchema
from app.schemas.agent.agent import (
    AgentCreateRequestSchema,
    AgentListItemSchema,
    AgentModelConfigCreateRequestSchema,
    AgentModelConfigSchema,
    AgentPromptTemplateCreateRequestSchema,
    AgentPromptTemplateSchema,
    AgentSchema,
)
from app.models.agent.agent import AgentModel
from app.models.agent.configs import AgentModelConfigModel, AgentPromptTemplateModel
from app.utils.id_lib import generate_id
from app.service.agent.tools import all_tools

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/agent",
    tags=["分析引擎管理"],
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
    query = AgentModelConfigModel.find(query_filters)
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


@router.post("/configs/prompt-templates", response_model=ApiResponseSchema[AgentPromptTemplateSchema], summary="新增提示词模板")
async def create_agent_prompt_template(data: AgentPromptTemplateCreateRequestSchema):
    template_id = generate_id(data.name + data.system_prompt + data.user_prompt)
    existing = await AgentPromptTemplateModel.find_one({"_id": template_id})
    if existing:
        return ApiResponseSchema.error(code=400, message="同名且同内容的模板已存在")
    existing_by_name = await AgentPromptTemplateModel.find_one({"name": data.name})
    if existing_by_name:
        return ApiResponseSchema.error(code=400, message=f"提示词模板名称已存在: {data.name}")
    doc = AgentPromptTemplateModel(
        id=template_id,
        name=data.name,
        description=data.description,
        system_prompt=data.system_prompt,
        user_prompt=data.user_prompt,
    )
    await doc.insert()
    logger.info(f"成功创建提示词模板: {template_id} - {data.name}")
    return ApiResponseSchema.success(data=AgentPromptTemplateSchema(
        id=doc.id,
        name=doc.name,
        description=doc.description,
        system_prompt=doc.system_prompt,
        user_prompt=doc.user_prompt,
        created_at=doc.created_at,
        updated_at=doc.updated_at,
    ))


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
    results = [
        AgentPromptTemplateSchema(
            id=t.id,
            name=t.name,
            description=t.description,
            system_prompt=t.system_prompt,
            user_prompt=t.user_prompt,
            created_at=t.created_at,
            updated_at=t.updated_at,
        )
        for t in items
    ]
    return PageResponseSchema.create(results, total, params.page, params.page_size)


@router.post("/agents", response_model=ApiResponseSchema[AgentSchema], summary="创建分析引擎")
async def create_agent(data: AgentCreateRequestSchema):
    raw = data.name + data.prompt_template_id + str(data.llm_config) + ",".join(data.tools)
    agent_id = generate_id(raw)
    existing = await AgentModel.find_one({"_id": agent_id})
    if existing:
        return ApiResponseSchema.error(code=400, message="该分析引擎已存在")
    existing_by_name = await AgentModel.find_one({"name": data.name})
    if existing_by_name:
        return ApiResponseSchema.error(code=400, message=f"分析引擎名称已存在: {data.name}")
    doc = AgentModel(
        id=agent_id,
        name=data.name,
        description=data.description,
        prompt_template_id=data.prompt_template_id,
        llm_config=data.llm_config,
        tools=data.tools,
    )
    await doc.insert()
    logger.info(f"成功创建分析引擎: {agent_id} - {data.name}")
    return ApiResponseSchema.success(data=AgentSchema(
        id=doc.id,
        name=doc.name,
        description=doc.description,
        prompt_template_id=doc.prompt_template_id,
        llm_config=doc.llm_config,
        tools=doc.tools,
        created_at=doc.created_at,
        updated_at=doc.updated_at,
    ))


@router.get("/agents", response_model=PageResponseSchema[AgentSchema], summary="查询分析引擎列表")
async def get_agent_list(
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
    query = AgentModel.find(query_filters)
    total = await query.count()
    items = await query.skip(skip).limit(params.page_size).to_list()
    results = [
        AgentSchema(
            id=a.id,
            name=a.name,
            description=a.description,
            prompt_template_id=a.prompt_template_id,
            llm_config=a.llm_config,
            tools=a.tools,
            created_at=a.created_at,
            updated_at=a.updated_at,
        )
        for a in items
    ]
    return PageResponseSchema.create(results, total, params.page, params.page_size)

@router.get("/configs/agents-list", response_model=ApiResponseSchema[list[AgentListItemSchema]], summary="查询分析引擎名称列表")
async def get_agent_agents_list():
    items = await AgentModel.find_all().to_list()
    results = [AgentListItemSchema(id=a.id, name=a.name) for a in items]
    return ApiResponseSchema.success(data=results)

@router.get("/configs/tools", response_model=ApiResponseSchema[list[AgentToolsResponseSchema]], summary="查询工具列表")
async def get_agent_tools():
    results = []
    for t in all_tools.values():
        params = []
        if hasattr(t, "args_schema") and t.args_schema is not None:
            get_schema = getattr(t.args_schema, "model_json_schema", None) or getattr(t.args_schema, "schema", None)
            schema = get_schema() if get_schema else {}
            props = schema.get("properties", {})
            required_list = schema.get("required", [])
            for name, info in props.items():
                req = name in required_list
                default = info.get("default", "无默认值")
                desc = info.get("description", "") or "无说明"
                typ = info.get("type", info.get("anyOf", "?"))
                if isinstance(typ, list):
                    typ = typ[0].get("type", "?") if typ else "?"
                params.append(AgentToolsParameterSchema(
                    name=name,
                    description=desc,
                    type=typ if isinstance(typ, str) else str(typ),
                    required=req,
                    default=default if default is not None else "None",
                ))
        results.append(AgentToolsResponseSchema(
            name=t.name,
            description=t.description or "",
            parameters=params,
        ))
    return ApiResponseSchema.success(data=results)


@router.get("/configs/tools-list", response_model=ApiResponseSchema[list[str]], summary="查询工具名称列表")
async def get_agent_tools_list():
    return ApiResponseSchema.success(data=list(all_tools.keys()))
