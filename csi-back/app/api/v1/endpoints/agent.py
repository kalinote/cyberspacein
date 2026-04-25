import asyncio
import json
import re
from datetime import datetime
from typing import Any, Optional

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import StreamingResponse
from loguru import logger

from app.models.agent.configs import AgentModelConfigModel, AgentPromptTemplateModel
from app.models.agent.nanobot import NanobotAgentModel, NanobotWorkspaceModel
from app.schemas.agent.configs import ModelConfigListItemSchema
from app.schemas.general import PageParamsSchema, PageResponseSchema
from app.schemas.response import ApiResponseSchema
from app.schemas.agent.agent import (
    AgentModelConfigCreateRequestSchema,
    AgentModelConfigSchema,
    AgentPromptTemplateCreateRequestSchema,
    AgentPromptTemplateSchema,
    ApproveRequestSchema,
    CancelAgentRequestSchema,
    CancelAgentResponseSchema,
    StartAgentRequestSchema,
    StartAgentResponseSchema,
    ToolDescriptorSchema,
)
from app.schemas.agent.nanobot_agent import (
    AgentServiceError,
    NanobotAgentCreateRequestSchema,
    NanobotAgentListItemSchema,
    NanobotAgentSchema,
    NanobotAgentUpdateRequestSchema,
)
from app.schemas.agent.workspace import (
    NanobotWorkspaceCreateRequestSchema,
    NanobotWorkspaceListItemSchema,
    NanobotWorkspaceSchema,
    NanobotWorkspaceUpdateRequestSchema,
    WorkspaceServiceError,
)
from app.service.analyst.agent import AgentService
from app.service.analyst.service import AnalystService
from app.service.analyst.tools import BUSINESS_TOOL_CLASSES
from app.service.analyst.workspace import WorkspaceService
from app.utils.jinja_injection import render_user_prompt
import app.utils.status_codes as status_codes
from app.utils.id_lib import generate_id

logger = logger.bind(name=__name__)

router = APIRouter(
    prefix="/agent",
    tags=["分析引擎管理"],
)

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


@router.post("/workspaces", response_model=ApiResponseSchema[NanobotWorkspaceSchema], summary="新增工作区")
async def create_workspace(data: NanobotWorkspaceCreateRequestSchema):
    try:
        doc = await WorkspaceService.create(data)
    except WorkspaceServiceError as exc:
        return ApiResponseSchema.error(code=exc.code, message=exc.message, data=exc.data)
    return ApiResponseSchema.success(data=NanobotWorkspaceSchema.from_doc(doc))


@router.get("/workspaces", response_model=PageResponseSchema[NanobotWorkspaceSchema], summary="查询工作区列表")
async def get_workspace_list(
    params: PageParamsSchema = Depends(),
    search: Optional[str] = Query(None, description="搜索关键词，模糊匹配名称或描述"),
):
    items, total = await WorkspaceService.list_page(
        page=params.page, page_size=params.page_size, search=search
    )
    results = [NanobotWorkspaceSchema.from_doc(m) for m in items]
    return PageResponseSchema.create(results, total, params.page, params.page_size)


@router.get(
    "/workspaces-list",
    response_model=ApiResponseSchema[list[NanobotWorkspaceListItemSchema]],
    summary="查询工作区名称列表",
)
async def get_workspace_brief_list():
    items = await WorkspaceService.list_all_brief()
    results = [NanobotWorkspaceListItemSchema(id=m.id, name=m.name) for m in items]
    return ApiResponseSchema.success(data=results)


@router.get(
    "/workspaces/{workspace_id}",
    response_model=ApiResponseSchema[NanobotWorkspaceSchema],
    summary="查询工作区详情",
)
async def get_workspace_detail(workspace_id: str):
    try:
        doc = await WorkspaceService.get(workspace_id)
    except WorkspaceServiceError as exc:
        return ApiResponseSchema.error(code=exc.code, message=exc.message, data=exc.data)
    return ApiResponseSchema.success(data=NanobotWorkspaceSchema.from_doc(doc))


@router.put(
    "/workspaces/{workspace_id}",
    response_model=ApiResponseSchema[NanobotWorkspaceSchema],
    summary="编辑工作区",
)
async def update_workspace(workspace_id: str, data: NanobotWorkspaceUpdateRequestSchema):
    try:
        doc = await WorkspaceService.update(workspace_id, data)
    except WorkspaceServiceError as exc:
        return ApiResponseSchema.error(code=exc.code, message=exc.message, data=exc.data)
    return ApiResponseSchema.success(data=NanobotWorkspaceSchema.from_doc(doc))


@router.delete("/workspaces/{workspace_id}", response_model=ApiResponseSchema[Any], summary="删除工作区")
async def delete_workspace(workspace_id: str):
    try:
        await WorkspaceService.delete(workspace_id)
    except WorkspaceServiceError as exc:
        return ApiResponseSchema.error(code=exc.code, message=exc.message, data=exc.data)
    return ApiResponseSchema.success(data=None, message="删除成功")


