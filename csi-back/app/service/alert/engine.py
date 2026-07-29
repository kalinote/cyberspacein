from __future__ import annotations

import hashlib
import json
import secrets
from datetime import datetime, timezone

from pymongo.errors import DuplicateKeyError

from app.db.redis import get_redis
from app.models.alert.evaluation_state import (
    AlertRuleEvaluationStateModel,
    AlertSignalStateModel,
)
from app.models.alert.rule import AlertRuleModel
from app.schemas.alert.constants import (
    ALERT_SEVERITY_ORDER,
    AlertInitialEvaluationPolicyEnum,
    AlertEvaluationModeEnum,
    AlertRuleStateEnum,
    AlertRuleValidationStatusEnum,
)
from app.schemas.alert.observation import AlertObservation
from app.service.alert.comparator import evaluate_expression, normalize_value
from app.service.alert.lifecycle import AlertLifecycleService
from app.service.alert.registry import AlertSourceRegistry, alert_source_registry
from app.utils.id_lib import generate_id


def utc_now() -> datetime:
    """返回带 UTC 时区的当前时间。"""
    return datetime.now(timezone.utc)


class AlertEngine:
    """把统一观测转换为规则状态、聚合信号和告警生命周期。"""

    def __init__(self, registry: AlertSourceRegistry | None = None) -> None:
        self.registry = registry or alert_source_registry

    @staticmethod
    def incident_key(observation: AlertObservation) -> str:
        """构造同一资源检测信号的稳定关联键。"""
        return generate_id(
            ":".join(
                [
                    observation.source_key,
                    observation.resource_type,
                    observation.resource_id,
                    observation.signal_key,
                ]
            )
        )

    @staticmethod
    def condition_fingerprint(rule: AlertRuleModel) -> str:
        """生成不包含等级等展示配置的条件状态指纹。"""
        payload = {
            "trigger": rule.trigger_expression.model_dump(mode="json"),
            "recovery": (
                rule.recovery_expression.model_dump(mode="json")
                if rule.recovery_expression
                else None
            ),
            "trigger_consecutive_count": rule.trigger_consecutive_count,
            "recovery_consecutive_count": rule.recovery_consecutive_count,
        }
        serialized = json.dumps(
            payload,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        return hashlib.sha256(serialized.encode("utf-8")).hexdigest()

    @staticmethod
    async def _acquire_lock(incident_key: str) -> str | None:
        """获取信号级 Redis 短锁，Redis 未初始化时允许单进程降级。"""
        redis = get_redis()
        if redis is None:
            return "local"
        token = secrets.token_urlsafe(18)
        acquired = await redis.set(
            f"alert:incident-lock:{incident_key}",
            token,
            ex=60,
            nx=True,
        )
        return token if acquired else None

    @staticmethod
    async def _release_lock(incident_key: str, token: str) -> None:
        """仅释放当前持有者的信号锁。"""
        redis = get_redis()
        if redis is None or token == "local":
            return
        await redis.eval(
            "if redis.call('GET', KEYS[1]) == ARGV[1] then return redis.call('DEL', KEYS[1]) else return 0 end",
            1,
            f"alert:incident-lock:{incident_key}",
            token,
        )

    async def _validate_observation(self, observation: AlertObservation):
        """校验观测与 Provider 描述一致并返回字段描述。"""
        field = self.registry.get_field(
            observation.source_key,
            observation.field_key,
        )
        descriptor = self.registry.get_descriptor(observation.source_key)
        if descriptor.resource_type != observation.resource_type:
            raise ValueError("观测资源类型与告警源描述不一致")
        if field.signal_key != observation.signal_key:
            raise ValueError("观测信号与告警字段描述不一致")
        if field.value_type != observation.value_type:
            raise ValueError("观测值类型与告警字段描述不一致")
        normalize_value(field.value_type, observation.value)
        return field

    @staticmethod
    async def _get_or_create_rule_state(
        rule: AlertRuleModel,
        observation: AlertObservation,
        incident_key: str,
    ) -> tuple[AlertRuleEvaluationStateModel, bool]:
        """读取或幂等创建规则资源状态。"""
        state_id = generate_id(
            f"{rule.id}:{observation.resource_type}:{observation.resource_id}"
        )
        existing = await AlertRuleEvaluationStateModel.find_one({"_id": state_id})
        if existing is not None:
            return existing, False
        state = AlertRuleEvaluationStateModel(
            id=state_id,
            rule_id=rule.id,
            rule_version=rule.version,
            condition_fingerprint=AlertEngine.condition_fingerprint(rule),
            source_key=observation.source_key,
            resource_type=observation.resource_type,
            resource_id=observation.resource_id,
            signal_key=observation.signal_key,
            incident_key=incident_key,
            last_value=observation.value,
            last_value_type=observation.value_type,
            last_observation_id=observation.observation_id,
            last_source_event_id=observation.source_event_id,
            last_observed_at=observation.observed_at,
        )
        try:
            await state.insert()
            return state, True
        except DuplicateKeyError:
            existing = await AlertRuleEvaluationStateModel.find_one({"_id": state_id})
            if existing is None:
                raise
            return existing, False

    @staticmethod
    async def _apply_rule(
        rule: AlertRuleModel,
        observation: AlertObservation,
        incident_key: str,
    ) -> AlertRuleEvaluationStateModel:
        """根据触发、恢复和连续次数更新单条规则状态。"""
        state, created = await AlertEngine._get_or_create_rule_state(
            rule,
            observation,
            incident_key,
        )
        fingerprint = AlertEngine.condition_fingerprint(rule)
        if (
            not created
            and state.last_observation_id == observation.observation_id
            and state.rule_version == rule.version
            and state.condition_fingerprint == fingerprint
        ):
            return state
        condition_changed = (
            state.condition_fingerprint is not None
            and state.condition_fingerprint != fingerprint
        )
        if condition_changed:
            state.state = AlertRuleStateEnum.NORMAL
            state.activated_at = None
            state.recovered_at = observation.observed_at
            state.trigger_match_count = 0
            state.recovery_match_count = 0
        if state.rule_version != rule.version or condition_changed:
            state.rule_version = rule.version
        state.condition_fingerprint = fingerprint
        now = utc_now()
        if state.state == AlertRuleStateEnum.NORMAL:
            trigger_matches = evaluate_expression(
                rule.trigger_expression,
                observation.value_type,
                observation.value,
            )
            state.trigger_match_count = (
                state.trigger_match_count + 1 if trigger_matches else 0
            )
            state.recovery_match_count = 0
            if state.trigger_match_count >= rule.trigger_consecutive_count:
                state.state = AlertRuleStateEnum.ACTIVE
                state.activated_at = observation.observed_at
                state.recovered_at = None
        elif rule.recovery_expression is not None:
            recovery_matches = evaluate_expression(
                rule.recovery_expression,
                observation.value_type,
                observation.value,
            )
            state.recovery_match_count = (
                state.recovery_match_count + 1 if recovery_matches else 0
            )
            if state.recovery_match_count >= rule.recovery_consecutive_count:
                state.state = AlertRuleStateEnum.NORMAL
                state.trigger_match_count = 0
                state.recovered_at = observation.observed_at
        state.last_value = observation.value
        state.last_value_type = observation.value_type
        state.last_observation_id = observation.observation_id
        state.last_source_event_id = observation.source_event_id
        state.last_observed_at = observation.observed_at
        state.updated_at = now
        await state.save()
        return state

    @staticmethod
    async def _get_or_create_signal(
        observation: AlertObservation,
        incident_key: str,
    ) -> AlertSignalStateModel:
        """读取或创建信号聚合状态。"""
        signal = await AlertSignalStateModel.find_one({"incident_key": incident_key})
        if signal is not None:
            return signal
        signal = AlertSignalStateModel(
            id=incident_key,
            incident_key=incident_key,
            source_key=observation.source_key,
            resource_type=observation.resource_type,
            resource_id=observation.resource_id,
            signal_key=observation.signal_key,
        )
        try:
            await signal.insert()
            return signal
        except DuplicateKeyError:
            existing = await AlertSignalStateModel.find_one(
                {"incident_key": incident_key}
            )
            if existing is None:
                raise
            return existing

    @staticmethod
    async def _active_rules(
        incident_key: str,
    ) -> list[AlertRuleModel]:
        """读取当前信号所有仍处于活动状态的规则。"""
        states = await AlertRuleEvaluationStateModel.find(
            {
                "incident_key": incident_key,
                "state": AlertRuleStateEnum.ACTIVE,
            }
        ).to_list()
        if not states:
            return []
        rule_ids = list(dict.fromkeys(state.rule_id for state in states))
        rules = await AlertRuleModel.find({"_id": {"$in": rule_ids}}).to_list()
        order = {rule_id: index for index, rule_id in enumerate(rule_ids)}
        return sorted(rules, key=lambda item: order.get(item.id, len(order)))

    async def process_observation(
        self,
        observation: AlertObservation,
        *,
        target_rule_id: str | None = None,
        realtime_only: bool = False,
    ) -> int:
        """处理一条观测并返回实际匹配的规则数量。"""
        await self._validate_observation(observation)
        filters = {
            "source_key": observation.source_key,
            "field_key": observation.field_key,
            "enabled": True,
            "is_deleted": False,
            "validation_status": AlertRuleValidationStatusEnum.VALID,
        }
        if target_rule_id is not None:
            filters["_id"] = target_rule_id
        if realtime_only:
            filters["evaluation_mode"] = {
                "$in": [
                    AlertEvaluationModeEnum.REALTIME,
                    AlertEvaluationModeEnum.HYBRID,
                ]
            }
        rules = await AlertRuleModel.find(filters).to_list()
        observation.observed_at = (
            observation.observed_at.replace(tzinfo=timezone.utc)
            if observation.observed_at.tzinfo is None
            else observation.observed_at.astimezone(timezone.utc)
        )
        rules = [
            rule
            for rule in rules
            if not (
                rule.initial_evaluation_policy
                == AlertInitialEvaluationPolicyEnum.FROM_ACTIVATION
                and observation.observed_at
                < (
                    rule.active_from.replace(tzinfo=timezone.utc)
                    if rule.active_from.tzinfo is None
                    else rule.active_from.astimezone(timezone.utc)
                )
            )
        ]
        if not rules:
            return 0
        incident_key = self.incident_key(observation)
        token = await self._acquire_lock(incident_key)
        if token is None:
            return 0
        try:
            for rule in rules:
                await self._apply_rule(rule, observation, incident_key)
            active_rules = await self._active_rules(incident_key)
            signal = await self._get_or_create_signal(observation, incident_key)
            now = utc_now()
            if active_rules:
                severity = max(
                    (rule.severity for rule in active_rules),
                    key=lambda item: ALERT_SEVERITY_ORDER[item],
                )
                signal.active_rule_ids = sorted(rule.id for rule in active_rules)
                signal.effective_severity = severity
                signal.last_abnormal_at = observation.observed_at
                if signal.manual_suppressed:
                    signal.updated_at = now
                    await signal.save()
                    return len(rules)
                alert = (
                    await AlertLifecycleService.get(signal.current_alert_id)
                    if signal.current_alert_id
                    else None
                )
                if alert is None:
                    signal.anomaly_sequence += 1
                    alert = await AlertLifecycleService.create_or_get(
                        incident_key=incident_key,
                        anomaly_sequence=signal.anomaly_sequence,
                        active_rules=active_rules,
                        severity=severity,
                        observation=observation,
                    )
                    signal.current_alert_id = alert.id
                    signal.armed = False
                else:
                    await AlertLifecycleService.sync_active(
                        alert,
                        active_rules=active_rules,
                        severity=severity,
                        observation=observation,
                    )
            else:
                signal.active_rule_ids = []
                signal.effective_severity = None
                signal.last_normal_at = observation.observed_at
                if signal.manual_suppressed:
                    signal.manual_suppressed = False
                    signal.armed = True
                elif signal.current_alert_id:
                    alert = await AlertLifecycleService.get(signal.current_alert_id)
                    await AlertLifecycleService.resolve_auto(alert, observation)
                    signal.current_alert_id = None
                    signal.armed = True
                else:
                    signal.armed = True
            signal.updated_at = now
            await signal.save()
            return len(rules)
        finally:
            await self._release_lock(incident_key, token)
