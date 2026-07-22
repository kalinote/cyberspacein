"""有副作用工具的持久化幂等执行仓储。"""

from __future__ import annotations

import json
from datetime import datetime
from typing import Any

from pymongo.errors import DuplicateKeyError

from app.models.agent.runtime import NanobotToolExecutionModel
from app.schemas.agent.runtime_state import (
    NanobotToolExecutionStatusEnum,
)
from app.service.analyst.runtime_store import AnalystRuntimeStore


class AnalystToolExecutionStore:
    """以 run_id/tool_call_id 唯一键阻止写工具被重复执行。"""

    @staticmethod
    async def claim(
        *,
        run_id: str,
        session_id: str,
        agent_id: str,
        tool_call_id: str,
        tool_name: str,
        arguments_hash: str,
        lease_token: str,
    ) -> tuple[str, Any]:
        """领取工具调用，返回 execute、cached 或 blocked。"""
        execution_id = f"{run_id}:{tool_call_id}"
        now = datetime.now()
        if not await AnalystRuntimeStore.owns_active_lease(run_id, lease_token):
            return "blocked", "当前 Worker 已失去 Run 租约或任务正在停止"
        try:
            await NanobotToolExecutionModel(
                id=execution_id,
                run_id=run_id,
                session_id=session_id,
                agent_id=agent_id,
                tool_call_id=tool_call_id,
                tool_name=tool_name,
                arguments_hash=arguments_hash,
                lease_token=lease_token,
                started_at=now,
                created_at=now,
                updated_at=now,
            ).insert()
            return "execute", None
        except DuplicateKeyError:
            existing = await NanobotToolExecutionModel.find_one({"_id": execution_id})

        if existing is None:
            return "blocked", "工具幂等记录冲突且无法读取"
        if existing.tool_name != tool_name or existing.arguments_hash != arguments_hash:
            return "blocked", "同一 tool_call_id 对应了不同的工具或参数"
        if existing.status == NanobotToolExecutionStatusEnum.SUCCEEDED:
            return "cached", existing.result
        if existing.status == NanobotToolExecutionStatusEnum.FAILED:
            return "blocked", existing.error_message or "该工具调用此前已经失败"
        if existing.status == NanobotToolExecutionStatusEnum.UNKNOWN:
            return "blocked", "该写工具在 Worker 中断前的执行结果未知，需要人工核对"

        if existing.lease_token != lease_token:
            await NanobotToolExecutionModel.get_motor_collection().update_one(
                {
                    "_id": execution_id,
                    "status": NanobotToolExecutionStatusEnum.CLAIMED.value,
                    "lease_token": existing.lease_token,
                },
                {
                    "$set": {
                        "status": NanobotToolExecutionStatusEnum.UNKNOWN.value,
                        "error_message": "原 Worker 在工具执行完成前失去租约",
                        "finished_at": now,
                        "updated_at": now,
                    }
                },
            )
            return "blocked", "该写工具在原 Worker 中断前的执行结果未知，需要人工核对"
        return "blocked", "同一工具调用正在执行或尚未完成"

    @staticmethod
    async def succeed(
        *,
        run_id: str,
        tool_call_id: str,
        lease_token: str,
        result: Any,
    ) -> bool:
        """仅由领取该调用的租约持有者提交成功结果。"""
        now = datetime.now()
        safe_result = json.loads(json.dumps(result, ensure_ascii=False, default=str))
        update = await NanobotToolExecutionModel.get_motor_collection().update_one(
            {
                "_id": f"{run_id}:{tool_call_id}",
                "status": NanobotToolExecutionStatusEnum.CLAIMED.value,
                "lease_token": lease_token,
            },
            {
                "$set": {
                    "status": NanobotToolExecutionStatusEnum.SUCCEEDED.value,
                    "result": safe_result,
                    "finished_at": now,
                    "updated_at": now,
                }
            },
        )
        return update.modified_count == 1

    @staticmethod
    async def fail(
        *,
        run_id: str,
        tool_call_id: str,
        lease_token: str,
        error_message: str,
    ) -> bool:
        """仅由领取该调用的租约持有者提交失败结果。"""
        now = datetime.now()
        update = await NanobotToolExecutionModel.get_motor_collection().update_one(
            {
                "_id": f"{run_id}:{tool_call_id}",
                "status": NanobotToolExecutionStatusEnum.CLAIMED.value,
                "lease_token": lease_token,
            },
            {
                "$set": {
                    "status": NanobotToolExecutionStatusEnum.FAILED.value,
                    "error_message": error_message,
                    "finished_at": now,
                    "updated_at": now,
                }
            },
        )
        return update.modified_count == 1

    @staticmethod
    async def mark_unfinished_unknown(run_id: str, reason: str) -> int:
        """Run 中断时将未提交结果的写工具标为结果未知。"""
        now = datetime.now()
        update = await NanobotToolExecutionModel.get_motor_collection().update_many(
            {
                "run_id": run_id,
                "status": NanobotToolExecutionStatusEnum.CLAIMED.value,
            },
            {
                "$set": {
                    "status": NanobotToolExecutionStatusEnum.UNKNOWN.value,
                    "error_message": reason,
                    "finished_at": now,
                    "updated_at": now,
                }
            },
        )
        return int(update.modified_count)


__all__ = ["AnalystToolExecutionStore"]
