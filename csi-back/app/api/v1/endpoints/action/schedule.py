import re
from datetime import datetime
from uuid import uuid4

from fastapi import APIRouter, Depends, Query

from app.models.action.action import ActionInstanceModel, ActionInstanceNodeModel
from app.models.action.blueprint import ActionBlueprintModel
from app.models.action.schedule import ActionScheduleModel
from app.schemas.action.schedule import (
    ActionScheduleCreateRequest,
    ActionSchedulePayload,
    ActionSchedulePreviewRequest,
    ActionSchedulePreviewResponse,
    ActionScheduleResponse,
    ActionScheduleRunResponse,
    ActionScheduleSummaryResponse,
    ActionSchedulerStatusResponse,
    ActionScheduleUpdateRequest,
)
from app.schemas.constants import ActionFlowStatusEnum, ActionScheduleTypeEnum
from app.schemas.general import PageParamsSchema, PageResponseSchema
from app.schemas.response import ApiResponseSchema
from app.service.action_schedule import ActionScheduleService, calculate_next_runs, utc_now
from app.utils.id_lib import generate_id

router = APIRouter(prefix="/schedules", tags=["行动调度"])


def schedule_response(schedule: ActionScheduleModel, blueprint: ActionBlueprintModel) -> ActionScheduleResponse:
    """将计划模型转换为包含蓝图摘要的响应。"""
    return ActionScheduleResponse(
        id=schedule.id,
        name=schedule.name,
        description=schedule.description,
        blueprint_id=schedule.blueprint_id,
        blueprint_name=blueprint.name,
        blueprint_version=blueprint.version,
        params=schedule.params,
        schedule_type=schedule.schedule_type,
        cron_expression=schedule.cron_expression,
        interval_seconds=schedule.interval_seconds,
        timezone=schedule.timezone,
        start_at=schedule.start_at,
        end_at=schedule.end_at,
        enabled=schedule.enabled,
        priority=schedule.priority,
        overlap_policy=schedule.overlap_policy,
        misfire_policy=schedule.misfire_policy,
        next_run_at=schedule.next_run_at,
        last_scheduled_for=schedule.last_scheduled_for,
        last_action_id=schedule.last_action_id,
        last_trigger_status=schedule.last_trigger_status,
        last_error=schedule.last_error,
        created_at=schedule.created_at,
        updated_at=schedule.updated_at,
    )


async def run_response(action: ActionInstanceModel) -> ActionScheduleRunResponse | None:
    """将定时 Action 转换为任务执行记录。"""
    blueprint = await ActionBlueprintModel.find_one({"_id": action.blueprint_id})
    if blueprint is None or not action.schedule_id:
        return None
    error_message = None
    if action.status == ActionFlowStatusEnum.FAILED:
        failed_node = await ActionInstanceNodeModel.find_one(
            {"action_id": action.id, "status": ActionFlowStatusEnum.FAILED.value}
        )
        error_message = failed_node.error_message if failed_node else None
    return ActionScheduleRunResponse(
        action_id=action.id,
        schedule_id=action.schedule_id,
        schedule_name=action.schedule_name or action.schedule_id,
        blueprint_id=action.blueprint_id,
        blueprint_name=blueprint.name,
        priority=action.schedule_priority,
        status=action.status,
        progress=action.progress,
        scheduled_for=action.scheduled_for,
        created_at=action.created_at,
        start_at=action.start_at,
        finished_at=action.finished_at,
        duration=action.duration,
        completed_steps=len(action.finished_nodes_instance),
        total_steps=len(action.nodes_id),
        error_message=error_message,
    )


