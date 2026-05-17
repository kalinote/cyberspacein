from typing import Optional

from fastapi import APIRouter, Depends, Query

from app.schemas.agent.nanobot_session import NanobotSessionSchema
from app.schemas.constants import NanobotSessionStatusEnum
from app.schemas.general import PageParamsSchema, PageResponseSchema
from app.service.analyst.session import SessionService

router = APIRouter()


@router.get(
    "/sessions",
    response_model=PageResponseSchema[NanobotSessionSchema],
    summary="查询分析会话列表",
)
async def get_session_list(
    params: PageParamsSchema = Depends(),
    agent_id: Optional[str] = Query(None, description="按所属 AgentID 过滤"),
    workspace_id: Optional[str] = Query(None, description="按工作区ID过滤"),
    status: Optional[NanobotSessionStatusEnum] = Query(None, description="按会话运行状态过滤"),
):
    items, total = await SessionService.list_page(
        page=params.page,
        page_size=params.page_size,
        agent_id=agent_id,
        workspace_id=workspace_id,
        status=status,
    )
    return PageResponseSchema.create(items, total, params.page, params.page_size)
