"""父子 Action Reference 队列的持久化桥接服务。"""

from __future__ import annotations

import asyncio
import uuid
from datetime import datetime, timedelta
from enum import Enum
from typing import Sequence

from pymongo import ReturnDocument
from pymongo.errors import DuplicateKeyError

from app.db import rabbitmq
from app.models.action.reference_bridge import (
    ReferenceBridgeDirectionEnum,
    ReferenceBridgeModel,
    ReferenceBridgeStatusEnum,
)
from app.schemas.action.reference import (
    ReferenceQueueBinding,
    ReferenceStreamDescriptor,
)
from app.utils.id_lib import generate_id


class ReferenceBridgeStepResult(str, Enum):
    """桥接器单步执行结果。"""

    IDLE = "idle"
    FORWARDED = "forwarded"
    CONTROL = "control"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    LEASE_LOST = "lease_lost"


class ReferenceBridgeLeaseLostError(RuntimeError):
    """Worker 已失去桥接租约。"""


class ReferenceBridgeService:
    """创建、领取并推进可恢复的 Reference 队列桥接。"""

    @staticmethod
    async def create(
        *,
        parent_action_id: str,
        child_action_id: str,
        parent_node_instance_id: str,
        public_port_id: str,
        direction: ReferenceBridgeDirectionEnum | str,
        sources: Sequence[ReferenceStreamDescriptor],
        destinations: Sequence[ReferenceStreamDescriptor],
        bridge_id: str | None = None,
    ) -> ReferenceBridgeModel:
        """幂等创建一个待领取的 Reference 桥接。"""
        if not sources:
            raise ValueError("Reference桥接至少需要一个源流")
        if not destinations:
            raise ValueError("Reference桥接至少需要一个目标流")
        normalized_direction = ReferenceBridgeDirectionEnum(direction)
        normalized_sources = list(sources)
        normalized_destinations = list(destinations)
        if len({source.stream_id for source in normalized_sources}) != len(
            normalized_sources
        ):
            raise ValueError("Reference桥接的源流ID不能重复")
        if len(
            {destination.queue_name for destination in normalized_destinations}
        ) != len(normalized_destinations):
            raise ValueError("Reference桥接的目标队列不能重复")
        resolved_id = bridge_id or generate_id(
            ":".join(
                (
                    "reference-bridge",
                    parent_action_id,
                    child_action_id,
                    parent_node_instance_id,
                    public_port_id,
                    normalized_direction.value,
                )
            )
        )
        now = datetime.now()
        bridge = ReferenceBridgeModel(
            id=resolved_id,
            parent_action_id=parent_action_id,
            child_action_id=child_action_id,
            parent_node_instance_id=parent_node_instance_id,
            public_port_id=public_port_id,
            direction=normalized_direction,
            sources=normalized_sources,
            destinations=normalized_destinations,
            created_at=now,
            updated_at=now,
        )
        try:
            await bridge.insert()
            return bridge
        except DuplicateKeyError:
            existing = await ReferenceBridgeModel.find_one({"_id": resolved_id})
            if existing is None:
                raise
            if (
                existing.parent_action_id != parent_action_id
                or existing.child_action_id != child_action_id
                or existing.parent_node_instance_id != parent_node_instance_id
                or existing.public_port_id != public_port_id
                or existing.direction != normalized_direction
                or existing.sources != normalized_sources
                or existing.destinations != normalized_destinations
            ):
                raise ValueError(f"桥接ID {resolved_id} 已被不同的流配置占用")
            return existing

    @staticmethod
    async def claim(
        *,
        worker_id: str,
        bridge_id: str | None = None,
        lease_seconds: int = 30,
    ) -> ReferenceBridgeModel | None:
        """原子领取待处理或租约过期的桥接。"""
        if lease_seconds <= 0:
            raise ValueError("桥接租约必须大于0秒")
        now = datetime.now()
        lease_token = str(uuid.uuid4())
        query: dict = {
            "status": {
                "$in": [
                    ReferenceBridgeStatusEnum.PENDING.value,
                    ReferenceBridgeStatusEnum.RUNNING.value,
                ]
            },
            "$or": [
                {"lease_expires_at": None},
                {"lease_expires_at": {"$exists": False}},
                {"lease_expires_at": {"$lte": now}},
            ],
        }
        if bridge_id:
            query["_id"] = bridge_id
        raw = (
            await ReferenceBridgeModel.get_motor_collection().find_one_and_update(
                query,
                {
                    "$set": {
                        "status": ReferenceBridgeStatusEnum.RUNNING.value,
                        "worker_id": worker_id,
                        "lease_token": lease_token,
                        "lease_expires_at": now + timedelta(seconds=lease_seconds),
                        "last_heartbeat_at": now,
                        "updated_at": now,
                    },
                    "$inc": {"attempt": 1},
                },
                sort=[("created_at", 1)],
                return_document=ReturnDocument.AFTER,
            )
        )
        return ReferenceBridgeModel.model_validate(raw) if raw else None

    @staticmethod
    async def renew_lease(
        *,
        bridge_id: str,
        worker_id: str,
        lease_token: str,
        lease_seconds: int = 30,
    ) -> bool:
        """仅由有效租约持有者续租。"""
        now = datetime.now()
        result = await ReferenceBridgeModel.get_motor_collection().update_one(
            {
                "_id": bridge_id,
                "status": ReferenceBridgeStatusEnum.RUNNING.value,
                "worker_id": worker_id,
                "lease_token": lease_token,
                "lease_expires_at": {"$gt": now},
            },
            {
                "$set": {
                    "lease_expires_at": now + timedelta(seconds=lease_seconds),
                    "last_heartbeat_at": now,
                    "updated_at": now,
                }
            },
        )
        return result.modified_count == 1

    @staticmethod
    async def cancel(bridge_id: str, reason: str | None = None) -> bool:
        """幂等取消尚未进入终态的桥接。"""
        now = datetime.now()
        result = await ReferenceBridgeModel.get_motor_collection().update_one(
            {
                "_id": bridge_id,
                "status": {
                    "$in": [
                        ReferenceBridgeStatusEnum.PENDING.value,
                        ReferenceBridgeStatusEnum.RUNNING.value,
                    ]
                },
            },
            {
                "$set": {
                    "status": ReferenceBridgeStatusEnum.CANCELLED.value,
                    "last_error": reason,
                    "cancelled_at": now,
                    "lease_expires_at": None,
                    "updated_at": now,
                }
            },
        )
        if result.modified_count == 1:
            return True
        existing = await ReferenceBridgeModel.find_one({"_id": bridge_id})
        return (
            existing is not None
            and existing.status == ReferenceBridgeStatusEnum.CANCELLED
        )

    @staticmethod
    async def process_once(
        *,
        bridge_id: str,
        worker_id: str,
        lease_token: str,
    ) -> ReferenceBridgeStepResult:
        """在有效租约下转存至多一条消息或聚合一次 EOS。"""
        bridge = await ReferenceBridgeService._get_owned_bridge(
            bridge_id=bridge_id,
            worker_id=worker_id,
            lease_token=lease_token,
        )
        if bridge is None:
            current = await ReferenceBridgeModel.find_one({"_id": bridge_id})
            if current and current.status == ReferenceBridgeStatusEnum.COMPLETED:
                return ReferenceBridgeStepResult.COMPLETED
            if current and current.status == ReferenceBridgeStatusEnum.CANCELLED:
                return ReferenceBridgeStepResult.CANCELLED
            if current and current.status == ReferenceBridgeStatusEnum.FAILED:
                return ReferenceBridgeStepResult.FAILED
            return ReferenceBridgeStepResult.LEASE_LOST

        if ReferenceBridgeService._all_sources_ended(bridge):
            return await ReferenceBridgeService._complete(
                bridge=bridge,
                worker_id=worker_id,
                lease_token=lease_token,
            )

        ended_stream_ids = ReferenceBridgeService._ended_stream_ids(bridge)
        for source in bridge.sources:
            if source.stream_id in ended_stream_ids:
                continue
            delivery = await rabbitmq.get_reference_message(source.queue_name)
            if delivery is None:
                continue
            try:
                control_kind = rabbitmq.get_reference_control_kind(delivery.message)
                if control_kind is None:
                    await rabbitmq.publish_reference_delivery(
                        delivery,
                        [destination.queue_name for destination in bridge.destinations],
                    )
                    await delivery.ack()
                    await ReferenceBridgeService._record_forwarded(
                        bridge_id=bridge.id,
                        worker_id=worker_id,
                        lease_token=lease_token,
                        byte_count=len(delivery.message.body),
                    )
                    return ReferenceBridgeStepResult.FORWARDED

                stream_id, producer_id = rabbitmq.get_reference_control_identity(
                    delivery.message
                )
                if stream_id != source.stream_id or not producer_id:
                    await ReferenceBridgeService._propagate_abort(
                        bridge=bridge,
                        producer_id=f"bridge:{bridge.id}",
                        reason="Reference控制消息缺少有效流或生产者身份",
                    )
                    failed = await ReferenceBridgeService._fail(
                        bridge=bridge,
                        worker_id=worker_id,
                        lease_token=lease_token,
                        error_message="Reference控制消息缺少有效流或生产者身份",
                    )
                    if not failed:
                        await delivery.nack(requeue=True)
                        return ReferenceBridgeStepResult.LEASE_LOST
                    await delivery.nack(requeue=False)
                    return ReferenceBridgeStepResult.FAILED

                control_key = ReferenceBridgeService._control_key(
                    stream_id,
                    producer_id,
                )
                if control_kind == "abort":
                    await ReferenceBridgeService._propagate_abort(
                        bridge=bridge,
                        producer_id=f"bridge:{bridge.id}",
                        reason="上游Reference流已中止",
                    )
                    failed = await ReferenceBridgeService._fail(
                        bridge=bridge,
                        worker_id=worker_id,
                        lease_token=lease_token,
                        error_message=f"源流 {stream_id} 被生产者 {producer_id} 中止",
                        abort_key=control_key,
                    )
                    if not failed:
                        await delivery.nack(requeue=True)
                        return ReferenceBridgeStepResult.LEASE_LOST
                    await delivery.ack()
                    return ReferenceBridgeStepResult.FAILED

                updated = await ReferenceBridgeService._record_eos(
                    bridge_id=bridge.id,
                    worker_id=worker_id,
                    lease_token=lease_token,
                    control_key=control_key,
                )
                if updated is None:
                    await delivery.nack(requeue=True)
                    return ReferenceBridgeStepResult.LEASE_LOST
                await delivery.ack()
                if ReferenceBridgeService._all_sources_ended(updated):
                    return await ReferenceBridgeService._complete(
                        bridge=updated,
                        worker_id=worker_id,
                        lease_token=lease_token,
                    )
                return ReferenceBridgeStepResult.CONTROL
            except Exception:
                if not delivery.message.processed:
                    await delivery.nack(requeue=True)
                raise
            finally:
                await delivery.close()
        return ReferenceBridgeStepResult.IDLE

    @staticmethod
    async def run_claimed(
        *,
        bridge_id: str,
        worker_id: str,
        lease_token: str,
        lease_seconds: int = 30,
        poll_interval: float = 0.1,
    ) -> ReferenceBridgeStepResult:
        """循环推进一个已领取桥接直至终态或失去租约。"""
        try:
            while True:
                renewed = await ReferenceBridgeService.renew_lease(
                    bridge_id=bridge_id,
                    worker_id=worker_id,
                    lease_token=lease_token,
                    lease_seconds=lease_seconds,
                )
                if not renewed:
                    return ReferenceBridgeStepResult.LEASE_LOST
                result = await ReferenceBridgeService.process_once(
                    bridge_id=bridge_id,
                    worker_id=worker_id,
                    lease_token=lease_token,
                )
                if result in {
                    ReferenceBridgeStepResult.COMPLETED,
                    ReferenceBridgeStepResult.FAILED,
                    ReferenceBridgeStepResult.CANCELLED,
                    ReferenceBridgeStepResult.LEASE_LOST,
                }:
                    return result
                if result == ReferenceBridgeStepResult.IDLE:
                    await asyncio.sleep(poll_interval)
        except BaseException as exc:
            now = datetime.now()
            try:
                await ReferenceBridgeModel.get_motor_collection().update_one(
                    {
                        "_id": bridge_id,
                        "status": ReferenceBridgeStatusEnum.RUNNING.value,
                        "worker_id": worker_id,
                        "lease_token": lease_token,
                    },
                    {
                        "$set": {
                            "last_error": str(exc) or "桥接Worker已停止",
                            "lease_expires_at": now + timedelta(seconds=1),
                            "updated_at": now,
                        }
                    },
                )
            except Exception:
                pass
            raise

    @staticmethod
    async def cleanup_owner_queues(
        owner_action_id: str,
        *,
        additional_streams: Sequence[
            ReferenceStreamDescriptor | ReferenceQueueBinding
        ] = (),
    ) -> list[str]:
        """幂等删除桥接记录中归指定 Action 所有的队列。"""
        bridges = await ReferenceBridgeModel.find(
            {
                "$or": [
                    {"sources.owner_action_id": owner_action_id},
                    {"destinations.owner_action_id": owner_action_id},
                ]
            }
        ).to_list()
        streams = list(additional_streams)
        for bridge in bridges:
            streams.extend(bridge.sources)
            streams.extend(bridge.destinations)
        unique_streams: dict[
            str,
            ReferenceStreamDescriptor | ReferenceQueueBinding,
        ] = {
            stream.queue_name: stream
            for stream in streams
            if stream.owner_action_id == owner_action_id
        }
        return await rabbitmq.delete_owned_queues(
            owner_action_id,
            list(unique_streams.values()),
        )

    @staticmethod
    async def _get_owned_bridge(
        *,
        bridge_id: str,
        worker_id: str,
        lease_token: str,
    ) -> ReferenceBridgeModel | None:
        """读取当前 Worker 仍持有有效租约的桥接。"""
        return await ReferenceBridgeModel.find_one(
            {
                "_id": bridge_id,
                "status": ReferenceBridgeStatusEnum.RUNNING.value,
                "worker_id": worker_id,
                "lease_token": lease_token,
                "lease_expires_at": {"$gt": datetime.now()},
            }
        )

    @staticmethod
    async def _record_forwarded(
        *,
        bridge_id: str,
        worker_id: str,
        lease_token: str,
        byte_count: int,
    ) -> None:
        """记录已确认转存的数据量。"""
        result = await ReferenceBridgeModel.get_motor_collection().update_one(
            {
                "_id": bridge_id,
                "status": ReferenceBridgeStatusEnum.RUNNING.value,
                "worker_id": worker_id,
                "lease_token": lease_token,
            },
            {
                "$inc": {
                    "copied_message_count": 1,
                    "copied_byte_count": byte_count,
                },
                "$set": {"updated_at": datetime.now(), "last_error": None},
            },
        )
        if result.modified_count != 1:
            raise ReferenceBridgeLeaseLostError("转存完成后桥接租约已失效")

    @staticmethod
    async def _record_eos(
        *,
        bridge_id: str,
        worker_id: str,
        lease_token: str,
        control_key: str,
    ) -> ReferenceBridgeModel | None:
        """幂等记录源生产者 EOS。"""
        raw = (
            await ReferenceBridgeModel.get_motor_collection().find_one_and_update(
                {
                    "_id": bridge_id,
                    "status": ReferenceBridgeStatusEnum.RUNNING.value,
                    "worker_id": worker_id,
                    "lease_token": lease_token,
                    "lease_expires_at": {"$gt": datetime.now()},
                },
                {
                    "$addToSet": {"received_eos_keys": control_key},
                    "$set": {
                        "updated_at": datetime.now(),
                        "last_error": None,
                    },
                },
                return_document=ReturnDocument.AFTER,
            )
        )
        return ReferenceBridgeModel.model_validate(raw) if raw else None

    @staticmethod
    async def _complete(
        *,
        bridge: ReferenceBridgeModel,
        worker_id: str,
        lease_token: str,
    ) -> ReferenceBridgeStepResult:
        """发布聚合 EOS 后以 fencing token 提交桥接终态。"""
        for destination in bridge.destinations:
            for producer_id in ReferenceBridgeService._destination_producer_ids(
                bridge,
                destination,
            ):
                await rabbitmq.publish_reference_control(
                    queue_names=[destination.queue_name],
                    stream_id=destination.stream_id,
                    producer_id=producer_id,
                    action_id=destination.owner_action_id,
                    status="eos",
                )
        now = datetime.now()
        result = await ReferenceBridgeModel.get_motor_collection().update_one(
            {
                "_id": bridge.id,
                "status": ReferenceBridgeStatusEnum.RUNNING.value,
                "worker_id": worker_id,
                "lease_token": lease_token,
                "lease_expires_at": {"$gt": now},
            },
            {
                "$set": {
                    "status": ReferenceBridgeStatusEnum.COMPLETED.value,
                    "completed_at": now,
                    "lease_expires_at": None,
                    "last_error": None,
                    "updated_at": now,
                }
            },
        )
        if result.modified_count != 1:
            return ReferenceBridgeStepResult.LEASE_LOST
        return ReferenceBridgeStepResult.COMPLETED

    @staticmethod
    async def _propagate_abort(
        *,
        bridge: ReferenceBridgeModel,
        producer_id: str,
        reason: str,
    ) -> None:
        """将源流 ABORT 聚合为桥接生产者 ABORT。"""
        for destination in bridge.destinations:
            producer_ids = (
                destination.expected_producer_ids
                if destination.expected_producer_ids
                else [producer_id]
            )
            for destination_producer_id in producer_ids:
                await rabbitmq.publish_reference_control(
                    queue_names=[destination.queue_name],
                    stream_id=destination.stream_id,
                    producer_id=destination_producer_id,
                    action_id=destination.owner_action_id,
                    status="abort",
                    reason=reason,
                )

    @staticmethod
    async def _fail(
        *,
        bridge: ReferenceBridgeModel,
        worker_id: str,
        lease_token: str,
        error_message: str,
        abort_key: str | None = None,
    ) -> bool:
        """由有效租约持有者提交桥接失败终态。"""
        now = datetime.now()
        update: dict = {
            "$set": {
                "status": ReferenceBridgeStatusEnum.FAILED.value,
                "last_error": error_message,
                "completed_at": now,
                "lease_expires_at": None,
                "updated_at": now,
            }
        }
        if abort_key:
            update["$addToSet"] = {"received_abort_keys": abort_key}
        result = await ReferenceBridgeModel.get_motor_collection().update_one(
            {
                "_id": bridge.id,
                "status": ReferenceBridgeStatusEnum.RUNNING.value,
                "worker_id": worker_id,
                "lease_token": lease_token,
            },
            update,
        )
        return result.modified_count == 1

    @staticmethod
    def _control_key(stream_id: str, producer_id: str) -> str:
        """构造不会与合法标识冲突的生产者终止键。"""
        return f"{stream_id}\x1f{producer_id}"

    @staticmethod
    def _received_producers(
        bridge: ReferenceBridgeModel,
        stream_id: str,
    ) -> set[str]:
        """返回指定流已记录 EOS 的生产者集合。"""
        prefix = f"{stream_id}\x1f"
        return {
            key[len(prefix) :]
            for key in bridge.received_eos_keys
            if key.startswith(prefix)
        }

    @staticmethod
    def _ended_stream_ids(bridge: ReferenceBridgeModel) -> set[str]:
        """计算已经收齐生产者 EOS 的源流。"""
        ended: set[str] = set()
        for source in bridge.sources:
            received = ReferenceBridgeService._received_producers(
                bridge,
                source.stream_id,
            )
            if source.expected_producer_ids:
                if set(source.expected_producer_ids).issubset(received):
                    ended.add(source.stream_id)
            elif received:
                ended.add(source.stream_id)
        return ended

    @staticmethod
    def _all_sources_ended(bridge: ReferenceBridgeModel) -> bool:
        """判断所有源流是否已经结束。"""
        return len(ReferenceBridgeService._ended_stream_ids(bridge)) == len(
            bridge.sources
        )

    @staticmethod
    def _destination_producer_ids(
        bridge: ReferenceBridgeModel,
        destination: ReferenceStreamDescriptor,
    ) -> list[str]:
        """返回目标消费契约期望收到的桥接生产者身份。"""
        return (
            destination.expected_producer_ids
            if destination.expected_producer_ids
            else [f"bridge:{bridge.id}"]
        )


__all__ = [
    "ReferenceBridgeLeaseLostError",
    "ReferenceBridgeService",
    "ReferenceBridgeStepResult",
]