@router.post("/agents", response_model=ApiResponseSchema[NanobotAgentSchema], summary="创建分析引擎")
async def create_agent(data: NanobotAgentCreateRequestSchema):
    try:
        doc = await AgentService.create(data)
    except AgentServiceError as exc:
        return ApiResponseSchema.error(code=exc.code, message=exc.message, data=exc.data)
    return ApiResponseSchema.success(data=NanobotAgentSchema.from_doc(doc))


@router.get("/agents", response_model=PageResponseSchema[NanobotAgentSchema], summary="查询分析引擎列表")
async def get_agent_list(
    params: PageParamsSchema = Depends(),
    workspace_id: Optional[str] = Query(None, description="按所属工作区ID过滤"),
    search: Optional[str] = Query(None, description="搜索关键词，模糊匹配名称或描述"),
):
    items, total = await AgentService.list_page(
        page=params.page,
        page_size=params.page_size,
        workspace_id=workspace_id,
        search=search,
    )
    results = [NanobotAgentSchema.from_doc(m) for m in items]
    return PageResponseSchema.create(results, total, params.page, params.page_size)


@router.get(
    "/agents-list",
    response_model=ApiResponseSchema[list[NanobotAgentListItemSchema]],
    summary="查询分析引擎名称列表",
)
async def get_agent_brief_list(
    workspace_id: Optional[str] = Query(None, description="按所属工作区ID过滤"),
):
    items = await AgentService.list_brief(workspace_id=workspace_id)
    results = [
        NanobotAgentListItemSchema(
            id=m.id, name=m.name, workspace_id=m.workspace_id, status=m.status
        )
        for m in items
    ]
    return ApiResponseSchema.success(data=results)


@router.get(
    "/agents/{agent_id}",
    response_model=ApiResponseSchema[NanobotAgentSchema],
    summary="查询分析引擎详情",
)
async def get_agent_detail(agent_id: str):
    try:
        doc = await AgentService.get(agent_id)
    except AgentServiceError as exc:
        return ApiResponseSchema.error(code=exc.code, message=exc.message, data=exc.data)
    return ApiResponseSchema.success(data=NanobotAgentSchema.from_doc(doc))


@router.put(
    "/agents/{agent_id}",
    response_model=ApiResponseSchema[NanobotAgentSchema],
    summary="编辑分析引擎",
)
async def update_agent(agent_id: str, data: NanobotAgentUpdateRequestSchema):
    try:
        doc = await AgentService.update(agent_id, data)
    except AgentServiceError as exc:
        return ApiResponseSchema.error(code=exc.code, message=exc.message, data=exc.data)
    return ApiResponseSchema.success(data=NanobotAgentSchema.from_doc(doc))


@router.delete("/agents/{agent_id}", response_model=ApiResponseSchema[Any], summary="删除分析引擎")
async def delete_agent(agent_id: str):
    try:
        await AgentService.delete(agent_id)
    except AgentServiceError as exc:
        return ApiResponseSchema.error(code=exc.code, message=exc.message, data=exc.data)
    return ApiResponseSchema.success(data=None, message="删除成功")


@router.get(
    "/configs/tools",
    response_model=ApiResponseSchema[list[ToolDescriptorSchema]],
    summary="查询可用业务工具列表（含元信息）",
)
async def get_agent_tools():
    """返回当前进程内 `BUSINESS_TOOL_CLASSES` 注册的全部业务工具描述。

    工具集在进程启动时静态注册，无需分页。前端在创建/编辑 Agent 时据此展示可勾选项。
    """
    results: list[ToolDescriptorSchema] = []
    for name, cls in BUSINESS_TOOL_CLASSES.items():
        try:
            instance = cls()
            results.append(
                ToolDescriptorSchema(
                    name=instance.name,
                    description=instance.description,
                    read_only=bool(instance.read_only),
                    exclusive=bool(instance.exclusive),
                )
            )
        except Exception as exc:
            logger.warning(f"构造工具描述失败，已跳过: {name} err={exc}")
    return ApiResponseSchema.success(data=results)


@router.get(
    "/configs/tools-list",
    response_model=ApiResponseSchema[list[str]],
    summary="查询可用业务工具名称列表",
)
async def get_agent_tools_list():
    return ApiResponseSchema.success(data=list(BUSINESS_TOOL_CLASSES.keys()))


@router.get("/configs/statistics", response_model=ApiResponseSchema[dict[str, int]], summary="配置资源数量统计")
async def get_configs_statistics():
    """返回各配置集合当前数量。前端概览面板使用。"""
    data = {
        "model_configs": await AgentModelConfigModel.find().count(),
        "prompt_templates": await AgentPromptTemplateModel.find().count(),
        "workspaces": await NanobotWorkspaceModel.find().count(),
        "agents": await NanobotAgentModel.find().count(),
        "business_tools": len(BUSINESS_TOOL_CLASSES),
    }
    return ApiResponseSchema.success(data=data)


