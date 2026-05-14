from typing import Any, Optional

from fastapi import APIRouter, Depends, Query
from loguru import logger

from app.schemas.agent.nanobot_agent import (
    AgentServiceError,
    NanobotAgentCreateRequestSchema,
    NanobotAgentListItemSchema,
    NanobotAgentSchema,
    NanobotAgentUpdateRequestSchema,
)
from app.schemas.general import PageParamsSchema, PageResponseSchema
from app.schemas.response import ApiResponseSchema
from app.service.analyst.agent import AgentService

logger = logger.bind(name=__name__)

router = APIRouter()


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
        NanobotAgentListItemSchema(id=m.id, name=m.name, workspace_id=m.workspace_id)
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

