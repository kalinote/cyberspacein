from __future__ import annotations

import asyncio
import json
import re
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Header, Query, Request
from fastapi.responses import StreamingResponse

from app.core.config import settings
from app.models.alert.event import AlertEventModel
from app.models.alert.instance import AlertInstanceModel
from app.models.alert.rule import AlertRuleModel
from app.schemas.alert.constants import (
    AlertInitialEvaluationPolicyEnum,
    AlertResolutionTypeEnum,
    AlertSeverityEnum,
    AlertStatusEnum,
)
from app.schemas.alert.instance import (
    AlertAcknowledgeRequest,
    AlertEventResponse,
    AlertInstanceResponse,
    AlertResolveRequest,
    AlertStatsResponse,
)
from app.schemas.alert.rule import (
    AlertRuleCreateRequest,
    AlertRuleEnabledRequest,
    AlertRuleResponse,
    AlertRuleTestResponse,
    AlertRuleUpdateRequest,
    AlertRuleValidationResponse,
)
from app.schemas.alert.source import AlertSourceDescriptor
from app.schemas.general import PageParamsSchema, PageResponseSchema
from app.schemas.response import ApiResponseSchema
from app.service.alert.comparator import evaluate_expression
from app.service.alert.lifecycle import AlertLifecycleService
from app.service.alert.registry import alert_source_registry
from app.service.alert.rule_service import AlertRuleService
from app.service.alert.stream import AlertStreamService
from app.service.alert.worker import AlertWorkerService

router = APIRouter(tags=["告警中心"])


def instance_response(alert: AlertInstanceModel) -> AlertInstanceResponse:
    """将告警模型转换为公开响应。"""
    return AlertInstanceResponse(**alert.model_dump(by_alias=False))


def rule_response(rule: AlertRuleModel) -> AlertRuleResponse:
    """将规则模型转换为公开响应。"""
    return AlertRuleResponse(**rule.model_dump(by_alias=False))


@router.get(
    "/sources",
    response_model=ApiResponseSchema[list[AlertSourceDescriptor]],
    summary="获取告警接入源",
)
async def get_sources():
    return ApiResponseSchema.success(data=alert_source_registry.list_descriptors())


@router.get(
    "/sources/status",
    response_model=ApiResponseSchema[dict],
    summary="获取告警接入状态",
)
async def get_sources_status():
    return ApiResponseSchema.success(
        data={
            "sources": [
                {
                    "source_key": descriptor.source_key,
                    "module_key": descriptor.module_key,
                    "schema_version": descriptor.schema_version,
                    "registered": True,
                }
                for descriptor in alert_source_registry.list_descriptors()
            ],
            "worker": await AlertWorkerService.status(),
        }
    )


@router.post(
    "/rules/validate",
    response_model=ApiResponseSchema[AlertRuleValidationResponse],
    summary="校验告警规则",
)
async def validate_rule(data: AlertRuleCreateRequest):
    descriptor, field = AlertRuleService().validate_payload(data)
    return ApiResponseSchema.success(
        data=AlertRuleValidationResponse(
            source_schema_version=descriptor.schema_version,
            signal_key=field.signal_key,
        )
    )


@router.get(
    "/rules",
    response_model=PageResponseSchema[AlertRuleResponse],
    summary="分页查询告警规则",
)
async def get_rules(
    params: PageParamsSchema = Depends(),
    source_key: str | None = Query(default=None),
    enabled: bool | None = Query(default=None),
    keyword: str | None = Query(default=None),
):
    filters: dict = {"is_deleted": False}
    if source_key:
        filters["source_key"] = source_key
    if enabled is not None:
        filters["enabled"] = enabled
    if keyword:
        pattern = re.compile(re.escape(keyword), re.IGNORECASE)
        filters["$or"] = [
            {"name": {"$regex": pattern}},
            {"description": {"$regex": pattern}},
        ]
    query = AlertRuleModel.find(filters)
    total = await query.count()
    rules = await query.sort("-updated_at").skip(
        (params.page - 1) * params.page_size
    ).limit(params.page_size).to_list()
    return PageResponseSchema.create(
        [rule_response(rule) for rule in rules],
        total,
        params.page,
        params.page_size,
    )


@router.post(
    "/rules",
    response_model=ApiResponseSchema[AlertRuleResponse],
    summary="创建告警规则",
)
async def create_rule(data: AlertRuleCreateRequest):
    rule = await AlertRuleService().create(data)
    return ApiResponseSchema.success(data=rule_response(rule))


@router.get(
    "/rules/{rule_id}",
    response_model=ApiResponseSchema[AlertRuleResponse],
    summary="获取告警规则详情",
)
async def get_rule(rule_id: str):
    return ApiResponseSchema.success(
        data=rule_response(await AlertRuleService.get(rule_id))
    )


@router.patch(
    "/rules/{rule_id}",
    response_model=ApiResponseSchema[AlertRuleResponse],
    summary="修改告警规则",
)
async def update_rule(rule_id: str, data: AlertRuleUpdateRequest):
    rule = await AlertRuleService().update(rule_id, data)
    return ApiResponseSchema.success(data=rule_response(rule))


