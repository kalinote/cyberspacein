from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from pymongo import ReturnDocument
from pymongo.errors import DuplicateKeyError

import app.utils.status_codes as status_codes
from app.core.exceptions import ApiException, BadRequestException, NotFoundException
from app.models.alert.evaluation_state import AlertSignalStateModel
from app.models.alert.event import AlertEventModel
from app.models.alert.instance import AlertInstanceModel
from app.models.alert.rule import AlertRuleModel
from app.schemas.alert.constants import (
    ALERT_SEVERITY_ORDER,
    AlertEventTypeEnum,
    AlertResolutionTypeEnum,
    AlertSeverityEnum,
    AlertStatusEnum,
)
from app.schemas.alert.observation import AlertObservation
from app.service.alert.stream import AlertStreamService


def utc_now() -> datetime:
    """返回带 UTC 时区的当前时间。"""
    return datetime.now(timezone.utc)


def alert_payload(alert: AlertInstanceModel) -> dict[str, Any]:
    """生成可供 REST 与 SSE 复用的告警公开数据。"""
    return alert.model_dump(
        mode="json",
        by_alias=False,
        exclude={
            "open_key",
            "incident_key",
            "anomaly_sequence",
            "pending_event",
        },
    )


_SSE_EVENT_TYPES = {
    AlertEventTypeEnum.TRIGGERED: "alert.created",
    AlertEventTypeEnum.ACKNOWLEDGED: "alert.acknowledged",
    AlertEventTypeEnum.SEVERITY_CHANGED: "alert.severity_changed",
    AlertEventTypeEnum.AUTO_RESOLVED: "alert.resolved",
    AlertEventTypeEnum.MANUAL_RESOLVED: "alert.resolved",
    AlertEventTypeEnum.RULE_ATTACHED: "alert.updated",
    AlertEventTypeEnum.RULE_DETACHED: "alert.updated",
}


