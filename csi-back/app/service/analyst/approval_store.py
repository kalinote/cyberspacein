"""分析引擎持久化审批请求仓储。"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pymongo import ReturnDocument

from app.models.agent.runtime import NanobotApprovalModel
from app.schemas.agent.runtime_state import NanobotApprovalStatusEnum


class AnalystApprovalStore:
    """提供跨进程可见且只能决议一次的审批原子操作。"""

    @staticmethod
    async def create(
        *,
        approval_request_id: str,
        run_id: str,
        session_id: str,
        agent_id: str,
        source: str,
        payload: dict[str, Any],
    ) -> NanobotApprovalModel:
        """创建待决议审批记录。"""
        now = datetime.now()
        doc = NanobotApprovalModel(
            id=approval_request_id,
            run_id=run_id,
            session_id=session_id,
            agent_id=agent_id,
            source=source,
            payload=dict(payload),
            requested_at=now,
            created_at=now,
            updated_at=now,
        )
        await doc.insert()
        return doc

    @staticmethod
    async def get(approval_request_id: str) -> NanobotApprovalModel | None:
        """按审批请求 ID 查询记录。"""
        return await NanobotApprovalModel.find_one({"_id": approval_request_id})

    @staticmethod
    async def get_pending(
        agent_id: str,
        session_id: str,
    ) -> NanobotApprovalModel | None:
        """查询会话当前最新的待审批记录。"""
        docs = (
            await NanobotApprovalModel.find(
                {
                    "agent_id": agent_id,
                    "session_id": session_id,
                    "status": NanobotApprovalStatusEnum.PENDING.value,
                }
            )
            .sort("-requested_at")
            .limit(1)
            .to_list()
        )
        return docs[0] if docs else None

    @staticmethod
    async def resolve(
        *,
        approval_request_id: str,
        agent_id: str,
        session_id: str,
        decisions: list[dict[str, Any]],
        resolution: str,
        reject_reasons: list[str] | None,
        resolver_user_id: str | None = None,
    ) -> NanobotApprovalModel | None:
        """仅将匹配会话的 pending 审批原子决议一次。"""
        try:
            status = NanobotApprovalStatusEnum(resolution)
        except ValueError:
            return None
        now = datetime.now()
        raw = await NanobotApprovalModel.get_motor_collection().find_one_and_update(
            {
                "_id": approval_request_id,
                "agent_id": agent_id,
                "session_id": session_id,
                "status": NanobotApprovalStatusEnum.PENDING.value,
            },
            {
                "$set": {
                    "status": status.value,
                    "decisions": list(decisions),
                    "resolution": resolution,
                    "reject_reasons": reject_reasons,
                    "resolver_user_id": resolver_user_id,
                    "resolved_at": now,
                    "updated_at": now,
                }
            },
            return_document=ReturnDocument.AFTER,
        )
        return NanobotApprovalModel.model_validate(raw) if raw else None

    @staticmethod
    async def cancel_pending_for_run(run_id: str, reason: str) -> int:
        """运行中断时批量取消尚未决议的审批。"""
        now = datetime.now()
        result = await NanobotApprovalModel.get_motor_collection().update_many(
            {
                "run_id": run_id,
                "status": NanobotApprovalStatusEnum.PENDING.value,
            },
            {
                "$set": {
                    "status": NanobotApprovalStatusEnum.CANCELLED.value,
                    "resolution": NanobotApprovalStatusEnum.CANCELLED.value,
                    "reject_reasons": [reason],
                    "resolved_at": now,
                    "updated_at": now,
                }
            },
        )
        return int(result.modified_count)


__all__ = ["AnalystApprovalStore"]
