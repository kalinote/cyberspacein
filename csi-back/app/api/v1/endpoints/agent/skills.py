from typing import Any, Optional

from fastapi import APIRouter, Depends, File, Query, UploadFile
from loguru import logger

import app.utils.status_codes as status_codes
from app.schemas.agent.skill import (
    NanobotSkillDetailSchema,
    NanobotSkillListItemSchema,
    SkillCreateRequestSchema,
    SkillFileBriefSchema,
    SkillFileContentSchema,
    SkillFileCreateRequestSchema,
    SkillFileUpsertRequestSchema,
    SkillServiceError,
    SkillUpdateRequestSchema,
    SkillUploadResponseSchema,
)
from app.schemas.general import PageParamsSchema, PageResponseSchema
from app.schemas.response import ApiResponseSchema
from app.service.analyst.skill_admin import SkillAdminService
from app.service.analyst.skill_service import SkillService
from app.service.analyst.skill_upload import SkillUploadService

logger = logger.bind(name=__name__)

router = APIRouter(prefix="/skills")


@router.post(
    "/upload",
    response_model=ApiResponseSchema[SkillUploadResponseSchema],
    summary="上传 Skill（zip）",
)
async def upload_skill(file: UploadFile = File(..., description="Skill 包 zip（支持单 skill 扁平/目录包裹，或多 skill 顶层目录）")):
    try:
        raw = await file.read()
        items = await SkillUploadService.upload_zip(raw, filename=file.filename or "")
        result = SkillUploadResponseSchema(skills=items, total=len(items))
    except SkillServiceError as exc:
        return ApiResponseSchema.error(code=exc.code, message=exc.message, data=exc.data)
    return ApiResponseSchema.success(data=result)


@router.get(
    "",
    response_model=PageResponseSchema[NanobotSkillListItemSchema],
    summary="分页查询 Skill 列表",
)
async def list_skills(
    params: PageParamsSchema = Depends(),
    search: Optional[str] = Query(None, description="按名称或描述模糊搜索"),
):
    rows, total = await SkillService.list_page(
        page=params.page,
        page_size=params.page_size,
        search=search,
    )
    results = [
        NanobotSkillListItemSchema(
            id=doc.id,
            name=doc.name,
            description=doc.description,
            always=doc.always,
            file_count=fc,
            created_at=doc.created_at,
            updated_at=doc.updated_at,
        )
        for doc, fc in rows
    ]
    return PageResponseSchema.create(results, total, params.page, params.page_size)


@router.post(
    "",
    response_model=ApiResponseSchema[NanobotSkillDetailSchema],
    summary="创建 Skill",
)
async def create_skill(data: SkillCreateRequestSchema):
    try:
        doc = await SkillAdminService.create(
            name=data.name,
            description=data.description,
            always=data.always,
            meta=data.meta,
            skill_md_body=data.skill_md_body,
        )
    except SkillServiceError as exc:
        return ApiResponseSchema.error(code=exc.code, message=exc.message, data=exc.data)
    file_docs = await SkillService.list_files(doc.id)
    return ApiResponseSchema.success(
        data=NanobotSkillDetailSchema(
            id=doc.id,
            name=doc.name,
            description=doc.description,
            always=doc.always,
            meta=dict(doc.meta or {}),
            files=[
                SkillFileBriefSchema(path=f.path, file_type=f.file_type)
                for f in file_docs
            ],
            created_at=doc.created_at,
            updated_at=doc.updated_at,
        ),
    )


@router.put(
    "/{skill_id}",
    response_model=ApiResponseSchema[NanobotSkillDetailSchema],
    summary="更新 Skill 元数据",
)
async def update_skill(skill_id: str, data: SkillUpdateRequestSchema):
    try:
        doc = await SkillAdminService.update_meta(
            skill_id,
            name=data.name,
            description=data.description,
            always=data.always,
            meta=data.meta,
        )
    except SkillServiceError as exc:
        return ApiResponseSchema.error(code=exc.code, message=exc.message, data=exc.data)
    file_docs = await SkillService.list_files(skill_id)
    return ApiResponseSchema.success(
        data=NanobotSkillDetailSchema(
            id=doc.id,
            name=doc.name,
            description=doc.description,
            always=doc.always,
            meta=dict(doc.meta or {}),
            files=[
                SkillFileBriefSchema(path=f.path, file_type=f.file_type)
                for f in file_docs
            ],
            created_at=doc.created_at,
            updated_at=doc.updated_at,
        ),
    )


