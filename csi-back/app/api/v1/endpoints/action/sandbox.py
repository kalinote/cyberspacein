import asyncio
import logging

from fastapi import APIRouter, BackgroundTasks, Body, Depends

from app.schemas.action.sandbox import (
    SandboxBaseInfo,
    SandboxCreateRequest,
    SandboxCreateResponse,
    SandboxDetailResponse,
)
from app.schemas.general import PageParamsSchema, PageResponseSchema
from app.schemas.response import ApiResponseSchema
from app.service import sandbox as sandbox_service

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/sandbox",
    tags=["沙盒环境"],
)


@router.post("/create", response_model=ApiResponseSchema[SandboxCreateResponse], summary="创建沙盒")
async def create_sandbox(body: SandboxCreateRequest, background_tasks: BackgroundTasks):
    ok, message, data = await asyncio.to_thread(sandbox_service.create_sandbox, body.name, body.image_type)
    if not ok:
        code = 240004 if "端口池" in message or "未配置" in message else 250005
        return ApiResponseSchema.error(code=code, message=message)
    await sandbox_service.insert_sandbox_doc(
        container_id=data["sandbox_id"],
        container_name=data["name"],
        image_type=body.image_type,
        display_name=data.get("display_name"),
        host_port=data["host_port"],
        image=data["image"],
        created_at=data.get("created_at"),
        sandbox_status=data["sandbox_status"],
    )
    background_tasks.add_task(
        sandbox_service.start_sandbox_and_update_status,
        data["sandbox_id"],
        body.image_type,
    )
    return ApiResponseSchema.success(data=SandboxCreateResponse(**data))


@router.delete("/{sandbox_id}", response_model=ApiResponseSchema[None], summary="销毁沙盒")
async def delete_sandbox(sandbox_id: str):
    doc = await sandbox_service.get_sandbox_doc_by_container_id(sandbox_id)
    if not doc:
        return ApiResponseSchema.error(code=240416, message="沙盒不存在")
    ok, message = await asyncio.to_thread(sandbox_service.delete_sandbox, sandbox_id, doc.image_type)
    if not ok and "不存在" not in message:
        code = 240002 if "仅允许" in message else 250005
        return ApiResponseSchema.error(code=code, message=message)
    await sandbox_service.delete_sandbox_doc_by_container_id(sandbox_id)
    return ApiResponseSchema.success(message="success")


@router.get("/list", response_model=PageResponseSchema[SandboxBaseInfo], summary="沙盒列表")
async def list_sandboxes(params: PageParamsSchema = Depends()):
    skip = (params.page - 1) * params.page_size
    items, total = await sandbox_service.list_sandboxes_from_db(skip, params.page_size)
    results = [SandboxBaseInfo(**x) for x in items]
    return PageResponseSchema.create(results, total, params.page, params.page_size)


@router.get("/detail/{sandbox_id}", response_model=ApiResponseSchema[SandboxDetailResponse], summary="沙盒详情")
async def get_sandbox_detail(sandbox_id: str):
    ok, message, data = await sandbox_service.get_sandbox_detail_from_db(sandbox_id)
    if not ok:
        code = 240416 if "不存在" in message else 240004 if "不能为空" in message else 250005
        return ApiResponseSchema.error(code=code, message=message)
    return ApiResponseSchema.success(data=SandboxDetailResponse(**data))
