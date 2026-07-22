"""分析引擎持久化 Run 的原子领取、租约与终态仓储。"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta
from typing import Any

from pymongo import ReturnDocument
from pymongo.errors import DuplicateKeyError

from app.core.config import settings
from app.models.agent.runtime import NanobotRunModel
from app.schemas.agent.runtime_state import (
    NanobotRunDesiredStateEnum,
    NanobotRunStatusEnum,
)


class AnalystRuntimeCapacityError(RuntimeError):
    """Agent 的持久化并行 Run 槽位已用尽。"""


class AnalystRuntimeStore:
    """以 MongoDB 为权威状态的分布式 Run 仓储。"""

    @staticmethod
    async def create_run(
        *,
        run_id: str,
        session_id: str,
        agent_id: str,
        workspace_id: str,
        generation: int,
        user_prompt: str,
        context: dict[str, Any] | None = None,
        auto_approve: bool = False,
        initiator_user_id: str | None = None,
    ) -> NanobotRunModel:
        """创建一个等待 Worker 领取的持久化 Run。"""
        now = datetime.now()
        max_parallel = settings.NANOBOT_AGENT_MAX_PARALLEL_SESSIONS
        slots: tuple[int | None, ...] = (
            tuple(range(max_parallel)) if max_parallel > 0 else (None,)
        )
        for parallel_slot in slots:
            doc = NanobotRunModel(
                id=run_id,
                session_id=session_id,
                agent_id=agent_id,
                workspace_id=workspace_id,
                generation=generation,
                parallel_slot=parallel_slot,
                user_prompt=user_prompt,
                context=dict(context or {}),
                auto_approve=auto_approve,
                initiator_user_id=initiator_user_id,
                max_attempts=max(1, settings.NANOBOT_RUNTIME_MAX_ATTEMPTS),
                queued_at=now,
                created_at=now,
                updated_at=now,
            )
            try:
                await doc.insert()
                return doc
            except DuplicateKeyError:
                if max_parallel <= 0:
                    raise
        raise AnalystRuntimeCapacityError(
            f"Agent 已达到持久化并行 Run 上限: {max_parallel}"
        )

    @staticmethod
    async def claim_next(worker_id: str) -> NanobotRunModel | None:
        """原子领取最早的 queued Run，并分配新的 fencing lease token。"""
        now = datetime.now()
        lease_token = str(uuid.uuid4())
        collection = NanobotRunModel.get_motor_collection()
        raw = await collection.find_one_and_update(
            {
                "active": True,
                "dispatch_ready": True,
                "status": NanobotRunStatusEnum.QUEUED.value,
                "desired_state": NanobotRunDesiredStateEnum.RUNNING.value,
                "$expr": {"$lt": ["$attempt", "$max_attempts"]},
            },
            {
                "$set": {
                    "status": NanobotRunStatusEnum.RUNNING.value,
                    "worker_id": worker_id,
                    "lease_token": lease_token,
                    "lease_expires_at": now
                    + timedelta(seconds=settings.NANOBOT_RUNTIME_LEASE_SECONDS),
                    "last_heartbeat_at": now,
                    "started_at": now,
                    "updated_at": now,
                },
                "$inc": {"attempt": 1},
            },
            sort=[("queued_at", 1)],
            return_document=ReturnDocument.AFTER,
        )
        return NanobotRunModel.model_validate(raw) if raw else None

    @staticmethod
    async def activate_queued(run_id: str) -> bool:
        """会话状态和首批事件就绪后开放 Run 给 Worker 领取。"""
        result = await NanobotRunModel.get_motor_collection().update_one(
            {
                "_id": run_id,
                "active": True,
                "dispatch_ready": {"$ne": True},
                "status": NanobotRunStatusEnum.QUEUED.value,
            },
            {"$set": {"dispatch_ready": True, "updated_at": datetime.now()}},
        )
        return result.modified_count == 1

    @staticmethod
    async def renew_lease(run_id: str, worker_id: str, lease_token: str) -> bool:
        """仅允许当前租约持有者续租。"""
        now = datetime.now()
        result = await NanobotRunModel.get_motor_collection().update_one(
            {
                "_id": run_id,
                "active": True,
                "worker_id": worker_id,
                "lease_token": lease_token,
                "lease_expires_at": {"$gt": now},
                "status": {
                    "$in": [
                        NanobotRunStatusEnum.RUNNING.value,
                        NanobotRunStatusEnum.AWAITING_APPROVAL.value,
                    ]
                },
            },
            {
                "$set": {
                    "lease_expires_at": now
                    + timedelta(seconds=settings.NANOBOT_RUNTIME_LEASE_SECONDS),
                    "last_heartbeat_at": now,
                    "updated_at": now,
                }
            },
        )
        return result.modified_count == 1

    @staticmethod
    async def get(run_id: str) -> NanobotRunModel | None:
        """按 ID 读取 Run。"""
        return await NanobotRunModel.find_one({"_id": run_id})

    @staticmethod
    async def owns_active_lease(run_id: str, lease_token: str) -> bool:
        """验证 fencing token 仍持有可执行的有效租约。"""
        now = datetime.now()
        run = await NanobotRunModel.find_one(
            {
                "_id": run_id,
                "active": True,
                "desired_state": NanobotRunDesiredStateEnum.RUNNING.value,
                "lease_token": lease_token,
                "lease_expires_at": {"$gt": now},
                "status": {
                    "$in": [
                        NanobotRunStatusEnum.RUNNING.value,
                        NanobotRunStatusEnum.AWAITING_APPROVAL.value,
                    ]
                },
            }
        )
        return run is not None

    @staticmethod
    async def get_active_for_session(
        agent_id: str,
        session_id: str,
    ) -> NanobotRunModel | None:
        """查询会话当前唯一的活动 Run。"""
        return await NanobotRunModel.find_one(
            {
                "agent_id": agent_id,
                "session_id": session_id,
                "active": True,
            }
        )

    @staticmethod
    async def request_state(
        run_id: str,
        desired_state: NanobotRunDesiredStateEnum,
        reason: str | None = None,
    ) -> bool:
        """持久化取消或暂停意图，供任意 Worker 观察。"""
        now = datetime.now()
        result = await NanobotRunModel.get_motor_collection().update_one(
            {"_id": run_id, "active": True},
            {
                "$set": {
                    "desired_state": desired_state.value,
                    "requested_reason": reason,
                    "updated_at": now,
                }
            },
        )
        return result.modified_count == 1

    @staticmethod
    async def request_session_stop(
        *,
        agent_id: str,
        session_id: str,
        desired_state: NanobotRunDesiredStateEnum,
        reason: str,
    ) -> NanobotRunModel | None:
        """停止会话活动 Run；未领取任务直接落终态，已领取任务写入期望状态。"""
        now = datetime.now()
        terminal_status = (
            NanobotRunStatusEnum.PAUSED
            if desired_state == NanobotRunDesiredStateEnum.PAUSED
            else NanobotRunStatusEnum.CANCELLED
        )
        collection = NanobotRunModel.get_motor_collection()
        raw = await collection.find_one_and_update(
            {
                "agent_id": agent_id,
                "session_id": session_id,
                "active": True,
                "status": NanobotRunStatusEnum.QUEUED.value,
            },
            {
                "$set": {
                    "active": False,
                    "status": terminal_status.value,
                    "desired_state": desired_state.value,
                    "requested_reason": reason,
                    "error_message": reason,
                    "finished_at": now,
                    "updated_at": now,
                }
            },
            return_document=ReturnDocument.AFTER,
        )
        if raw:
            return NanobotRunModel.model_validate(raw)
        raw = await collection.find_one_and_update(
            {
                "agent_id": agent_id,
                "session_id": session_id,
                "active": True,
            },
            {
                "$set": {
                    "desired_state": desired_state.value,
                    "requested_reason": reason,
                    "updated_at": now,
                }
            },
            return_document=ReturnDocument.AFTER,
        )
        return NanobotRunModel.model_validate(raw) if raw else None

    @staticmethod
    async def abandon_queued(run_id: str, error_message: str) -> bool:
        """投递会话失败时关闭尚未领取的 Run。"""
        now = datetime.now()
        result = await NanobotRunModel.get_motor_collection().update_one(
            {
                "_id": run_id,
                "active": True,
                "status": NanobotRunStatusEnum.QUEUED.value,
            },
            {
                "$set": {
                    "active": False,
                    "status": NanobotRunStatusEnum.FAILED.value,
                    "error_message": error_message,
                    "finished_at": now,
                    "updated_at": now,
                }
            },
        )
        return result.modified_count == 1

    @staticmethod
    async def set_status(
        run_id: str,
        worker_id: str,
        lease_token: str,
        status: NanobotRunStatusEnum,
    ) -> bool:
        """当前租约持有者更新非终态状态。"""
        now = datetime.now()
        result = await NanobotRunModel.get_motor_collection().update_one(
            {
                "_id": run_id,
                "active": True,
                "worker_id": worker_id,
                "lease_token": lease_token,
                "lease_expires_at": {"$gt": now},
            },
            {"$set": {"status": status.value, "updated_at": now}},
        )
        return result.modified_count == 1

    @staticmethod
    async def finish(
        *,
        run_id: str,
        worker_id: str,
        lease_token: str,
        status: NanobotRunStatusEnum,
        result: dict[str, Any] | None = None,
        error_message: str | None = None,
    ) -> bool:
        """使用 fencing token 原子提交 Run 终态，失租 Worker 无权覆盖结果。"""
        now = datetime.now()
        update = await NanobotRunModel.get_motor_collection().update_one(
            {
                "_id": run_id,
                "active": True,
                "worker_id": worker_id,
                "lease_token": lease_token,
                "lease_expires_at": {"$gt": now},
            },
            {
                "$set": {
                    "active": False,
                    "status": status.value,
                    "result": result,
                    "error_message": error_message,
                    "finished_at": now,
                    "updated_at": now,
                    "lease_expires_at": None,
                }
            },
        )
        return update.modified_count == 1

    @staticmethod
    async def expire_stale() -> list[NanobotRunModel]:
        """收敛租约过期的执行中 Run，避免数据库长期残留幽灵任务。"""
        now = datetime.now()
        docs = await NanobotRunModel.find(
            {
                "active": True,
                "status": {
                    "$in": [
                        NanobotRunStatusEnum.RUNNING.value,
                        NanobotRunStatusEnum.AWAITING_APPROVAL.value,
                    ]
                },
                "lease_expires_at": {"$lte": now},
            }
        ).to_list()
        expired: list[NanobotRunModel] = []
        collection = NanobotRunModel.get_motor_collection()
        for doc in docs:
            result = await collection.update_one(
                {
                    "_id": doc.id,
                    "active": True,
                    "lease_token": doc.lease_token,
                    "lease_expires_at": {"$lte": now},
                },
                {
                    "$set": {
                        "active": False,
                        "status": NanobotRunStatusEnum.INTERRUPTED.value,
                        "error_message": "Worker 心跳租约已过期，运行已中断",
                        "finished_at": now,
                        "updated_at": now,
                    }
                },
            )
            if result.modified_count == 1:
                doc.active = False
                doc.status = NanobotRunStatusEnum.INTERRUPTED
                doc.error_message = "Worker 心跳租约已过期，运行已中断"
                doc.finished_at = now
                expired.append(doc)
        return expired

    @staticmethod
    async def expire_unready() -> list[NanobotRunModel]:
        """收敛 API 投递过程中崩溃而从未开放领取的 Run。"""
        now = datetime.now()
        deadline = now - timedelta(seconds=settings.NANOBOT_RUNTIME_LEASE_SECONDS)
        docs = await NanobotRunModel.find(
            {
                "active": True,
                "dispatch_ready": {"$ne": True},
                "status": NanobotRunStatusEnum.QUEUED.value,
                "queued_at": {"$lte": deadline},
            }
        ).to_list()
        expired: list[NanobotRunModel] = []
        collection = NanobotRunModel.get_motor_collection()
        for doc in docs:
            result = await collection.update_one(
                {
                    "_id": doc.id,
                    "active": True,
                    "dispatch_ready": {"$ne": True},
                    "status": NanobotRunStatusEnum.QUEUED.value,
                },
                {
                    "$set": {
                        "active": False,
                        "status": NanobotRunStatusEnum.INTERRUPTED.value,
                        "error_message": "API 投递未完成，运行未进入可领取状态",
                        "finished_at": now,
                        "updated_at": now,
                    }
                },
            )
            if result.modified_count == 1:
                doc.active = False
                doc.status = NanobotRunStatusEnum.INTERRUPTED
                doc.error_message = "API 投递未完成，运行未进入可领取状态"
                doc.finished_at = now
                expired.append(doc)
        return expired


__all__ = ["AnalystRuntimeCapacityError", "AnalystRuntimeStore"]