@router.patch(
    "/rules/{rule_id}/enabled",
    response_model=ApiResponseSchema[AlertRuleResponse],
    summary="启用或停用告警规则",
)
async def set_rule_enabled(rule_id: str, data: AlertRuleEnabledRequest):
    rule = await AlertRuleService().set_enabled(rule_id, data)
    return ApiResponseSchema.success(data=rule_response(rule))


@router.delete(
    "/rules/{rule_id}",
    response_model=ApiResponseSchema[None],
    summary="删除告警规则",
)
async def delete_rule(
    rule_id: str,
    expected_version: int = Query(ge=1),
):
    await AlertRuleService().delete(rule_id, expected_version)
    return ApiResponseSchema.success()


@router.post(
    "/rules/{rule_id}/test",
    response_model=ApiResponseSchema[AlertRuleTestResponse],
    summary="试运行告警规则",
)
async def test_rule(
    rule_id: str,
    max_resources: int = Query(default=100, ge=1, le=500),
):
    rule = await AlertRuleService.get(rule_id)
    provider = alert_source_registry.get(rule.source_key)
    active_from = (
        datetime(1970, 1, 1, tzinfo=timezone.utc)
        if rule.initial_evaluation_policy
        == AlertInitialEvaluationPolicyEnum.INCLUDE_EXISTING
        else rule.active_from
    )
    page = await provider.iter_observations(
        field_key=rule.field_key,
        active_from=active_from,
        cursor=None,
        limit=max_resources,
    )
    samples = []
    matched = 0
    for observation in page.items:
        if not evaluate_expression(
            rule.trigger_expression,
            observation.value_type,
            observation.value,
        ):
            continue
        matched += 1
        if len(samples) < 20:
            samples.append(
                {
                    "resource_id": observation.resource_id,
                    "resource_name": observation.resource_name,
                    "value": observation.value,
                    "observed_at": observation.observed_at,
                }
            )
    return ApiResponseSchema.success(
        data=AlertRuleTestResponse(
            scanned=len(page.items),
            matched=matched,
            truncated=page.next_cursor is not None,
            samples=samples,
        )
    )


@router.get(
    "/instances",
    response_model=PageResponseSchema[AlertInstanceResponse],
    summary="分页查询告警实例",
)
async def get_instances(
    params: PageParamsSchema = Depends(),
    status: list[AlertStatusEnum] | None = Query(default=None),
    severity: list[AlertSeverityEnum] | None = Query(default=None),
    source_key: str | None = Query(default=None),
    rule_id: str | None = Query(default=None),
    triggered_from: datetime | None = Query(default=None),
    triggered_to: datetime | None = Query(default=None),
    keyword: str | None = Query(default=None),
    sort_by: str = Query(default="triggered_at"),
    sort_order: str = Query(default="desc", pattern="^(asc|desc)$"),
):
    filters: dict = {}
    if status:
        filters["status"] = {"$in": status}
    if severity:
        filters["current_severity"] = {"$in": severity}
    if source_key:
        filters["source_key"] = source_key
    if rule_id:
        filters["active_rule_ids"] = rule_id
    if triggered_from or triggered_to:
        filters["triggered_at"] = {}
        if triggered_from:
            filters["triggered_at"]["$gte"] = triggered_from
        if triggered_to:
            filters["triggered_at"]["$lte"] = triggered_to
    if keyword:
        pattern = re.compile(re.escape(keyword), re.IGNORECASE)
        filters["$or"] = [
            {"title": {"$regex": pattern}},
            {"resource_name": {"$regex": pattern}},
            {"resource_id": {"$regex": pattern}},
        ]
    allowed_sort_fields = {
        "triggered_at",
        "updated_at",
        "resolved_at",
        "current_severity",
        "status",
    }
    sort_field = sort_by if sort_by in allowed_sort_fields else "triggered_at"
    query = AlertInstanceModel.find(filters)
    total = await query.count()
    alerts = await query.sort(
        [(sort_field, 1 if sort_order == "asc" else -1)]
    ).skip((params.page - 1) * params.page_size).limit(
        params.page_size
    ).to_list()
    return PageResponseSchema.create(
        [instance_response(alert) for alert in alerts],
        total,
        params.page,
        params.page_size,
    )


@router.get(
    "/instances/{alert_id}",
    response_model=ApiResponseSchema[AlertInstanceResponse],
    summary="获取告警详情",
)
async def get_instance(alert_id: str):
    alert = await AlertLifecycleService.get(alert_id)
    return ApiResponseSchema.success(data=instance_response(alert))


@router.get(
    "/instances/{alert_id}/events",
    response_model=PageResponseSchema[AlertEventResponse],
    summary="获取告警永久事件",
)
async def get_instance_events(
    alert_id: str,
    params: PageParamsSchema = Depends(),
):
    await AlertLifecycleService.get(alert_id)
    query = AlertEventModel.find({"alert_id": alert_id})
    total = await query.count()
    events = await query.sort("+created_at").skip(
        (params.page - 1) * params.page_size
    ).limit(params.page_size).to_list()
    return PageResponseSchema.create(
        [
            AlertEventResponse(**event.model_dump(by_alias=False))
            for event in events
        ],
        total,
        params.page,
        params.page_size,
    )


