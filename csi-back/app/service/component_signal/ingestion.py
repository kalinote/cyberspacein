from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from typing import Any

from loguru import logger
from pymongo import ReturnDocument
from pymongo.errors import DuplicateKeyError

from app.core.config import settings
from app.db.redis import get_redis
from app.dependencies.auth import ComponentContext
from app.models.alert.observation import AlertObservationInboxModel
from app.models.component_signal import ComponentSignalSnapshotModel
from app.schemas.alert.constants import AlertValueTypeEnum
from app.schemas.alert.observation import AlertObservation
from app.schemas.component_signal import (
    ComponentSignalBatchRequest,
    ComponentSignalBatchResponse,
    ComponentSignalDefinition,
    ComponentSignalReport,
    ComponentSignalReportResult,
)
from app.service.alert.comparator import normalize_value
from app.service.alert.observation_inbox import AlertObservationInboxService
from app.service.component_signal.registry import (
    ComponentSignalDefinitionRegistry,
    component_signal_definition_registry,
)
from app.utils.id_lib import generate_id

logger = logger.bind(name=__name__)

_SENSITIVE_METADATA_PARTS = {
    "apikey",
    "authorization",
    "bearer",
    "cookie",
    "credential",
    "password",
    "passwd",
    "privatekey",
    "proxyauth",
    "secret",
    "session",
    "token",
}


def utc_now() -> datetime:
    """返回带 UTC 时区的当前时间。"""
    return datetime.now(timezone.utc)


def _contains_sensitive_metadata(value: Any) -> bool:
    """递归检查 metadata 是否包含常见凭证键。"""
    if isinstance(value, dict):
        for key, nested in value.items():
            normalized_key = "".join(
                character
                for character in str(key).lower()
                if character.isalnum()
            )
            if any(part in normalized_key for part in _SENSITIVE_METADATA_PARTS):
                return True
            if _contains_sensitive_metadata(nested):
                return True
    elif isinstance(value, list):
        return any(_contains_sensitive_metadata(item) for item in value)
    return False


