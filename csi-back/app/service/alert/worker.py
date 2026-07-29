from __future__ import annotations

import asyncio
import json
import secrets
from contextlib import suppress
from datetime import datetime, timedelta, timezone
from typing import Any

from loguru import logger

from app.core.config import settings
from app.db.redis import get_redis
from app.models.alert.rule import AlertRuleModel
from app.schemas.alert.constants import (
    AlertEvaluationModeEnum,
    AlertInitialEvaluationPolicyEnum,
    AlertRuleValidationStatusEnum,
)
from app.service.alert.engine import AlertEngine
from app.service.alert.observation_inbox import AlertObservationInboxService
from app.service.alert.registry import alert_source_registry
from app.service.alert.stream import AlertStreamService

logger = logger.bind(name=__name__)


def utc_now() -> datetime:
    """返回带 UTC 时区的当前时间。"""
    return datetime.now(timezone.utc)


class AlertWorkerService:
    """消费实时观测、扫描周期规则并分发告警事件。"""

    HEARTBEAT_KEY = "alert:worker:heartbeat"

    def __init__(self, worker_id: str) -> None:
        self.worker_id = worker_id
        self.engine = AlertEngine()
        self.last_observation_scan_at: datetime | None = None
        self.last_rule_scan_at: datetime | None = None
        self.last_sse_dispatch_at: datetime | None = None

    @staticmethod
    async def status() -> dict[str, Any]:
        """读取 Worker 心跳并判断是否在线。"""
        redis = get_redis()
        if redis is None:
            return {"online": False, "reason": "redis_unavailable"}
        raw = await redis.get(AlertWorkerService.HEARTBEAT_KEY)
        if not raw:
            return {"online": False}
        try:
            payload = json.loads(raw)
            heartbeat_at = datetime.fromisoformat(payload["heartbeat_at"])
            payload["online"] = (
                utc_now() - heartbeat_at
            ).total_seconds() <= settings.ALERT_WORKER_HEARTBEAT_TTL_SECONDS
            return payload
        except (KeyError, TypeError, ValueError):
            return {"online": False, "reason": "invalid_heartbeat"}

    async def heartbeat(self) -> None:
        """写入当前 Worker 的处理进度和存活时间。"""
        redis = get_redis()
        if redis is None:
            return
        payload = {
            "worker_id": self.worker_id,
            "heartbeat_at": utc_now().isoformat(),
            "last_observation_scan_at": (
                self.last_observation_scan_at.isoformat()
                if self.last_observation_scan_at
                else None
            ),
            "last_rule_scan_at": (
                self.last_rule_scan_at.isoformat()
                if self.last_rule_scan_at
                else None
            ),
            "last_sse_dispatch_at": (
                self.last_sse_dispatch_at.isoformat()
                if self.last_sse_dispatch_at
                else None
            ),
        }
        await redis.set(
            self.HEARTBEAT_KEY,
            json.dumps(payload, ensure_ascii=False),
            ex=settings.ALERT_WORKER_HEARTBEAT_TTL_SECONDS,
        )

    async def clear_heartbeat(self) -> None:
        """仅清理当前 Worker 自己写入的心跳。"""
        redis = get_redis()
        if redis is None:
            return
        raw = await redis.get(self.HEARTBEAT_KEY)
        if not raw:
            return
        with suppress(KeyError, TypeError, ValueError):
            if json.loads(raw).get("worker_id") == self.worker_id:
                await redis.delete(self.HEARTBEAT_KEY)

    @staticmethod
    async def _acquire_rule_lock(rule_id: str) -> str | None:
        """获取规则扫描 Redis 租约。"""
        redis = get_redis()
        if redis is None:
            return None
        token = secrets.token_urlsafe(18)
        acquired = await redis.set(
            f"alert:rule-lock:{rule_id}",
            token,
            ex=settings.ALERT_RULE_LOCK_SECONDS,
            nx=True,
        )
        return token if acquired else None

    @staticmethod
    async def _release_rule_lock(rule_id: str, token: str) -> None:
        """仅释放当前 Worker 持有的规则租约。"""
        redis = get_redis()
        if redis is None:
            return
        await redis.eval(
            "if redis.call('GET', KEYS[1]) == ARGV[1] then return redis.call('DEL', KEYS[1]) else return 0 end",
            1,
            f"alert:rule-lock:{rule_id}",
            token,
        )

    @staticmethod
    def _next_interval_seconds(rule: AlertRuleModel) -> int:
        """计算规则下一次补偿或周期扫描间隔。"""
        if rule.evaluation_mode == AlertEvaluationModeEnum.REALTIME:
            return (
                rule.reconciliation_interval_seconds
                or settings.ALERT_REALTIME_RECONCILE_SECONDS
            )
        return rule.interval_seconds or settings.ALERT_REALTIME_RECONCILE_SECONDS

    @staticmethod
    async def _mark_rule_invalid(
        rule: AlertRuleModel,
        message: str,
    ) -> None:
        """停止不再兼容 Provider 契约的规则并通知管理页面。"""
        now = utc_now()
        result = await AlertRuleModel.find_one(
            {
                "_id": rule.id,
                "version": rule.version,
                "validation_status": AlertRuleValidationStatusEnum.VALID,
            }
        ).update(
            {
                "$set": {
                    "validation_status": AlertRuleValidationStatusEnum.INVALID.value,
                    "validation_message": message[:2000],
                    "last_error": message[:2000],
                    "next_evaluate_at": None,
                    "updated_at": now,
                }
            }
        )
        if not result or result.modified_count != 1:
            return
        await AlertStreamService.enqueue(
            event_id=f"rule:{rule.id}:v{rule.version}:rule.invalid",
            event_type="rule.updated",
            aggregate_type="alert_rule",
            aggregate_id=rule.id,
            aggregate_version=rule.version,
            payload={
                "rule_id": rule.id,
                "version": rule.version,
                "enabled": rule.enabled,
                "validation_status": AlertRuleValidationStatusEnum.INVALID.value,
                "validation_message": message[:2000],
                "updated_at": now.isoformat(),
            },
        )

    async def scan_rule(self, rule: AlertRuleModel) -> int:
        """分页扫描一条到期规则并更新其运行状态。"""
        token = await self._acquire_rule_lock(rule.id)
        if token is None:
            return 0
        started_at = utc_now()
        try:
            current = await AlertRuleModel.find_one(
                {
                    "_id": rule.id,
                    "enabled": True,
                    "is_deleted": False,
                    "validation_status": AlertRuleValidationStatusEnum.VALID,
                    "next_evaluate_at": {"$lte": started_at},
                }
            )
            if current is None:
                return 0
            try:
                provider = alert_source_registry.get(current.source_key)
                descriptor = alert_source_registry.get_descriptor(
                    current.source_key
                )
                field = alert_source_registry.get_field(
                    current.source_key,
                    current.field_key,
                )
            except KeyError as exc:
                await self._mark_rule_invalid(current, str(exc))
                return 0
            if descriptor.schema_version != current.source_schema_version:
                await self._mark_rule_invalid(
                    current,
                    (
                        "告警源版本已变化，请重新保存规则："
                        f"{current.source_schema_version} -> "
                        f"{descriptor.schema_version}"
                    ),
                )
                return 0
            if field.signal_key != current.signal_key:
                await self._mark_rule_invalid(
                    current,
                    "告警字段信号契约已变化，请重新保存规则",
                )
                return 0
            active_from = (
                datetime(1970, 1, 1, tzinfo=timezone.utc)
                if current.initial_evaluation_policy
                == AlertInitialEvaluationPolicyEnum.INCLUDE_EXISTING
                else current.active_from
            )
            cursor: str | None = None
            processed = 0
            pages = 0
            while True:
                page = await provider.iter_observations(
                    field_key=current.field_key,
                    active_from=active_from,
                    cursor=cursor,
                    limit=settings.ALERT_PROVIDER_PAGE_SIZE,
                )
                for observation in page.items:
                    await self.engine.process_observation(
                        observation,
                        target_rule_id=current.id,
                    )
                    processed += 1
                pages += 1
                if not page.next_cursor:
                    break
                if pages >= 1000:
                    raise RuntimeError("Provider 单次扫描超过 1000 页安全上限")
                cursor = page.next_cursor
            finished_at = utc_now()
            await AlertRuleModel.find_one({"_id": current.id}).update(
                {
                    "$set": {
                        "last_evaluate_at": started_at,
                        "last_success_at": finished_at,
                        "last_error": None,
                        "next_evaluate_at": finished_at
                        + timedelta(
                            seconds=self._next_interval_seconds(current)
                        ),
                    }
                }
            )
            return processed
        except Exception as exc:
            retry_at = utc_now() + timedelta(
                seconds=min(self._next_interval_seconds(rule), 60)
            )
            await AlertRuleModel.find_one({"_id": rule.id}).update(
                {
                    "$set": {
                        "last_evaluate_at": started_at,
                        "last_error": str(exc)[:2000],
                        "next_evaluate_at": retry_at,
                    }
                }
            )
            logger.exception(f"告警规则扫描失败，Rule ID: {rule.id}: {exc}")
            return 0
        finally:
            await self._release_rule_lock(rule.id, token)

    async def scan_due_rules(self, limit: int = 50) -> int:
        """扫描本轮到期的有效规则。"""
        now = utc_now()
        rules = await AlertRuleModel.find(
            {
                "enabled": True,
                "is_deleted": False,
                "validation_status": AlertRuleValidationStatusEnum.VALID,
                "next_evaluate_at": {"$lte": now},
            }
        ).sort("+next_evaluate_at").limit(limit).to_list()
        processed = 0
        for rule in rules:
            processed += await self.scan_rule(rule)
        self.last_rule_scan_at = utc_now()
        return processed

    async def consume_observations(self, limit: int = 100) -> int:
        """领取并处理一批实时观测。"""
        processed = 0
        for _ in range(limit):
            inbox = await AlertObservationInboxService.claim(self.worker_id)
            if inbox is None:
                break
            try:
                await self.engine.process_observation(
                    inbox.observation,
                    realtime_only=True,
                )
                await AlertObservationInboxService.mark_processed(
                    inbox.id,
                    self.worker_id,
                )
                processed += 1
            except Exception as exc:
                await AlertObservationInboxService.mark_failed(
                    inbox.id,
                    self.worker_id,
                    exc,
                )
                logger.exception(f"告警实时观测处理失败，Inbox ID: {inbox.id}: {exc}")
        self.last_observation_scan_at = utc_now()
        return processed

    async def observation_loop(self, stop_event: asyncio.Event) -> None:
        """持续消费可靠观测收件箱。"""
        while not stop_event.is_set():
            try:
                count = await self.consume_observations()
            except Exception as exc:
                count = 0
                logger.exception(f"告警观测消费循环异常: {exc}")
            if count:
                await asyncio.sleep(0)
                continue
            try:
                await asyncio.wait_for(
                    stop_event.wait(),
                    timeout=settings.ALERT_WORKER_POLL_SECONDS,
                )
            except TimeoutError:
                pass

    async def rule_loop(self, stop_event: asyncio.Event) -> None:
        """持续扫描到期规则。"""
        while not stop_event.is_set():
            try:
                await self.scan_due_rules()
            except Exception as exc:
                logger.exception(f"告警规则扫描循环异常: {exc}")
            try:
                await asyncio.wait_for(
                    stop_event.wait(),
                    timeout=settings.ALERT_WORKER_POLL_SECONDS,
                )
            except TimeoutError:
                pass

    async def outbox_loop(self, stop_event: asyncio.Event) -> None:
        """持续把 MongoDB Outbox 分发到 Redis Stream。"""
        while not stop_event.is_set():
            try:
                await AlertStreamService.publish_pending(worker_id=self.worker_id)
                self.last_sse_dispatch_at = utc_now()
            except Exception as exc:
                logger.exception(f"告警 SSE Outbox 分发循环异常: {exc}")
            try:
                await asyncio.wait_for(
                    stop_event.wait(),
                    timeout=settings.ALERT_WORKER_POLL_SECONDS,
                )
            except TimeoutError:
                pass

    async def heartbeat_loop(self, stop_event: asyncio.Event) -> None:
        """持续刷新 Worker 心跳。"""
        while not stop_event.is_set():
            try:
                await self.heartbeat()
            except Exception as exc:
                logger.warning(f"告警 Worker 心跳写入失败: {exc}")
            try:
                await asyncio.wait_for(
                    stop_event.wait(),
                    timeout=settings.ALERT_WORKER_HEARTBEAT_SECONDS,
                )
            except TimeoutError:
                pass
