import asyncio
import logging

from fastapi import APIRouter, Body, Depends

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
async def create_sandbox(body: SandboxCreateRequest = Body(default=SandboxCreateRequest())):
    ok, message, data = await asyncio.to_thread(sandbox_service.create_sandbox, body.name)
    if not ok:
        code = 400 if "端口池" in message or "未配置" in message else 500
        return ApiResponseSchema.error(code=code, message=message)
    return ApiResponseSchema.success(data=SandboxCreateResponse(**data))


@router.delete("/{sandbox_id}", response_model=ApiResponseSchema[None], summary="销毁沙盒")
async def delete_sandbox(sandbox_id: str):
    ok, message = await asyncio.to_thread(sandbox_service.delete_sandbox, sandbox_id)
    if not ok:
        code = 404 if "不存在" in message else 400 if "仅允许" in message else 500
        return ApiResponseSchema.error(code=code, message=message)
    return ApiResponseSchema.success(message=message)


@router.get("/list", response_model=PageResponseSchema[SandboxBaseInfo], summary="沙盒列表")
async def list_sandboxes(params: PageParamsSchema = Depends()):
    skip = (params.page - 1) * params.page_size
    items, total = await asyncio.to_thread(sandbox_service.list_sandboxes, skip, params.page_size)
    results = [SandboxBaseInfo(**x) for x in items]
    return PageResponseSchema.create(results, total, params.page, params.page_size)


@router.get("/detail/{sandbox_id}", response_model=ApiResponseSchema[SandboxDetailResponse], summary="沙盒详情")
async def get_sandbox_detail(sandbox_id: str):
    ok, message, data = await asyncio.to_thread(sandbox_service.get_sandbox_detail, sandbox_id)
    if not ok:
        code = 404 if "不存在" in message else 400 if "仅允许" in message or "不能为空" in message else 500
        return ApiResponseSchema.error(code=code, message=message)
    return ApiResponseSchema.success(data=SandboxDetailResponse(**data))