@router.post(
    "/start",
    response_model=ApiResponseSchema[StartAgentResponseSchema],
    summary="启动分析引擎",
)
async def start_agent(data: StartAgentRequestSchema):
    try:
        context = {
            **data.extra_context,
            **({"entity_uuid": data.entity_uuid} if data.entity_uuid else {}),
            **({"entity_type": data.entity_type.value} if data.entity_type else {}),
        }

        raw_user_prompt = str(data.user_prompt or "").strip()
        if not raw_user_prompt:
            agent = await NanobotAgentModel.find_one({"_id": data.agent_id})
            if not agent:
                raise AgentServiceError(
                    status_codes.NOT_FOUND_AGENT,
                    f"Agent 不存在: {data.agent_id}",
                )

            tpl = await AgentPromptTemplateModel.find_one(
                {"_id": agent.prompt_template_id}
            )
            if not tpl:
                raise AgentServiceError(
                    status_codes.NOT_FOUND_TEMPLATE,
                    f"Agent 绑定的提示词模板不存在: {agent.prompt_template_id}",
                )

            prompt = str(tpl.user_prompt or "").strip()
            if not prompt:
                raise AgentServiceError(
                    status_codes.INVALID_ARGUMENT,
                    "该 Agent 的提示词模板默认 user_prompt 为空",
                    data={"prompt_template_id": agent.prompt_template_id},
                )
            raw_user_prompt = prompt

        final_user_prompt = render_user_prompt(raw_user_prompt, context).strip()
        if not final_user_prompt:
            raise AgentServiceError(
                status_codes.INVALID_ARGUMENT,
                "用户提示词为空，且模板渲染后仍为空",
            )

        session_id = await AnalystService.start_agent(
            agent_id=data.agent_id,
            user_prompt=final_user_prompt,
            context=context,
        )
    except AgentServiceError as exc:
        return ApiResponseSchema.error(code=exc.code, message=exc.message, data=exc.data)
    return ApiResponseSchema.success(
        data=StartAgentResponseSchema(agent_id=data.agent_id, session_id=session_id)
    )


@router.get("/status", summary="订阅 Agent 状态事件流（SSE）")
async def get_agent_status(
    request: Request,
    agent_id: str = Query(..., description="分析引擎ID"),
    debug: bool = Query(False, description="是否开启调试模式（开启后会通过 SSE 额外返回更详细信息）"),
):
    # 兼容：函数被直接调用时 debug 可能是 fastapi.Query(...) 对象而非 bool
    debug_enabled = (
        debug
        if isinstance(debug, bool)
        else bool(getattr(debug, "default", False))
    )
    try:
        queue = await AnalystService.subscribe(agent_id, debug=debug_enabled)
    except TypeError:
        # 测试/旧实现兼容：subscribe 可能不支持 debug 参数
        queue = await AnalystService.subscribe(agent_id)

    async def event_stream():
        try:
            while True:
                if await request.is_disconnected():
                    break
                try:
                    payload = await asyncio.wait_for(queue.get(), timeout=15.0)
                except asyncio.TimeoutError:
                    yield ": keep-alive\n\n"
                    continue
                event = payload.get("event", "message")
                data_str = json.dumps(payload.get("data"), ensure_ascii=False, default=str)
                event_id = payload.get("id")
                if event_id is not None:
                    yield f"id: {event_id}\nevent: {event}\ndata: {data_str}\n\n"
                else:
                    yield f"event: {event}\ndata: {data_str}\n\n"
        finally:
            await AnalystService.unsubscribe(agent_id, queue)

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.post("/approve", response_model=ApiResponseSchema[Any], summary="提交行为批准")
async def approve_agent(data: ApproveRequestSchema):
    try:
        await AnalystService.submit_approval(data.agent_id, data.decisions)
    except AgentServiceError as exc:
        return ApiResponseSchema.error(code=exc.code, message=exc.message, data=exc.data)
    return ApiResponseSchema.success(data=None, message="批准决策已提交")


@router.post(
    "/cancel",
    response_model=ApiResponseSchema[CancelAgentResponseSchema],
    summary="取消正在运行的分析引擎",
)
async def cancel_agent(data: CancelAgentRequestSchema):
    """向后台任务发出取消请求；最终状态落地由 `run_analysis.finally` 完成。

    如 agent 不存在于后台任务表（比如已经结束或从未启动），返回 cancelled=False 但仍 2xx。
    """
    cancelled = await AnalystService.cancel_agent(data.agent_id, reason=data.reason)
    return ApiResponseSchema.success(
        data=CancelAgentResponseSchema(agent_id=data.agent_id, cancelled=cancelled),
        message="取消请求已发送" if cancelled else "该 Agent 当前没有正在运行的任务",
    )