@router.get("", response_model=PageResponseSchema[ActionScheduleResponse], summary="获取行动调度计划")
async def get_schedules(
    params: PageParamsSchema = Depends(),
    keyword: str | None = Query(default=None),
    enabled: bool | None = Query(default=None),
    schedule_type: ActionScheduleTypeEnum | None = Query(default=None),
):
    filters: dict = {"is_deleted": False}
    if enabled is not None:
        filters["enabled"] = enabled
    if schedule_type is not None:
        filters["schedule_type"] = schedule_type
    if keyword:
        pattern = re.compile(re.escape(keyword), re.IGNORECASE)
        blueprints = await ActionBlueprintModel.find({"name": {"$regex": pattern}}).to_list()
        filters["$or"] = [
            {"name": {"$regex": pattern}},
            {"description": {"$regex": pattern}},
            {"blueprint_id": {"$in": [item.id for item in blueprints]}},
        ]
    query = ActionScheduleModel.find(filters)
    total = await query.count()
    schedules = await query.sort([("created_at", -1)]).skip(
        (params.page - 1) * params.page_size
    ).limit(params.page_size).to_list()
    items = []
    for schedule in schedules:
        blueprint = await ActionBlueprintModel.find_one({"_id": schedule.blueprint_id})
        if blueprint:
            items.append(schedule_response(schedule, blueprint))
    return PageResponseSchema.create(items, total, params.page, params.page_size)


@router.post("", response_model=ApiResponseSchema[ActionScheduleResponse], summary="创建行动调度计划")
async def create_schedule(data: ActionScheduleCreateRequest):
    try:
        blueprint = await ActionScheduleService.validate_payload(data)
    except ValueError as exc:
        return ApiResponseSchema.error(code=240421, message=str(exc))
    now = utc_now()
    next_runs = ActionScheduleService.next_runs(data, count=1) if data.enabled else []
    schedule = ActionScheduleModel(
        id=generate_id(f"{data.name}:{uuid4().hex}"),
        **data.model_dump(exclude={"enabled"}),
        next_run_at=next_runs[0] if next_runs else None,
        enabled=data.enabled and bool(next_runs),
        created_at=now,
        updated_at=now,
    )
    await schedule.insert()
    return ApiResponseSchema.success(data=schedule_response(schedule, blueprint))


@router.post("/preview", response_model=ApiResponseSchema[ActionSchedulePreviewResponse], summary="预览行动调度时刻")
async def preview_schedule(data: ActionSchedulePreviewRequest):
    try:
        runs = calculate_next_runs(
            data.schedule_type,
            cron_expression=data.cron_expression,
            interval_seconds=data.interval_seconds,
            timezone_name=data.timezone,
            start_at=data.start_at,
            end_at=data.end_at,
            count=5,
        )
    except ValueError as exc:
        return ApiResponseSchema.error(code=240421, message=str(exc))
    return ApiResponseSchema.success(data=ActionSchedulePreviewResponse(next_runs=runs))


@router.get("/runs", response_model=PageResponseSchema[ActionScheduleRunResponse], summary="获取计划执行任务")
async def get_schedule_runs(
    params: PageParamsSchema = Depends(),
    schedule_id: str | None = Query(default=None),
    status: ActionFlowStatusEnum | None = Query(default=None),
    keyword: str | None = Query(default=None),
    start_at: datetime | None = Query(default=None),
    end_at: datetime | None = Query(default=None),
):
    filters: dict = {"schedule_id": {"$type": "string"}}
    if schedule_id:
        filters["schedule_id"] = schedule_id
    if status:
        filters["status"] = status
    if start_at or end_at:
        filters["scheduled_for"] = {}
        if start_at:
            filters["scheduled_for"]["$gte"] = start_at
        if end_at:
            filters["scheduled_for"]["$lte"] = end_at
    if keyword:
        pattern = re.compile(re.escape(keyword), re.IGNORECASE)
        schedules = await ActionScheduleModel.find({"name": {"$regex": pattern}}).to_list()
        blueprints = await ActionBlueprintModel.find({"name": {"$regex": pattern}}).to_list()
        filters["$or"] = [
            {"schedule_id": {"$in": [item.id for item in schedules]}},
            {"blueprint_id": {"$in": [item.id for item in blueprints]}},
        ]
    query = ActionInstanceModel.find(filters)
    total = await query.count()
    actions = await query.sort([("created_at", -1)]).skip(
        (params.page - 1) * params.page_size
    ).limit(params.page_size).to_list()
    items = []
    for action in actions:
        item = await run_response(action)
        if item:
            items.append(item)
    return PageResponseSchema.create(items, total, params.page, params.page_size)


