from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query
from loguru import logger

from app.schemas.agent.configs import (
    AgentPromptBriefSchema,
    SystemPromptCreateRequestSchema,
    SystemPromptSchema,
    SystemPromptUpdateRequestSchema,
)
from app.schemas.constants import NanobotMemoryDocTypeEnum
from app.schemas.general import PageParamsSchema, PageResponseSchema
from app.schemas.response import ApiResponseSchema
from app.service.analyst.system_prompt import (
    SystemPromptService,
    SystemPromptServiceError,
)

logger = logger.bind(name=__name__)

router = APIRouter(prefix="/configs")


@router.post(
    "/system-prompts",
    response_model=ApiResponseSchema[SystemPromptSchema],
    summary="新增系统指令模板",
)
async def create_system_prompt(data: SystemPromptCreateRequestSchema):
    try:
        doc = await SystemPromptService.create(data)
    except SystemPromptServiceError as exc:
        return ApiResponseSchema.error(code=exc.code, message=exc.message, data=exc.data)
    return ApiResponseSchema.success(data=SystemPromptSchema.from_doc(doc))


@router.get(
    "/system-prompts",
    response_model=PageResponseSchema[SystemPromptSchema],
    summary="查询系统指令模板列表",
)
async def get_system_prompt_list(
    params: Annotated[PageParamsSchema, Depends()],
    workspace_id: Annotated[str | None, Query(description="按工作区ID过滤")] = None,
    prompt_type: Annotated[
        NanobotMemoryDocTypeEnum | None,
        Query(alias="type", description="按系统指令模板类型过滤"),
    ] = None,
    search: Annotated[
        str | None,
        Query(description="搜索关键词，模糊匹配名称、描述或内容"),
    ] = None,
):
    items, total = await SystemPromptService.list_page(
        page=params.page,
        page_size=params.page_size,
        workspace_id=workspace_id,
        type=prompt_type,
        search=search,
    )
    results = [SystemPromptSchema.from_doc(doc) for doc in items]
    return PageResponseSchema.create(results, total, params.page, params.page_size)


@router.get(
    "/system-prompts/{system_prompt_id}",
    response_model=ApiResponseSchema[SystemPromptSchema],
    summary="查询系统指令模板详情",
)
async def get_system_prompt_detail(system_prompt_id: str):
    try:
        doc = await SystemPromptService.get(system_prompt_id)
    except SystemPromptServiceError as exc:
        return ApiResponseSchema.error(code=exc.code, message=exc.message, data=exc.data)
    return ApiResponseSchema.success(data=SystemPromptSchema.from_doc(doc))


@router.put(
    "/system-prompts/{system_prompt_id}",
    response_model=ApiResponseSchema[SystemPromptSchema],
    summary="编辑系统指令模板",
)
async def update_system_prompt(system_prompt_id: str, data: SystemPromptUpdateRequestSchema):
    try:
        doc = await SystemPromptService.update(system_prompt_id, data)
    except SystemPromptServiceError as exc:
        return ApiResponseSchema.error(code=exc.code, message=exc.message, data=exc.data)
    return ApiResponseSchema.success(data=SystemPromptSchema.from_doc(doc))


@router.delete(
    "/system-prompts/{system_prompt_id}",
    response_model=ApiResponseSchema[Any],
    summary="删除系统指令模板",
)
async def delete_system_prompt(system_prompt_id: str):
    try:
        await SystemPromptService.delete(system_prompt_id)
    except SystemPromptServiceError as exc:
        return ApiResponseSchema.error(code=exc.code, message=exc.message, data=exc.data)
    return ApiResponseSchema.success(data=None, message="删除成功")

@router.get(
    "/filter/agent-prompts",
    response_model=ApiResponseSchema[list[AgentPromptBriefSchema]],
    summary="获取 AGENT 内置提示词简要列表",
)
async def list_agent_prompt_brief():
    items = await SystemPromptService.list_agent_prompt_brief()
    return ApiResponseSchema.success(
        data=[AgentPromptBriefSchema.model_validate(item) for item in items],
    )
