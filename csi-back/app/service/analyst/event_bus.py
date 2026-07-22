"""基于 Redis Streams 的分析事件跨实例实时总线。"""

from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass
from typing import Any

from loguru import logger

from app.core.config import settings
from app.db.redis import get_redis

logger = logger.bind(name=__name__)


@dataclass
class AnalystEventSubscription:
    """一个可关闭的 Redis Streams 消费任务。"""

    key: str
    cursor: str
    queue: asyncio.Queue
    replay_max_seq: int = 0
    persisted_max_seq: int = 0
    task: asyncio.Task | None = None

    async def close(self) -> None:
        """取消当前订阅的阻塞读取任务。"""
        if self.task is None:
            return
        self.task.cancel()
        try:
            await self.task
        except asyncio.CancelledError:
            pass
        self.task = None


class AnalystEventBus:
    """为 SSE 提供跨 Worker 的 Redis Streams 发布与订阅。"""

    _namespace = "csi:analyst:events"

    @classmethod
    def stream_key(cls, agent_id: str, session_id: str) -> str:
        """构造按会话隔离的 Redis Stream key。"""
        return f"{cls._namespace}:{agent_id}:{session_id}"

    @classmethod
    async def publish(
        cls,
        *,
        agent_id: str,
        session_id: str,
        event: str,
        data: Any,
        seq: int | None = None,
    ) -> bool:
        """发布事件到 Redis Stream；Redis 不可用时返回 False 供本地路径降级。"""
        redis = get_redis()
        if redis is None:
            return False
        key = cls.stream_key(agent_id, session_id)
        fields = {
            "event": event,
            "data": json.dumps(data, ensure_ascii=False, default=str),
            "seq": str(seq or ""),
        }
        try:
            await redis.xadd(
                key,
                fields,
                maxlen=max(100, settings.NANOBOT_EVENT_STREAM_MAXLEN),
                approximate=True,
            )
            await redis.expire(key, max(60, settings.NANOBOT_EVENT_STREAM_TTL_SECONDS))
            return True
        except Exception:
            logger.exception(
                "发布分析事件到 Redis Stream 失败: agent_id={} session_id={} event={}",
                agent_id,
                session_id,
                event,
            )
            return False

    @classmethod
    async def prepare_subscription(
        cls,
        agent_id: str,
        session_id: str,
        queue: asyncio.Queue,
    ) -> AnalystEventSubscription | None:
        """在数据库回放前记录 Stream 游标，消除回放与实时订阅之间的事件空窗。"""
        redis = get_redis()
        if redis is None:
            return None
        key = cls.stream_key(agent_id, session_id)
        try:
            latest = await redis.xrevrange(key, count=1)
        except Exception:
            logger.exception(
                "读取分析事件 Stream 游标失败: agent_id={} session_id={}",
                agent_id,
                session_id,
            )
            return None
        cursor = latest[0][0] if latest else "0-0"
        return AnalystEventSubscription(key=key, cursor=cursor, queue=queue)

    @classmethod
    def start_subscription(
        cls,
        subscription: AnalystEventSubscription,
        *,
        replay_max_seq: int = 0,
        persisted_max_seq: int = 0,
    ) -> None:
        """数据库回放完成后，从预先记录的游标开始消费实时事件。"""
        subscription.replay_max_seq = replay_max_seq
        subscription.persisted_max_seq = persisted_max_seq
        subscription.task = asyncio.create_task(
            cls._pump(subscription),
            name=f"analyst-event-stream:{subscription.key}",
        )

    @classmethod
    async def _pump(cls, subscription: AnalystEventSubscription) -> None:
        """持续读取 Redis Stream，并按 Mongo seq 去除回放阶段产生的重复事件。"""
        cursor = subscription.cursor
        recovered = False
        while True:
            try:
                redis = get_redis()
                if redis is None:
                    await asyncio.sleep(1.0)
                    continue
                if not recovered and cursor != "0-0":
                    rows = await redis.xrange(
                        subscription.key,
                        min="-",
                        max=cursor,
                    )
                    for _, fields in rows:
                        raw_seq = fields.get("seq")
                        seq = int(raw_seq) if raw_seq else None
                        if seq is None or seq <= subscription.persisted_max_seq:
                            continue
                        try:
                            data = json.loads(fields.get("data") or "null")
                        except json.JSONDecodeError:
                            data = fields.get("data")
                        await subscription.queue.put(
                            {
                                "event": fields.get("event") or "message",
                                "data": data,
                                "id": seq,
                            }
                        )
                    recovered = True
                rows = await redis.xread(
                    {subscription.key: cursor},
                    count=100,
                    block=15000,
                )
                for _, messages in rows or []:
                    for message_id, fields in messages:
                        cursor = message_id
                        raw_seq = fields.get("seq")
                        seq = int(raw_seq) if raw_seq else None
                        if seq is not None and seq <= subscription.replay_max_seq:
                            continue
                        try:
                            data = json.loads(fields.get("data") or "null")
                        except json.JSONDecodeError:
                            data = fields.get("data")
                        await subscription.queue.put(
                            {
                                "event": fields.get("event") or "message",
                                "data": data,
                                "id": seq,
                            }
                        )
            except asyncio.CancelledError:
                raise
            except Exception:
                logger.exception(
                    "消费分析事件 Stream 失败，将从原游标重试: key={} cursor={}",
                    subscription.key,
                    cursor,
                )
                await asyncio.sleep(1.0)


__all__ = ["AnalystEventBus", "AnalystEventSubscription"]
