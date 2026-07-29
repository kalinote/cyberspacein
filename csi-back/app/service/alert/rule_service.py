from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from pydantic import ValidationError

import app.utils.status_codes as status_codes
from app.core.config import settings
from app.core.exceptions import ApiException, BadRequestException, NotFoundException
from app.models.alert.rule import AlertRuleModel
from app.schemas.alert.condition import AlertExpression
from app.schemas.alert.constants import (
    AlertEvaluationModeEnum,
    AlertInitialEvaluationPolicyEnum,
    AlertOperatorEnum,
    AlertRuleValidationStatusEnum,
    AlertValueTypeEnum,
)
from app.schemas.alert.rule import (
    AlertRuleCreateRequest,
    AlertRuleEnabledRequest,
    AlertRuleUpdateRequest,
)
from app.schemas.alert.source import AlertFieldDescriptor, AlertSourceDescriptor
from app.service.alert.comparator import normalize_threshold
from app.service.alert.registry import AlertSourceRegistry, alert_source_registry
from app.service.alert.stream import AlertStreamService


def utc_now() -> datetime:
    """返回带 UTC 时区的当前时间。"""
    return datetime.now(timezone.utc)


class AlertRuleService:
    """校验、持久化和试运行告警规则。"""

    def __init__(self, registry: AlertSourceRegistry | None = None) -> None:
        self.registry = registry or alert_source_registry

    @staticmethod
    def _validate_expression(
        expression: AlertExpression,
        field: AlertFieldDescriptor,
    ) -> None:
        """按照 Provider 字段能力校验表达式。"""
        enum_values = {item.value for item in field.enum_options}
        for condition in expression.conditions:
            if condition.field_key != field.field_key:
                raise BadRequestException("条件字段与规则检测字段不一致")
            if condition.operator not in field.supported_operators:
                raise BadRequestException(
                    f"字段不支持运算符: {condition.operator.value}"
                )
            try:
                normalized = normalize_threshold(field.value_type, condition.value)
            except ValueError as exc:
                raise BadRequestException(str(exc)) from exc
            if field.value_type != AlertValueTypeEnum.ENUM:
                continue
            values = (
                normalized.value
                if isinstance(normalized.value, list)
                else [normalized.value]
            )
            invalid = [value for value in values if value not in enum_values]
            if invalid:
                raise BadRequestException(
                    f"枚举阈值不存在: {', '.join(map(str, invalid))}"
                )
            if condition.operator in {
                AlertOperatorEnum.IN,
                AlertOperatorEnum.NOT_IN,
            } and not isinstance(condition.value.value, list):
                raise BadRequestException("属于运算符必须使用枚举值列表")

    def validate_payload(
        self,
        payload: AlertRuleCreateRequest,
    ) -> tuple[AlertSourceDescriptor, AlertFieldDescriptor]:
        """校验规则与已注册告警源是否兼容。"""
        try:
            descriptor = self.registry.get_descriptor(payload.source_key)
            field = self.registry.get_field(payload.source_key, payload.field_key)
        except KeyError as exc:
            raise BadRequestException(str(exc)) from exc
        if payload.evaluation_mode not in field.supported_evaluation_modes:
            raise BadRequestException("字段不支持所选检测方式")
        if payload.initial_evaluation_policy is not None and (
            payload.initial_evaluation_policy
            not in {
                AlertInitialEvaluationPolicyEnum.FROM_ACTIVATION,
                AlertInitialEvaluationPolicyEnum.INCLUDE_EXISTING,
            }
        ):
            raise BadRequestException("首次检测策略无效")
        self._validate_expression(payload.trigger_expression, field)
        if payload.recovery_expression is not None:
            self._validate_expression(payload.recovery_expression, field)
        return descriptor, field

    @staticmethod
    async def _emit_rule_change(rule: AlertRuleModel, event_type: str) -> None:
        """把规则变化写入可靠 SSE Outbox。"""
        await AlertStreamService.enqueue(
            event_id=f"rule:{rule.id}:v{rule.version}:{event_type}",
            event_type=event_type,
            aggregate_type="alert_rule",
            aggregate_id=rule.id,
            aggregate_version=rule.version,
            payload={
                "rule_id": rule.id,
                "version": rule.version,
                "enabled": rule.enabled,
                "validation_status": rule.validation_status.value,
                "updated_at": rule.updated_at.isoformat(),
            },
        )

    async def create(self, payload: AlertRuleCreateRequest) -> AlertRuleModel:
        """创建并立即安排首次检测。"""
        descriptor, field = self.validate_payload(payload)
        now = utc_now()
        initial_policy = (
            payload.initial_evaluation_policy or field.initial_evaluation_policy
        )
        reconciliation = (
            settings.ALERT_REALTIME_RECONCILE_SECONDS
            if payload.evaluation_mode
            in {
                AlertEvaluationModeEnum.REALTIME,
                AlertEvaluationModeEnum.HYBRID,
            }
            else None
        )
        rule = AlertRuleModel(
            id=uuid4().hex,
            name=payload.name,
            description=payload.description,
            source_key=payload.source_key,
            source_schema_version=descriptor.schema_version,
            field_key=payload.field_key,
            signal_key=field.signal_key,
            resource_scope=payload.resource_scope,
            trigger_expression=payload.trigger_expression,
            recovery_expression=payload.recovery_expression,
            severity=payload.severity,
            evaluation_mode=payload.evaluation_mode,
            interval_seconds=payload.interval_seconds,
            reconciliation_interval_seconds=reconciliation,
            initial_evaluation_policy=initial_policy,
            trigger_consecutive_count=payload.trigger_consecutive_count,
            recovery_consecutive_count=payload.recovery_consecutive_count,
            enabled=payload.enabled,
            validation_status=AlertRuleValidationStatusEnum.VALID,
            active_from=now,
            next_evaluate_at=now if payload.enabled else None,
            created_at=now,
            updated_at=now,
        )
        await rule.insert()
        await self._emit_rule_change(rule, "rule.created")
        return rule

    @staticmethod
    async def get(rule_id: str) -> AlertRuleModel:
        """读取未删除规则。"""
        rule = await AlertRuleModel.find_one({"_id": rule_id, "is_deleted": False})
        if rule is None:
            raise NotFoundException("告警规则不存在")
        return rule

    async def update(
        self,
        rule_id: str,
        payload: AlertRuleUpdateRequest,
    ) -> AlertRuleModel:
        """按乐观版本修改规则并重新安排检测。"""
        rule = await self.get(rule_id)
        if rule.version != payload.expected_version:
            raise ApiException(status_codes.CONFLICT_STATE, "规则版本已变化，请刷新后重试")
        values = {
            "name": payload.name if payload.name is not None else rule.name,
            "description": (
                payload.description
                if payload.description is not None
                else rule.description
            ),
            "source_key": rule.source_key,
            "field_key": rule.field_key,
            "resource_scope": rule.resource_scope,
            "trigger_expression": payload.trigger_expression or rule.trigger_expression,
            "recovery_expression": (
                None
                if payload.clear_recovery_expression
                else (
                    payload.recovery_expression
                    if payload.recovery_expression is not None
                    else rule.recovery_expression
                )
            ),
            "severity": payload.severity or rule.severity,
            "evaluation_mode": payload.evaluation_mode or rule.evaluation_mode,
            "interval_seconds": (
                payload.interval_seconds
                if "interval_seconds" in payload.model_fields_set
                else rule.interval_seconds
            ),
            "initial_evaluation_policy": (
                payload.initial_evaluation_policy or rule.initial_evaluation_policy
            ),
            "trigger_consecutive_count": (
                payload.trigger_consecutive_count or rule.trigger_consecutive_count
            ),
            "recovery_consecutive_count": (
                payload.recovery_consecutive_count or rule.recovery_consecutive_count
            ),
            "enabled": rule.enabled,
        }
        if values["evaluation_mode"] == AlertEvaluationModeEnum.REALTIME:
            values["interval_seconds"] = None
        try:
            candidate = AlertRuleCreateRequest(**values)
        except ValidationError as exc:
            raise BadRequestException(
                "规则修改后配置无效",
                data={"errors": exc.errors(include_url=False)},
            ) from exc
        descriptor, field = self.validate_payload(candidate)
        now = utc_now()
        update_result = await AlertRuleModel.find_one(
            {
                "_id": rule.id,
                "version": payload.expected_version,
                "is_deleted": False,
            }
        ).update(
            {
                "$set": {
                    "name": candidate.name,
                    "description": candidate.description,
                    "trigger_expression": candidate.trigger_expression.model_dump(),
                    "recovery_expression": (
                        candidate.recovery_expression.model_dump()
                        if candidate.recovery_expression
                        else None
                    ),
                    "severity": candidate.severity.value,
                    "evaluation_mode": candidate.evaluation_mode.value,
                    "interval_seconds": candidate.interval_seconds,
                    "reconciliation_interval_seconds": (
                        settings.ALERT_REALTIME_RECONCILE_SECONDS
                        if candidate.evaluation_mode
                        in {
                            AlertEvaluationModeEnum.REALTIME,
                            AlertEvaluationModeEnum.HYBRID,
                        }
                        else None
                    ),
                    "initial_evaluation_policy": (
                        candidate.initial_evaluation_policy
                        or field.initial_evaluation_policy
                    ).value,
                    "trigger_consecutive_count": candidate.trigger_consecutive_count,
                    "recovery_consecutive_count": candidate.recovery_consecutive_count,
                    "source_schema_version": descriptor.schema_version,
                    "signal_key": field.signal_key,
                    "validation_status": AlertRuleValidationStatusEnum.VALID.value,
                    "validation_message": None,
                    "next_evaluate_at": now if rule.enabled else None,
                    "updated_at": now,
                },
                "$inc": {"version": 1},
            }
        )
        if not update_result or update_result.modified_count != 1:
            raise ApiException(status_codes.CONFLICT_STATE, "规则版本已变化，请刷新后重试")
        updated = await self.get(rule.id)
        await self._emit_rule_change(updated, "rule.updated")
        return updated

    async def set_enabled(
        self,
        rule_id: str,
        payload: AlertRuleEnabledRequest,
    ) -> AlertRuleModel:
        """按版本启用或停用规则。"""
        rule = await self.get(rule_id)
        if rule.version != payload.expected_version:
            raise ApiException(status_codes.CONFLICT_STATE, "规则版本已变化，请刷新后重试")
        if rule.enabled == payload.enabled:
            return rule
        now = utc_now()
        result = await AlertRuleModel.find_one(
            {
                "_id": rule.id,
                "version": payload.expected_version,
                "is_deleted": False,
            }
        ).update(
            {
                "$set": {
                    "enabled": payload.enabled,
                    "next_evaluate_at": now if payload.enabled else None,
                    "active_from": now if payload.enabled else rule.active_from,
                    "updated_at": now,
                },
                "$inc": {"version": 1},
            }
        )
        if not result or result.modified_count != 1:
            raise ApiException(status_codes.CONFLICT_STATE, "规则版本已变化，请刷新后重试")
        updated = await self.get(rule.id)
        await self._emit_rule_change(updated, "rule.updated")
        return updated

    async def delete(self, rule_id: str, expected_version: int) -> AlertRuleModel:
        """软删除规则并保留历史关联。"""
        rule = await self.get(rule_id)
        if rule.version != expected_version:
            raise ApiException(status_codes.CONFLICT_STATE, "规则版本已变化，请刷新后重试")
        now = utc_now()
        result = await AlertRuleModel.find_one(
            {"_id": rule.id, "version": expected_version, "is_deleted": False}
        ).update(
            {
                "$set": {
                    "is_deleted": True,
                    "enabled": False,
                    "next_evaluate_at": None,
                    "updated_at": now,
                },
                "$inc": {"version": 1},
            }
        )
        if not result or result.modified_count != 1:
            raise ApiException(status_codes.CONFLICT_STATE, "规则版本已变化，请刷新后重试")
        deleted = await AlertRuleModel.find_one({"_id": rule.id})
        await self._emit_rule_change(deleted, "rule.deleted")
        return deleted
