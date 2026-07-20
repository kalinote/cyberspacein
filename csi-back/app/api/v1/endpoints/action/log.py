from fastapi import APIRouter, Query

from app.models.action.action import ActionInstanceNodeModel
from app.schemas.action.log import ActionNodeLogPage
from app.schemas.response import ApiResponseSchema
from app.service.action_log import ActionLogService


router = APIRouter(tags=["行动节点日志"])


@router.get(
    "/nodes/{node_instance_id}/logs",
    response_model=ApiResponseSchema[ActionNodeLogPage],
    summary="查询节点运行日志",
)
async def get_node_logs(
    node_instance_id: str,
    cursor: str | None = None,
    before_cursor: str | None = None,
    limit: int = Query(default=200, ge=1, le=500),
    levels: list[str] | None = Query(default=None),
    sources: list[str] | None = Query(default=None),
    component_run_id: str | None = None,
    keyword: str | None = Query(default=None, max_length=256),
):
    node = await ActionInstanceNodeModel.find_one({"_id": node_instance_id})
    if node is None:
        return ApiResponseSchema.error(code=240417, message="节点实例不存在")
    try:
        page = await ActionLogService.query(
            node_instance_id,
            cursor=cursor,
            before_cursor=before_cursor,
            limit=limit,
            levels=levels,
            sources=sources,
            component_run_id=component_run_id,
            keyword=keyword,
        )
    except ValueError as exc:
        return ApiResponseSchema.error(code=240420, message=str(exc))
    return ApiResponseSchema.success(data=page)
