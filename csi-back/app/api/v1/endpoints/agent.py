import asyncio
import json
import logging
import re
from typing import Optional

from elasticsearch.exceptions import NotFoundError
from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import StreamingResponse

from app.db.elasticsearch import get_es
from app.models.agent.agent import AgentModel, AgentAnalysisSessionModel
from app.models.agent.configs import AgentModelConfigModel, AgentPromptTemplateModel
from app.schemas.agent.configs import AgentToolsParameterSchema, AgentToolsResponseSchema, ModelConfigListItemSchema
from app.schemas.constants import ENTITY_TYPE_INDEX_MAP
from app.schemas.general import PageParamsSchema, PageResponseSchema
from app.schemas.response import ApiResponseSchema
from app.schemas.agent.agent import (
    AgentCreateRequestSchema,
    AgentListItemSchema,
    AgentModelConfigCreateRequestSchema,
    AgentModelConfigSchema,
    AgentPromptTemplateCreateRequestSchema,
    AgentPromptTemplateSchema,
    AgentSchema,
    ApprovalRequiredPayloadSchema,
    ApproveRequestSchema,
    ApproveResponseSchema,
    ResultEventPayloadSchema,
    ResultPayloadSchema,
    StartAgentRequestSchema,
    StartAgentResponseSchema,
)
from app.service.agent.agent import AgentService
from app.service.agent.tools import all_tools
from app.utils.agent import inject_template_fields
from app.utils.id_lib import generate_id

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
    raw = data.name + data.prompt_template_id + data.model_id + str(data.llm_config) + ",".join(data.tools)
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
        model_id=data.model_id,
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
        model_id=doc.model_id,
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
            model_id=a.model_id,
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



@router.post("/start", response_model=ApiResponseSchema[StartAgentResponseSchema], summary="启动分析引擎")
async def start_agent(data: StartAgentRequestSchema):
    agent_template = await AgentModel.find_one({"_id": data.agent_id})
    if not agent_template:
        return ApiResponseSchema.error(code=404, message=f"分析引擎不存在，ID: {data.agent_id}")

    prompt_template = await AgentPromptTemplateModel.find_one({"_id": agent_template.prompt_template_id})
    if not prompt_template:
        raise ValueError(f"提示词模板不存在，ID: {agent_template.prompt_template_id}")

    es = get_es()
    index_name = ENTITY_TYPE_INDEX_MAP.get(data.entity_type)
    if not index_name:
        return ApiResponseSchema.error(code=400, message=f"不支持的实体类型: {data.entity_type}")

    try:
        result = await es.get(index=index_name, id=data.entity_uuid)
    except NotFoundError:
        return ApiResponseSchema.error(code=404, message=f"实体不存在，UUID: {data.entity_uuid}")

    doc_source = result.get("_source") or {}
    fields = {k: (v if v is not None else "!字段值缺失!") for k, v in doc_source.items()}

    system_prompt = prompt_template.system_prompt
    user_prompt = inject_template_fields(prompt_template.user_prompt, fields)
    
    model = await AgentModelConfigModel.find_one({"_id": agent_template.model_id})
    if not model:
        return ApiResponseSchema.error(code=404, message=f"模型配置不存在，ID: {agent_template.model_id}")
    
    try:
        thread_id = await AgentService.start_agent(system_prompt, user_prompt, agent_template, model, data)
    except Exception as e:
        return ApiResponseSchema.error(code=400, message=f"启动分析引擎失败: {str(e)}")
    return ApiResponseSchema.success(data=StartAgentResponseSchema(thread_id=thread_id))


@router.get("/status", summary="获取会话状态（SSE）")
async def get_agent_status(request: Request, thread_id: str = Query(..., description="会话ID")):
    doc = await AgentAnalysisSessionModel.find_one({"thread_id": thread_id})
    if not doc:
        return ApiResponseSchema.error(code=404, message="无该会话")
    queue = asyncio.Queue(maxsize=128)
    async with AgentService.sse_lock:
        AgentService.sse_subscribers.setdefault(thread_id, []).append(queue)
    async with AgentService.task_lock:
        is_running = thread_id in AgentService.running_tasks
    payload_schema = AgentService.session_to_status_payload(doc, is_running)
    initial = AgentService.sse_event("status", payload_schema)

    async def event_gen():
        try:
            yield f"data: {json.dumps(initial, ensure_ascii=False)}\n\n"
            init_data = initial.get("data") or {}
            if init_data.get("status") == "awaiting_approval" and init_data.get("pending_approval") is not None:
                approval_event = AgentService.sse_event(
                    "approval_required",
                    ApprovalRequiredPayloadSchema(payload=init_data["pending_approval"], thread_id=thread_id),
                )
                yield f"data: {json.dumps(approval_event, ensure_ascii=False)}\n\n"
            if init_data.get("status") in ("completed", "cancelled", "paused"):
                if doc.result:
                    try:
                        result_event = AgentService.sse_event(
                            "result",
                            ResultEventPayloadSchema(thread_id=thread_id, result=ResultPayloadSchema(**doc.result)),
                        )
                        yield f"data: {json.dumps(result_event, ensure_ascii=False)}\n\n"
                    except Exception:
                        pass
                return
            while True:
                if await request.is_disconnected():
                    break
                try:
                    payload = await asyncio.wait_for(queue.get(), timeout=30.0)
                    yield f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"
                    if (
                        payload.get("type") == "status"
                        and payload.get("data", {}).get("status") in ("completed", "cancelled", "paused")
                    ):
                        try:
                            next_payload = queue.get_nowait()
                            yield f"data: {json.dumps(next_payload, ensure_ascii=False)}\n\n"
                        except asyncio.QueueEmpty:
                            pass
                        break
                except asyncio.TimeoutError:
                    yield ": keepalive\n\n"
        except asyncio.CancelledError:
            pass
        finally:
            async with AgentService.sse_lock:
                if thread_id in AgentService.sse_subscribers:
                    try:
                        AgentService.sse_subscribers[thread_id].remove(queue)
                    except ValueError:
                        pass
                    if not AgentService.sse_subscribers[thread_id]:
                        del AgentService.sse_subscribers[thread_id]

    return StreamingResponse(
        event_gen(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.post("/approve", response_model=ApiResponseSchema[ApproveResponseSchema], summary="提交行为批准")
async def approve_agent(data: ApproveRequestSchema):
    q = AgentService.pending_resumes.get(data.thread_id)
    if q is None:
        return ApiResponseSchema.error(code=404, message="该会话当前无待确认的操作，或任务已结束")
    try:
        q.put_nowait(data.decisions)
    except asyncio.QueueFull:
        return ApiResponseSchema.error(code=409, message="已有决策待处理")
    return ApiResponseSchema.success(data=ApproveResponseSchema(thread_id=data.thread_id, status="approved"))