class ComponentSignalIngestionService:
    """校验组件报告并可靠写入信号快照和告警 Inbox。"""

    def __init__(
        self,
        registry: ComponentSignalDefinitionRegistry | None = None,
    ) -> None:
        self.registry = registry or component_signal_definition_registry

    @staticmethod
    async def enforce_rate_limit(component_run_id: str, report_count: int) -> None:
        """按组件运行实例执行 Redis 分钟级限流。"""
        redis = get_redis()
        if redis is None:
            return
        minute = int(utc_now().timestamp() // 60)
        key = f"component-signal:rate:{component_run_id}:{minute}"
        try:
            current = await redis.incrby(key, report_count)
            if current == report_count:
                await redis.expire(key, 120)
        except Exception as exc:
            logger.warning(
                f"组件信号限流状态读取失败，按无 Redis 模式继续: {exc}"
            )
            return
        if current > settings.COMPONENT_SIGNAL_MAX_REPORTS_PER_MINUTE:
            raise ValueError("组件信号上报频率超过限制")

    @staticmethod
    def _validate_metadata(
        definition: ComponentSignalDefinition,
        metadata: dict[str, Any],
    ) -> dict[str, Any]:
        """校验 metadata 允许键、敏感内容和序列化大小。"""
        unsupported = sorted(set(metadata) - definition.allowed_metadata_keys)
        if unsupported:
            raise ValueError(
                f"组件信号 metadata 包含未允许字段: {', '.join(unsupported)}"
            )
        if _contains_sensitive_metadata(metadata):
            raise ValueError("组件信号 metadata 不能包含凭证或敏感认证信息")
        try:
            serialized = json.dumps(
                metadata,
                ensure_ascii=False,
                separators=(",", ":"),
                allow_nan=False,
            ).encode("utf-8")
        except (TypeError, ValueError) as exc:
            raise ValueError("组件信号 metadata 必须可以序列化为 JSON") from exc
        limit = min(
            definition.max_metadata_bytes,
            settings.COMPONENT_SIGNAL_METADATA_MAX_BYTES,
        )
        if len(serialized) > limit:
            raise ValueError(f"组件信号 metadata 超过 {limit} 字节限制")
        return metadata

    @staticmethod
    def _normalize_value(
        definition: ComponentSignalDefinition,
        value: Any,
    ) -> Any:
        """按服务端定义规范化组件信号值。"""
        normalized = normalize_value(
            definition.value_type,
            value,
            unit=definition.unit,
        )
        if definition.value_type == AlertValueTypeEnum.ENUM:
            allowed = {item.value for item in definition.enum_options}
            if normalized not in allowed:
                raise ValueError(
                    f"组件信号枚举值未注册: {definition.definition_key}.{normalized}"
                )
        return normalized

    @staticmethod
    def _observation_from_snapshot(
        snapshot: ComponentSignalSnapshotModel,
    ) -> AlertObservation:
        """把最新组件信号快照转换为实时告警观测。"""
        return AlertObservation(
            observation_id=snapshot.last_observation_id,
            source_key=snapshot.source_key,
            resource_type=snapshot.resource_type,
            resource_id=snapshot.resource_id,
            resource_name=snapshot.resource_name,
            resource_url=snapshot.resource_url,
            field_key=snapshot.field_key,
            signal_key=snapshot.signal_key,
            value_type=snapshot.value_type,
            value=snapshot.current_value,
            observed_at=snapshot.observed_at,
            source_event_id=(
                snapshot.last_source_event_id
                or f"component-report:{snapshot.last_report_id}"
            ),
            ordering_key=snapshot.last_report_id,
            metadata=snapshot.metadata,
        )

    @staticmethod
    def _same_report_payload(
        snapshot: ComponentSignalSnapshotModel,
        *,
        report: ComponentSignalReport,
        resource_id: str,
        normalized_value: Any,
        resource_name: str,
        resource_url: str | None,
        metadata: dict[str, Any],
    ) -> bool:
        """确认重复报告 ID 没有被用于另一份业务载荷。"""
        return (
            snapshot.definition_key == report.definition_key
            and snapshot.definition_version == report.definition_version
            and snapshot.resource_id == resource_id
            and snapshot.resource_name == resource_name
            and snapshot.resource_url == resource_url
            and snapshot.current_value == normalized_value
            and snapshot.last_source_event_id == report.source_event_id
            and snapshot.observed_at == report.observed_at
            and snapshot.metadata == metadata
        )

    async def ingest_batch(
        self,
        context: ComponentContext,
        batch: ComponentSignalBatchRequest,
    ) -> ComponentSignalBatchResponse:
        """按请求顺序接收一批组件信号报告。"""
        if len(batch.reports) > settings.COMPONENT_SIGNAL_MAX_BATCH_SIZE:
            raise ValueError(
                "组件信号单批最多允许 "
                f"{settings.COMPONENT_SIGNAL_MAX_BATCH_SIZE} 条"
            )
        await self.enforce_rate_limit(
            context.component_run_id,
            len(batch.reports),
        )
        results = [
            await self.ingest_report(context, report)
            for report in batch.reports
        ]
        return ComponentSignalBatchResponse(results=results)

    async def ingest_report(
        self,
        context: ComponentContext,
        report: ComponentSignalReport,
    ) -> ComponentSignalReportResult:
        """接收单条报告并执行授权、时序和持久化处理。"""
        try:
            definition = self.registry.get(report.definition_key)
        except KeyError as exc:
            raise ValueError(str(exc)) from exc
        if definition.definition_version != report.definition_version:
            raise ValueError(
                "组件信号定义版本不兼容: "
                f"{report.definition_version} -> {definition.definition_version}"
            )
        if (
            "*" not in definition.allowed_component_ids
            and context.component_id not in definition.allowed_component_ids
        ):
            raise PermissionError(
                f"组件无权上报信号定义: {report.definition_key}"
            )
        resolved_resource = await self.registry.resolve_resource(
            report.definition_key,
            context,
            report.resource,
        )
        normalized_value = self._normalize_value(definition, report.value)
        metadata = self._validate_metadata(definition, report.metadata)
        now = utc_now()
        if report.observed_at > now + timedelta(
            seconds=settings.COMPONENT_SIGNAL_FUTURE_SKEW_SECONDS
        ):
            raise ValueError("组件信号观测时间明显晚于服务器时间")
        exceeds_max_age = report.observed_at < now - timedelta(
            seconds=settings.COMPONENT_SIGNAL_MAX_AGE_SECONDS
        )

        resource_name = (
            resolved_resource.resource_name
            or f"{definition.resource_name} {resolved_resource.resource_id}"
        )[:300]
        resource_id = resolved_resource.resource_id
        resource_url = resolved_resource.resource_url
        snapshot_id = generate_id(
            ":".join(
                [
                    definition.definition_key,
                    definition.resource_type,
                    resource_id,
                ]
            )
        )
        observation_id = generate_id(
            "component-signal:"
            f"{definition.definition_key}:"
            f"{resource_id}:"
            f"{report.report_id}"
        )

        for _ in range(8):
            existing = await ComponentSignalSnapshotModel.find_one(
                {"_id": snapshot_id}
            )
            if existing is None:
                if exceeds_max_age:
                    return ComponentSignalReportResult(
                        report_id=report.report_id,
                        status="stale",
                    )
                snapshot = ComponentSignalSnapshotModel(
                    id=snapshot_id,
                    definition_key=definition.definition_key,
                    definition_version=definition.definition_version,
                    source_schema_version=definition.source_schema_version,
                    source_key=definition.source_key,
                    resource_type=definition.resource_type,
                    resource_id=resource_id,
                    resource_name=resource_name,
                    resource_url=resource_url,
                    field_key=definition.field_key,
                    signal_key=definition.signal_key,
                    value_type=definition.value_type,
                    current_value=normalized_value,
                    last_report_id=report.report_id,
                    last_observation_id=observation_id,
                    last_source_event_id=report.source_event_id,
                    last_component_id=context.component_id,
                    last_component_run_id=context.component_run_id,
                    last_action_id=context.action_id,
                    last_node_instance_id=context.node_instance_id,
                    observed_at=report.observed_at,
                    metadata=metadata,
                )
                try:
                    await snapshot.insert()
                except DuplicateKeyError:
                    continue
                await AlertObservationInboxService.publish(
                    self._observation_from_snapshot(snapshot)
                )
                return ComponentSignalReportResult(
                    report_id=report.report_id,
                    status="accepted",
                    observation_id=observation_id,
                )

            if existing.last_report_id == report.report_id:
                if not self._same_report_payload(
                    existing,
                    report=report,
                    resource_id=resource_id,
                    normalized_value=normalized_value,
                    resource_name=resource_name,
                    resource_url=resource_url,
                    metadata=metadata,
                ):
                    raise ValueError("相同 report_id 不能对应不同组件信号载荷")
                await AlertObservationInboxService.publish(
                    self._observation_from_snapshot(existing)
                )
                return ComponentSignalReportResult(
                    report_id=report.report_id,
                    status="duplicate",
                    observation_id=existing.last_observation_id,
                )

            current_order = (
                existing.observed_at,
                existing.last_report_id,
            )
            incoming_order = (report.observed_at, report.report_id)
            if exceeds_max_age or incoming_order <= current_order:
                processed = await AlertObservationInboxModel.find_one(
                    {"_id": observation_id}
                )
                if processed is not None:
                    observation = processed.observation
                    expected_source_event_id = (
                        report.source_event_id
                        or f"component-report:{report.report_id}"
                    )
                    if not (
                        observation.source_key == definition.source_key
                        and observation.resource_type == definition.resource_type
                        and observation.resource_id == resource_id
                        and observation.resource_name == resource_name
                        and observation.resource_url == resource_url
                        and observation.field_key == definition.field_key
                        and observation.signal_key == definition.signal_key
                        and observation.value_type == definition.value_type
                        and observation.value == normalized_value
                        and observation.observed_at == report.observed_at
                        and observation.source_event_id
                        == expected_source_event_id
                        and observation.metadata == metadata
                    ):
                        raise ValueError(
                            "相同 report_id 不能对应不同组件信号载荷"
                        )
                    return ComponentSignalReportResult(
                        report_id=report.report_id,
                        status="duplicate",
                        observation_id=observation_id,
                    )
                return ComponentSignalReportResult(
                    report_id=report.report_id,
                    status="stale",
                )

            updated_at = utc_now()
            raw = (
                await ComponentSignalSnapshotModel.get_motor_collection()
                .find_one_and_update(
                    {
                        "_id": snapshot_id,
                        "version": existing.version,
                    },
                    {
                        "$set": {
                            "definition_key": definition.definition_key,
                            "definition_version": definition.definition_version,
                            "source_schema_version": definition.source_schema_version,
                            "source_key": definition.source_key,
                            "resource_type": definition.resource_type,
                            "resource_id": resource_id,
                            "resource_name": resource_name,
                            "resource_url": resource_url,
                            "field_key": definition.field_key,
                            "signal_key": definition.signal_key,
                            "value_type": definition.value_type.value,
                            "current_value": normalized_value,
                            "last_report_id": report.report_id,
                            "last_observation_id": observation_id,
                            "last_source_event_id": report.source_event_id,
                            "last_component_id": context.component_id,
                            "last_component_run_id": context.component_run_id,
                            "last_action_id": context.action_id,
                            "last_node_instance_id": context.node_instance_id,
                            "observed_at": report.observed_at,
                            "metadata": metadata,
                            "updated_at": updated_at,
                        },
                        "$inc": {"version": 1},
                    },
                    return_document=ReturnDocument.AFTER,
                )
            )
            if raw is None:
                continue
            snapshot = ComponentSignalSnapshotModel.model_validate(raw)
            await AlertObservationInboxService.publish(
                self._observation_from_snapshot(snapshot)
            )
            return ComponentSignalReportResult(
                report_id=report.report_id,
                status="accepted",
                observation_id=observation_id,
            )
        raise RuntimeError("组件信号快照并发更新冲突，请使用相同 report_id 重试")