@router.get("/summary", response_model=ApiResponseSchema[ActionScheduleSummaryResponse], summary="获取调度任务统计")
async def get_schedule_summary():
    schedule_count = await ActionScheduleModel.find({"is_deleted": False}).count()
    enabled_count = await ActionScheduleModel.find({"is_deleted": False, "enabled": True}).count()
    base_filter = {"schedule_id": {"$type": "string"}}
    task_count = await ActionInstanceModel.find(base_filter).count()
    running_count = await ActionInstanceModel.find({**base_filter, "status": ActionFlowStatusEnum.RUNNING}).count()
    pending_count = await ActionInstanceModel.find(
        {**base_filter, "status": {"$in": [ActionFlowStatusEnum.READY, ActionFlowStatusEnum.UNREADY]}}
    ).count()
    failed_count = await ActionInstanceModel.find({**base_filter, "status": ActionFlowStatusEnum.FAILED}).count()
    recent_actions = await ActionInstanceModel.find(base_filter).sort([("created_at", -1)]).limit(6).to_list()
    recent_runs = []
    for action in recent_actions:
        item = await run_response(action)
        if item:
            recent_runs.append(item)
    return ApiResponseSchema.success(
        data=ActionScheduleSummaryResponse(
            schedule_count=schedule_count,
            enabled_schedule_count=enabled_count,
            task_count=task_count,
            running_count=running_count,
            pending_count=pending_count,
            failed_count=failed_count,
            recent_runs=recent_runs,
        )
    )


@router.get("/status", response_model=ApiResponseSchema[ActionSchedulerStatusResponse], summary="获取调度器状态")
async def get_scheduler_status():
    online, heartbeat, last_scan = await ActionScheduleService.scheduler_status()
    return ApiResponseSchema.success(
        data=ActionSchedulerStatusResponse(
            online=online,
            last_heartbeat_at=heartbeat,
            last_scan_at=last_scan,
        )
    )


@router.get("/{schedule_id}", response_model=ApiResponseSchema[ActionScheduleResponse], summary="获取行动调度计划详情")
async def get_schedule(schedule_id: str):
    schedule = await ActionScheduleModel.find_one({"_id": schedule_id, "is_deleted": False})
    if schedule is None:
        return ApiResponseSchema.error(code=240422, message="行动调度计划不存在")
    blueprint = await ActionBlueprintModel.find_one({"_id": schedule.blueprint_id})
    if blueprint is None:
        return ApiResponseSchema.error(code=240411, message="行动蓝图不存在")
    return ApiResponseSchema.success(data=schedule_response(schedule, blueprint))


@router.patch("/{schedule_id}", response_model=ApiResponseSchema[ActionScheduleResponse], summary="更新行动调度计划")
async def update_schedule(schedule_id: str, data: ActionScheduleUpdateRequest):
    schedule = await ActionScheduleModel.find_one({"_id": schedule_id, "is_deleted": False})
    if schedule is None:
        return ApiResponseSchema.error(code=240422, message="行动调度计划不存在")
    current = {
        name: getattr(schedule, name)
        for name in ActionSchedulePayload.model_fields
    }
    updates = data.model_dump(exclude_unset=True)
    current.update(updates)
    if current["schedule_type"] == ActionScheduleTypeEnum.CRON:
        current["interval_seconds"] = None
    else:
        current["cron_expression"] = None
    try:
        payload = ActionSchedulePayload(**current)
        blueprint = await ActionScheduleService.validate_payload(payload)
    except ValueError as exc:
        return ApiResponseSchema.error(code=240421, message=str(exc))
    next_runs = ActionScheduleService.next_runs(payload, count=1) if payload.enabled else []
    for field, value in payload.model_dump().items():
        setattr(schedule, field, value)
    schedule.next_run_at = next_runs[0] if next_runs else None
    schedule.enabled = payload.enabled and bool(next_runs)
    schedule.last_error = None
    schedule.updated_at = utc_now()
    await schedule.save()
    return ApiResponseSchema.success(data=schedule_response(schedule, blueprint))


@router.delete("/{schedule_id}", response_model=ApiResponseSchema[None], summary="删除行动调度计划")
async def delete_schedule(schedule_id: str):
    schedule = await ActionScheduleModel.find_one({"_id": schedule_id, "is_deleted": False})
    if schedule is None:
        return ApiResponseSchema.error(code=240422, message="行动调度计划不存在")
    schedule.is_deleted = True
    schedule.enabled = False
    schedule.next_run_at = None
    schedule.updated_at = utc_now()
    await schedule.save()
    return ApiResponseSchema.success()
