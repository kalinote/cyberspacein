from typing import Any, Optional

from fastapi import APIRouter, Depends, Query
from loguru import logger

from app.schemas.agent.workspace import (
    NanobotWorkspaceCreateRequestSchema,
    NanobotWorkspaceListItemSchema,
    NanobotWorkspaceSchema,
    NanobotWorkspaceUpdateRequestSchema,
    WorkspaceServiceError,
)
from app.schemas.general import PageParamsSchema, PageResponseSchema
from app.schemas.response import ApiResponseSchema
from app.service.analyst.workspace import WorkspaceService

logger = logger.bind(name=__name__)

router = APIRouter()


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

