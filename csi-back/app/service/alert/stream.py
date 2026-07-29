from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from typing import Any

from loguru import logger
from pymongo import ReturnDocument
from pymongo.errors import DuplicateKeyError

from app.core.config import settings
from app.db.redis import get_redis
from app.models.alert.stream_outbox import AlertStreamOutboxModel
from app.schemas.alert.constants import AlertOutboxStatusEnum

logger = logger.bind(name=__name__)


def utc_now() -> datetime:
    """返回带 UTC 时区的当前时间。"""
    return datetime.now(timezone.utc)


class AlertStreamService:
    """通过 MongoDB Outbox 和 Redis Stream 发布告警领域变化。"""

    STREAM_KEY = "csi:alerts:events"

    @staticmethod
    async def enqueue(
        *,
        event_id: str,
        event_type: str,
        aggregate_type: str,
        aggregate_id: str | None,
        aggregate_version: int | None,
        payload: dict[str, Any],
    ) -> AlertStreamOutboxModel:
        """幂等写入一条待发布 SSE 事件。"""
        existing = await AlertStreamOutboxModel.find_one({"_id": event_id})
        if existing is not None:
            return existing
        outbox = AlertStreamOutboxModel(
            id=event_id,
            event_type=event_type,
            aggregate_type=aggregate_type,
            aggregate_id=aggregate_id,
            aggregate_version=aggregate_version,
            payload=payload,
        )
        try:
            await outbox.insert()
            return outbox
        except DuplicateKeyError:
            existing = await AlertStreamOutboxModel.find_one({"_id": event_id})
            if existing is None:
                raise
            return existing

    @classmethod
    async def claim(cls, worker_id: str) -> AlertStreamOutboxModel | None:
        """原子声明一条待投递或租约过期的 Outbox。"""
        now = utc_now()
        raw = await AlertStreamOutboxModel.get_motor_collection().find_one_and_update(
            {
                "$or": [
                    {
                        "status": {
                            "$in": [
                                AlertOutboxStatusEnum.PENDING.value,
                                AlertOutboxStatusEnum.FAILED.value,
                            ]
                        },
                        "attempts": {
                            "$lt": settings.ALERT_OBSERVATION_MAX_ATTEMPTS
                        },
                        "$or": [
                            {"next_retry_at": None},
                            {"next_retry_at": {"$lte": now}},
                        ],
                    },
                    {
                        "status": AlertOutboxStatusEnum.PUBLISHING.value,
                        "lease_until": {"$lte": now},
                    },
                ]
            },
            {
                "$set": {
                    "status": AlertOutboxStatusEnum.PUBLISHING.value,
                    "claimed_by": worker_id,
                    "lease_until": now
                    + timedelta(seconds=settings.ALERT_OBSERVATION_LEASE_SECONDS),
                    "last_error": None,
                },
                "$inc": {"attempts": 1},
            },
            sort=[("created_at", 1)],
            return_document=ReturnDocument.AFTER,
        )
        return AlertStreamOutboxModel.model_validate(raw) if raw else None

    @classmethod
    async def publish_one(
        cls,
        outbox: AlertStreamOutboxModel,
        worker_id: str,
    ) -> bool:
        """发布一条 Outbox 并更新其投递状态。"""
        redis = get_redis()
        now = utc_now()
        try:
            if redis is None:
                raise RuntimeError("Redis 尚未初始化")
            stream_id = await redis.xadd(
                cls.STREAM_KEY,
                {
                    "event_id": outbox.id,
                    "event": outbox.event_type,
                    "aggregate_type": outbox.aggregate_type,
                    "aggregate_id": outbox.aggregate_id or "",
                    "aggregate_version": str(outbox.aggregate_version or ""),
                    "data": json.dumps(
                        outbox.payload,
                        ensure_ascii=False,
                        default=str,
                    ),
                },
                maxlen=max(100, settings.ALERT_SSE_STREAM_MAXLEN),
                approximate=True,
            )
            result = await AlertStreamOutboxModel.get_motor_collection().update_one(
                {
                    "_id": outbox.id,
                    "status": AlertOutboxStatusEnum.PUBLISHING.value,
                    "claimed_by": worker_id,
                },
                {
                    "$set": {
                        "status": AlertOutboxStatusEnum.PUBLISHED.value,
                        "published_at": now,
                        "last_error": None,
                        "next_retry_at": None,
                        "claimed_by": None,
                        "lease_until": None,
                        "expire_at": now
                        + timedelta(
                            days=max(
                                1,
                                settings.ALERT_OBSERVATION_RETENTION_DAYS,
                            )
                        ),
                        "payload.stream_id": stream_id,
                    }
                },
            )
            return result.modified_count == 1
        except Exception as exc:
            status = (
                AlertOutboxStatusEnum.FAILED
                if outbox.attempts >= settings.ALERT_OBSERVATION_MAX_ATTEMPTS
                else AlertOutboxStatusEnum.PENDING
            )
            await AlertStreamOutboxModel.get_motor_collection().update_one(
                {
                    "_id": outbox.id,
                    "status": AlertOutboxStatusEnum.PUBLISHING.value,
                    "claimed_by": worker_id,
                },
                {
                    "$set": {
                        "status": status.value,
                        "claimed_by": None,
                        "lease_until": None,
                        "last_error": str(exc)[:2000],
                        "next_retry_at": (
                            None
                            if status == AlertOutboxStatusEnum.FAILED
                            else now
                            + timedelta(
                                seconds=min(2 ** min(outbox.attempts, 8), 300)
                            )
                        ),
                    }
                },
            )
            logger.warning(f"告警 SSE Outbox 发布失败: {outbox.id}: {exc}")
            return False

    @classmethod
    async def publish_pending(
        cls,
        limit: int = 100,
        *,
        worker_id: str = "inline",
    ) -> int:
        """批量发布到期 Outbox。"""
        published = 0
        for _ in range(limit):
            item = await cls.claim(worker_id)
            if item is None:
                break
            if await cls.publish_one(item, worker_id):
                published += 1
        return published

    @classmethod
    async def latest_cursor(cls) -> str:
        """读取当前告警事件流的最新游标。"""
        redis = get_redis()
        if redis is None:
            return "0-0"
        rows = await redis.xrevrange(cls.STREAM_KEY, count=1)
        return rows[0][0] if rows else "0-0"

    @staticmethod
    def _cursor_tuple(cursor: str) -> tuple[int, int] | None:
        """解析 Redis Stream 游标，非法值返回空。"""
        try:
            milliseconds, sequence = cursor.split("-", 1)
            return int(milliseconds), int(sequence)
        except (AttributeError, TypeError, ValueError):
            return None

    @classmethod
    async def replay_status(
        cls,
        cursor: str,
    ) -> tuple[bool, str, str]:
        """判断游标是否早于当前保留窗口，并返回首尾游标。"""
        redis = get_redis()
        if redis is None:
            return False, "0-0", "0-0"
        oldest_rows = await redis.xrange(cls.STREAM_KEY, count=1)
        latest_rows = await redis.xrevrange(cls.STREAM_KEY, count=1)
        if not oldest_rows or not latest_rows:
            return False, "0-0", "0-0"
        oldest = oldest_rows[0][0]
        latest = latest_rows[0][0]
        parsed = cls._cursor_tuple(cursor)
        if cursor == "0-0":
            return False, oldest, latest
        oldest_parsed = cls._cursor_tuple(oldest)
        stale = (
            parsed is None
            or oldest_parsed is None
            or parsed < oldest_parsed
        )
        return stale, oldest, latest

    @classmethod
    async def read_after(
        cls,
        cursor: str,
        *,
        block_ms: int = 15000,
        count: int = 100,
    ) -> list[tuple[str, dict[str, str]]]:
        """从指定 Redis Stream 游标之后读取事件。"""
        redis = get_redis()
        if redis is None:
            return []
        rows = await redis.xread(
            {cls.STREAM_KEY: cursor},
            count=count,
            block=block_ms,
        )
        messages: list[tuple[str, dict[str, str]]] = []
        for _, stream_messages in rows or []:
            messages.extend(stream_messages)
        return messages