@router.delete(
    "/{skill_id}",
    response_model=ApiResponseSchema[Any],
    summary="删除 Skill",
)
async def delete_skill(skill_id: str):
    try:
        await SkillAdminService.delete(skill_id)
    except SkillServiceError as exc:
        return ApiResponseSchema.error(code=exc.code, message=exc.message, data=exc.data)
    return ApiResponseSchema.success(data=None, message="删除成功")


@router.get(
    "/{skill_id}/files/content",
    response_model=ApiResponseSchema[SkillFileContentSchema],
    summary="读取 Skill 单文件内容",
)
async def get_skill_file_content(
    skill_id: str,
    path: str = Query(..., description="相对路径，如 SKILL.md、references/foo.md"),
):
    try:
        file_doc = await SkillAdminService.get_file_content(skill_id, path)
    except SkillServiceError as exc:
        return ApiResponseSchema.error(code=exc.code, message=exc.message, data=exc.data)
    return ApiResponseSchema.success(
        data=SkillFileContentSchema(
            path=file_doc.path,
            file_type=file_doc.file_type,
            content=file_doc.content,
            updated_at=file_doc.updated_at,
        ),
    )


@router.put(
    "/{skill_id}/files/content",
    response_model=ApiResponseSchema[SkillFileContentSchema],
    summary="更新 Skill 单文件内容",
)
async def update_skill_file_content(
    skill_id: str,
    data: SkillFileUpsertRequestSchema,
    path: str = Query(..., description="相对路径"),
):
    try:
        file_doc = await SkillAdminService.upsert_file_content(skill_id, path, data.content)
    except SkillServiceError as exc:
        return ApiResponseSchema.error(code=exc.code, message=exc.message, data=exc.data)
    return ApiResponseSchema.success(
        data=SkillFileContentSchema(
            path=file_doc.path,
            file_type=file_doc.file_type,
            content=file_doc.content,
            updated_at=file_doc.updated_at,
        ),
    )


@router.post(
    "/{skill_id}/files",
    response_model=ApiResponseSchema[SkillFileContentSchema],
    summary="新增 Skill 文件",
)
async def create_skill_file(skill_id: str, data: SkillFileCreateRequestSchema):
    try:
        file_doc = await SkillAdminService.create_file(skill_id, data.path, data.content)
    except SkillServiceError as exc:
        return ApiResponseSchema.error(code=exc.code, message=exc.message, data=exc.data)
    return ApiResponseSchema.success(
        data=SkillFileContentSchema(
            path=file_doc.path,
            file_type=file_doc.file_type,
            content=file_doc.content,
            updated_at=file_doc.updated_at,
        ),
    )


@router.delete(
    "/{skill_id}/files",
    response_model=ApiResponseSchema[Any],
    summary="删除 Skill 单文件",
)
async def delete_skill_file(
    skill_id: str,
    path: str = Query(..., description="相对路径（不可为 SKILL.md）"),
):
    try:
        await SkillAdminService.delete_file(skill_id, path)
    except SkillServiceError as exc:
        return ApiResponseSchema.error(code=exc.code, message=exc.message, data=exc.data)
    return ApiResponseSchema.success(data=None, message="删除成功")


@router.get(
    "/{skill_id}",
    response_model=ApiResponseSchema[NanobotSkillDetailSchema],
    summary="查询 Skill 详情",
)
async def get_skill_detail(skill_id: str):
    doc = await SkillService.get_by_id(skill_id)
    if doc is None:
        return ApiResponseSchema.error(
            code=status_codes.NOT_FOUND,
            message=f"Skill 不存在: {skill_id}",
        )
    file_docs = await SkillService.list_files(skill_id)
    return ApiResponseSchema.success(
        data=NanobotSkillDetailSchema(
            id=doc.id,
            name=doc.name,
            description=doc.description,
            always=doc.always,
            meta=dict(doc.meta or {}),
            files=[
                SkillFileBriefSchema(path=f.path, file_type=f.file_type)
                for f in file_docs
            ],
            created_at=doc.created_at,
            updated_at=doc.updated_at,
        ),
    )