class AlertLifecycleService:
    """以幂等方式维护告警实例和永久事件。"""

    @staticmethod
    async def get(alert_id: str) -> AlertInstanceModel:
        """读取告警实例。"""
        alert = await AlertInstanceModel.find_one({"_id": alert_id})
        if alert is None:
            raise NotFoundException("告警不存在")
        return alert

    @staticmethod
    def _pending_event(
        event_type: AlertEventTypeEnum,
        *,
        from_status: AlertStatusEnum | None = None,
        to_status: AlertStatusEnum | None = None,
        from_severity: AlertSeverityEnum | None = None,
        to_severity: AlertSeverityEnum | None = None,
        rule: AlertRuleModel | None = None,
        rule_id: str | None = None,
        rule_version: int | None = None,
        observation: AlertObservation | None = None,
        note: str | None = None,
    ) -> dict[str, Any]:
        """构造与告警状态原子保存的待发布领域事件。"""
        return {
            "event_type": event_type.value,
            "from_status": from_status.value if from_status else None,
            "to_status": to_status.value if to_status else None,
            "from_severity": (
                from_severity.value if from_severity else None
            ),
            "to_severity": to_severity.value if to_severity else None,
            "rule_id": rule.id if rule else rule_id,
            "rule_version": rule.version if rule else rule_version,
            "observation": (
                observation.model_dump(mode="python")
                if observation
                else None
            ),
            "note": note,
        }

    @staticmethod
    async def _record_event(
        alert: AlertInstanceModel,
        event_type: AlertEventTypeEnum,
        *,
        from_status: AlertStatusEnum | None = None,
        to_status: AlertStatusEnum | None = None,
        from_severity: AlertSeverityEnum | None = None,
        to_severity: AlertSeverityEnum | None = None,
        rule: AlertRuleModel | None = None,
        rule_id: str | None = None,
        rule_version: int | None = None,
        observation: AlertObservation | None = None,
        note: str | None = None,
    ) -> AlertEventModel:
        """永久记录一次告警变化并写入 SSE Outbox。"""
        event_id = (
            f"alert:{alert.id}:v{alert.version}:{event_type.value}"
        )
        event = AlertEventModel(
            id=event_id,
            alert_id=alert.id,
            incident_key=alert.incident_key,
            event_type=event_type,
            from_status=from_status,
            to_status=to_status,
            from_severity=from_severity,
            to_severity=to_severity,
            rule_id=rule.id if rule else rule_id,
            rule_version=rule.version if rule else rule_version,
            observation_id=observation.observation_id if observation else None,
            value=observation.value if observation else alert.latest_value,
            value_type=(
                observation.value_type
                if observation
                else alert.trigger_value_type
            ),
            note=note,
            alert_version=alert.version,
        )
        try:
            await event.insert()
        except DuplicateKeyError:
            existing = await AlertEventModel.find_one({"_id": event_id})
            if existing is not None:
                event = existing
            else:
                raise
        await AlertStreamService.enqueue(
            event_id=f"sse:{event.id}",
            event_type=_SSE_EVENT_TYPES[event_type],
            aggregate_type="alert_instance",
            aggregate_id=alert.id,
            aggregate_version=alert.version,
            payload={
                "event_id": event.id,
                "event_type": _SSE_EVENT_TYPES[event_type],
                "occurred_at": event.created_at.isoformat(),
                "alert_id": alert.id,
                "alert_version": alert.version,
                "data": alert_payload(alert),
            },
        )
        await AlertStreamService.enqueue(
            event_id=f"sse:stats:{event.id}",
            event_type="stats.changed",
            aggregate_type="alert_stats",
            aggregate_id=None,
            aggregate_version=None,
            payload={
                "event_id": event.id,
                "occurred_at": event.created_at.isoformat(),
            },
        )
        return event

    @classmethod
    async def _flush_pending_event(
        cls,
        alert: AlertInstanceModel,
    ) -> AlertInstanceModel:
        """幂等补齐永久事件和 SSE Outbox 后清除待办标记。"""
        for _ in range(5):
            pending = alert.pending_event
            if not pending:
                return alert
            observation_data = pending.get("observation")
            observation = (
                AlertObservation.model_validate(observation_data)
                if observation_data
                else None
            )
            await cls._record_event(
                alert,
                AlertEventTypeEnum(pending["event_type"]),
                from_status=(
                    AlertStatusEnum(pending["from_status"])
                    if pending.get("from_status")
                    else None
                ),
                to_status=(
                    AlertStatusEnum(pending["to_status"])
                    if pending.get("to_status")
                    else None
                ),
                from_severity=(
                    AlertSeverityEnum(pending["from_severity"])
                    if pending.get("from_severity")
                    else None
                ),
                to_severity=(
                    AlertSeverityEnum(pending["to_severity"])
                    if pending.get("to_severity")
                    else None
                ),
                rule_id=pending.get("rule_id"),
                rule_version=pending.get("rule_version"),
                observation=observation,
                note=pending.get("note"),
            )
            result = await AlertInstanceModel.get_motor_collection().update_one(
                {
                    "_id": alert.id,
                    "version": alert.version,
                    "pending_event.event_type": pending["event_type"],
                },
                {"$set": {"pending_event": None}},
            )
            if result.modified_count == 1:
                alert.pending_event = None
                return alert
            alert = await cls.get(alert.id)
        raise ApiException(
            status_codes.CONFLICT_STATE,
            "告警事件仍在补偿，请稍后重试",
        )

    @classmethod
    async def create_or_get(
        cls,
        *,
        incident_key: str,
        anomaly_sequence: int,
        active_rules: list[AlertRuleModel],
        severity: AlertSeverityEnum,
        observation: AlertObservation,
    ) -> AlertInstanceModel:
        """为新异常周期创建告警，唯一索引冲突时返回已有实例。"""
        severity_rule = max(
            active_rules,
            key=lambda item: ALERT_SEVERITY_ORDER[item.severity],
        )
        existing = await AlertInstanceModel.find_one({"open_key": incident_key})
        if existing is not None:
            if existing.pending_event:
                await cls._flush_pending_event(existing)
            elif existing.version == 1:
                await cls._record_event(
                    existing,
                    AlertEventTypeEnum.TRIGGERED,
                    to_status=AlertStatusEnum.FIRING,
                    to_severity=severity,
                    rule=severity_rule,
                    observation=observation,
                )
            return existing
        now = utc_now()
        field_label = severity_rule.field_key
        alert = AlertInstanceModel(
            id=uuid4().hex,
            open_key=incident_key,
            incident_key=incident_key,
            anomaly_sequence=anomaly_sequence,
            source_key=observation.source_key,
            resource_type=observation.resource_type,
            resource_id=observation.resource_id,
            resource_name=observation.resource_name,
            resource_url=observation.resource_url,
            field_key=observation.field_key,
            signal_key=observation.signal_key,
            title=severity_rule.name,
            detail=(
                f"{observation.resource_name} 的 {field_label} 当前值为 "
                f"{observation.value}"
            ),
            status=AlertStatusEnum.FIRING,
            initial_severity=severity,
            current_severity=severity,
            active_rule_ids=sorted(rule.id for rule in active_rules),
            trigger_value=observation.value,
            trigger_value_type=observation.value_type,
            latest_value=observation.value,
            latest_observed_at=observation.observed_at,
            pending_event=cls._pending_event(
                AlertEventTypeEnum.TRIGGERED,
                to_status=AlertStatusEnum.FIRING,
                to_severity=severity,
                rule=severity_rule,
                observation=observation,
            ),
            triggered_at=observation.observed_at,
            created_at=now,
            updated_at=now,
        )
        try:
            await alert.insert()
        except DuplicateKeyError:
            existing = await AlertInstanceModel.find_one({"open_key": incident_key})
            if existing is None:
                raise
            if existing.pending_event:
                await cls._flush_pending_event(existing)
            return existing
        await cls._flush_pending_event(alert)
        return alert

    @classmethod
    async def sync_active(
        cls,
        alert: AlertInstanceModel,
        *,
        active_rules: list[AlertRuleModel],
        severity: AlertSeverityEnum,
        observation: AlertObservation,
    ) -> AlertInstanceModel:
        """同步活动规则、最新值及实时等级变化。"""
        if alert.pending_event:
            alert = await cls._flush_pending_event(alert)
        if alert.status == AlertStatusEnum.RESOLVED:
            return alert
        old_rule_ids = set(alert.active_rule_ids)
        new_rule_ids = {rule.id for rule in active_rules}
        old_severity = alert.current_severity
        now = utc_now()
        visible_change = old_rule_ids != new_rule_ids or old_severity != severity
        severity_rule = max(
            active_rules,
            key=lambda item: ALERT_SEVERITY_ORDER[item.severity],
        )
        pending_event = None
        if visible_change:
            if old_severity != severity:
                pending_event = cls._pending_event(
                    AlertEventTypeEnum.SEVERITY_CHANGED,
                    from_severity=old_severity,
                    to_severity=severity,
                    rule=severity_rule,
                    observation=observation,
                )
            else:
                attached = new_rule_ids - old_rule_ids
                event_type = (
                    AlertEventTypeEnum.RULE_ATTACHED
                    if attached
                    else AlertEventTypeEnum.RULE_DETACHED
                )
                changed_rule_id = next(
                    iter(attached or (old_rule_ids - new_rule_ids)),
                    None,
                )
                changed_rule = next(
                    (
                        rule
                        for rule in active_rules
                        if rule.id == changed_rule_id
                    ),
                    None,
                )
                pending_event = cls._pending_event(
                    event_type,
                    rule=changed_rule,
                    rule_id=changed_rule_id,
                    observation=observation,
                )
        update = {
            "$set": {
                "active_rule_ids": sorted(new_rule_ids),
                "current_severity": severity.value,
                "latest_value": observation.value,
                "latest_observed_at": observation.observed_at,
                "resource_name": observation.resource_name,
                "resource_url": observation.resource_url,
                "updated_at": now,
            }
        }
        if visible_change:
            update["$set"]["pending_event"] = pending_event
            update["$inc"] = {"version": 1}
        raw = await AlertInstanceModel.get_motor_collection().find_one_and_update(
            {
                "_id": alert.id,
                "version": alert.version,
                "status": {
                    "$in": [
                        AlertStatusEnum.FIRING.value,
                        AlertStatusEnum.ACKNOWLEDGED.value,
                    ]
                },
            },
            update,
            return_document=ReturnDocument.AFTER,
        )
        if raw is None:
            current = await cls.get(alert.id)
            if current.pending_event:
                current = await cls._flush_pending_event(current)
            return current
        updated = AlertInstanceModel.model_validate(raw)
        if updated.pending_event:
            updated = await cls._flush_pending_event(updated)
        return updated

    @classmethod
    async def acknowledge(
        cls,
        alert_id: str,
        expected_version: int,
    ) -> AlertInstanceModel:
        """确认活动告警，不改变检测和自动恢复。"""
        current = await cls.get(alert_id)
        if current.pending_event:
            current = await cls._flush_pending_event(current)
        if current.status == AlertStatusEnum.ACKNOWLEDGED:
            return current
        if current.status == AlertStatusEnum.RESOLVED:
            raise ApiException(status_codes.CONFLICT_STATE, "已解决告警不能确认")
        now = utc_now()
        raw = await AlertInstanceModel.get_motor_collection().find_one_and_update(
            {
                "_id": alert_id,
                "version": expected_version,
                "status": AlertStatusEnum.FIRING.value,
            },
            {
                "$set": {
                    "status": AlertStatusEnum.ACKNOWLEDGED.value,
                    "acknowledged_at": now,
                    "updated_at": now,
                    "pending_event": cls._pending_event(
                        AlertEventTypeEnum.ACKNOWLEDGED,
                        from_status=AlertStatusEnum.FIRING,
                        to_status=AlertStatusEnum.ACKNOWLEDGED,
                    ),
                },
                "$inc": {"version": 1},
            },
            return_document=ReturnDocument.AFTER,
        )
        if raw is None:
            raise ApiException(status_codes.CONFLICT_STATE, "告警版本已变化，请刷新后重试")
        updated = AlertInstanceModel.model_validate(raw)
        updated = await cls._flush_pending_event(updated)
        return updated

    @classmethod
    async def resolve_manual(
        cls,
        alert_id: str,
        *,
        expected_version: int,
        note: str | None,
    ) -> AlertInstanceModel:
        """手动解决告警并抑制当前持续异常周期。"""
        current = await cls.get(alert_id)
        if current.pending_event:
            current = await cls._flush_pending_event(current)
        if current.status == AlertStatusEnum.RESOLVED:
            if current.resolution_type == AlertResolutionTypeEnum.MANUAL:
                now = utc_now()
                await AlertSignalStateModel.find_one(
                    {"incident_key": current.incident_key}
                ).update(
                    {
                        "$set": {
                            "manual_suppressed": True,
                            "armed": False,
                            "current_alert_id": None,
                            "updated_at": now,
                        }
                    }
                )
            return current
        normalized_note = (note or "").strip()
        if (
            ALERT_SEVERITY_ORDER[current.current_severity]
            >= ALERT_SEVERITY_ORDER[AlertSeverityEnum.ERROR]
            and not normalized_note
        ):
            raise BadRequestException("严重和致命告警必须填写处理说明")
        now = utc_now()
        raw = await AlertInstanceModel.get_motor_collection().find_one_and_update(
            {
                "_id": alert_id,
                "version": expected_version,
                "status": {
                    "$in": [
                        AlertStatusEnum.FIRING.value,
                        AlertStatusEnum.ACKNOWLEDGED.value,
                    ]
                },
            },
            {
                "$set": {
                    "status": AlertStatusEnum.RESOLVED.value,
                    "resolution_type": AlertResolutionTypeEnum.MANUAL.value,
                    "resolution_note": normalized_note or None,
                    "resolved_at": now,
                    "open_key": None,
                    "updated_at": now,
                    "pending_event": cls._pending_event(
                        AlertEventTypeEnum.MANUAL_RESOLVED,
                        from_status=current.status,
                        to_status=AlertStatusEnum.RESOLVED,
                        note=normalized_note or None,
                    ),
                },
                "$inc": {"version": 1},
            },
            return_document=ReturnDocument.AFTER,
        )
        if raw is None:
            raise ApiException(status_codes.CONFLICT_STATE, "告警版本已变化，请刷新后重试")
        updated = AlertInstanceModel.model_validate(raw)
        await AlertSignalStateModel.find_one(
            {"incident_key": updated.incident_key}
        ).update(
            {
                "$set": {
                    "manual_suppressed": True,
                    "armed": False,
                    "current_alert_id": None,
                    "updated_at": now,
                }
            }
        )
        updated = await cls._flush_pending_event(updated)
        return updated

    @classmethod
    async def resolve_auto(
        cls,
        alert: AlertInstanceModel,
        observation: AlertObservation,
    ) -> AlertInstanceModel:
        """在所有规则恢复后自动解决活动告警。"""
        if alert.pending_event:
            alert = await cls._flush_pending_event(alert)
        if alert.status == AlertStatusEnum.RESOLVED:
            return alert
        now = utc_now()
        raw = await AlertInstanceModel.get_motor_collection().find_one_and_update(
            {
                "_id": alert.id,
                "version": alert.version,
                "status": {
                    "$in": [
                        AlertStatusEnum.FIRING.value,
                        AlertStatusEnum.ACKNOWLEDGED.value,
                    ]
                },
            },
            {
                "$set": {
                    "status": AlertStatusEnum.RESOLVED.value,
                    "resolution_type": AlertResolutionTypeEnum.AUTO.value,
                    "resolved_at": now,
                    "open_key": None,
                    "active_rule_ids": [],
                    "latest_value": observation.value,
                    "latest_observed_at": observation.observed_at,
                    "updated_at": now,
                    "pending_event": cls._pending_event(
                        AlertEventTypeEnum.AUTO_RESOLVED,
                        from_status=alert.status,
                        to_status=AlertStatusEnum.RESOLVED,
                        observation=observation,
                    ),
                },
                "$inc": {"version": 1},
            },
            return_document=ReturnDocument.AFTER,
        )
        if raw is None:
            current = await cls.get(alert.id)
            if current.pending_event:
                current = await cls._flush_pending_event(current)
            return current
        updated = AlertInstanceModel.model_validate(raw)
        updated = await cls._flush_pending_event(updated)
        return updated