@router.post(
    "/instances/{alert_id}/acknowledge",
    response_model=ApiResponseSchema[AlertInstanceResponse],
    summary="确认告警",
)
async def acknowledge_instance(
    alert_id: str,
    data: AlertAcknowledgeRequest,
):
    alert = await AlertLifecycleService.acknowledge(
        alert_id,
        data.expected_version,
    )
    return ApiResponseSchema.success(data=instance_response(alert))


@router.post(
    "/instances/{alert_id}/resolve",
    response_model=ApiResponseSchema[AlertInstanceResponse],
    summary="手动解决告警",
)
async def resolve_instance(
    alert_id: str,
    data: AlertResolveRequest,
):
    alert = await AlertLifecycleService.resolve_manual(
        alert_id,
        expected_version=data.expected_version,
        note=data.note,
    )
    return ApiResponseSchema.success(data=instance_response(alert))


@router.get(
    "/stats",
    response_model=ApiResponseSchema[AlertStatsResponse],
    summary="获取告警统计",
)
async def get_stats():
    local_now = datetime.now().astimezone()
    local_midnight = local_now.replace(
        hour=0,
        minute=0,
        second=0,
        microsecond=0,
    ).astimezone(timezone.utc)
    active = [AlertStatusEnum.FIRING, AlertStatusEnum.ACKNOWLEDGED]
    by_severity = {
        severity: await AlertInstanceModel.find(
            {
                "status": {"$in": active},
                "current_severity": severity,
            }
        ).count()
        for severity in AlertSeverityEnum
    }
    try:
        stream_cursor = await AlertStreamService.latest_cursor()
    except Exception:
        stream_cursor = "0-0"
    return ApiResponseSchema.success(
        data=AlertStatsResponse(
            firing=await AlertInstanceModel.find(
                {"status": AlertStatusEnum.FIRING}
            ).count(),
            acknowledged=await AlertInstanceModel.find(
                {"status": AlertStatusEnum.ACKNOWLEDGED}
            ).count(),
            resolved_today_auto=await AlertInstanceModel.find(
                {
                    "status": AlertStatusEnum.RESOLVED,
                    "resolution_type": AlertResolutionTypeEnum.AUTO,
                    "resolved_at": {"$gte": local_midnight},
                }
            ).count(),
            resolved_today_manual=await AlertInstanceModel.find(
                {
                    "status": AlertStatusEnum.RESOLVED,
                    "resolution_type": AlertResolutionTypeEnum.MANUAL,
                    "resolved_at": {"$gte": local_midnight},
                }
            ).count(),
            by_severity=by_severity,
            stream_cursor=stream_cursor,
        )
    )


@router.get("/stream", summary="订阅告警领域事件流")
async def stream_alerts(
    request: Request,
    after_id: str | None = Query(default=None),
    last_event_id: str | None = Header(default=None, alias="Last-Event-ID"),
):
    cursor = after_id or last_event_id
    if cursor is None:
        try:
            cursor = await AlertStreamService.latest_cursor()
        except Exception:
            cursor = "0-0"

    async def event_stream():
        nonlocal cursor
        try:
            stale, oldest_cursor, latest_cursor = (
                await AlertStreamService.replay_status(cursor)
            )
        except Exception:
            stale = False
            oldest_cursor = "0-0"
            latest_cursor = cursor
        if stale:
            cursor = latest_cursor
            payload = json.dumps(
                {
                    "reason": "cursor_expired",
                    "oldest_cursor": oldest_cursor,
                    "latest_cursor": latest_cursor,
                },
                ensure_ascii=False,
            )
            yield (
                f"id: {latest_cursor}\n"
                f"event: stream.reset\n"
                f"data: {payload}\n\n"
            )
        while True:
            if await request.is_disconnected():
                break
            try:
                messages = await AlertStreamService.read_after(
                    cursor,
                    block_ms=settings.ALERT_SSE_HEARTBEAT_SECONDS * 1000,
                )
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                payload = json.dumps(
                    {"message": "告警事件流暂时不可用", "detail": str(exc)[:300]},
                    ensure_ascii=False,
                )
                yield f"event: stream.error\ndata: {payload}\n\n"
                await asyncio.sleep(1)
                continue
            if not messages:
                yield ": keep-alive\n\n"
                continue
            for stream_id, fields in messages:
                cursor = stream_id
                event_name = fields.get("event") or "message"
                data = fields.get("data") or "{}"
                yield f"id: {stream_id}\nevent: {event_name}\ndata: {data}\n\n"

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.get(
    "/worker/status",
    response_model=ApiResponseSchema[dict],
    summary="获取告警 Worker 状态",
)
async def get_worker_status():
    return ApiResponseSchema.success(data=await AlertWorkerService.status())
