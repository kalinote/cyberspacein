import logging
from fastapi import APIRouter, BackgroundTasks, Path

from app.core.config import settings
from app.schemas.constants import EntityType
from app.schemas.response import ApiResponseSchema
from app.service.analyze import (
    _get_es_doc,
    get_task,
    is_content_analysis_running,
    run_content_analysis,
    upsert_start_content_analysis,
)

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/analyze",
    tags=["analyze"],
)


@router.post("/content/{entity_type}/{uuid}", response_model=ApiResponseSchema, summary="提交内容分析任务")
async def analyze_content(
    background_tasks: BackgroundTasks,
    entity_type: EntityType = Path(..., description="实体类型"),
    uuid: str = Path(..., description="实体UUID"),
):
    et = entity_type.value
    if not (settings.ML_SERVICE_BASE_URL or "").strip():
        return ApiResponseSchema.error(code=503, message="ML 服务未配置 ML_SERVICE_BASE_URL")
    doc = await _get_es_doc(et, uuid)
    if not doc:
        return ApiResponseSchema.error(code=400, message="ES 文档不存在")
    raw = (doc.get("raw_content") or "").strip()
    if not raw:
        return ApiResponseSchema.error(code=400, message="文档缺少 raw_content")

    task = await get_task(et, uuid)
    if is_content_analysis_running(task):
        return ApiResponseSchema.error(code=409, message="该实体已有进行中的内容分析任务")

    await upsert_start_content_analysis(et, uuid)
    background_tasks.add_task(run_content_analysis, et, uuid)
    return ApiResponseSchema.success(
        data={"entity_type": et, "uuid": uuid},
        message="任务已下发",
    )


@router.get("/status/{entity_type}/{uuid}", response_model=ApiResponseSchema, summary="查询分析进度与结果")
async def get_analyze_status(
    entity_type: EntityType = Path(..., description="实体类型"),
    uuid: str = Path(..., description="实体UUID"),
):
    et = entity_type.value
    task = await get_task(et, uuid)
    if not task:
        return ApiResponseSchema.success(
            data={
                "entity_type": et,
                "uuid": uuid,
                "created_at": None,
                "updated_at": None,
                "steps": {},
            },
            message="暂无分析任务记录",
        )
    return ApiResponseSchema.success(
        data={
            "entity_type": task.entity_type,
            "uuid": task.uuid,
            "created_at": task.created_at,
            "updated_at": task.updated_at,
            "steps": task.steps or {},
        },
    )
