"""分析引擎分布式 Run、审批与工具执行持久化模型。"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from beanie import Document
from pydantic import Field
from pymongo import ASCENDING, DESCENDING, IndexModel

from app.schemas.agent.runtime_state import (
    NanobotApprovalStatusEnum,
    NanobotRunDesiredStateEnum,
    NanobotRunStatusEnum,
    NanobotToolExecutionStatusEnum,
)


class NanobotRunModel(Document):
    """一次可被任意 Worker 领取的持久化分析运行。"""

    id: str = Field(alias="_id", description="Run ID")
    session_id: str
    agent_id: str
    workspace_id: str
    generation: int = Field(ge=1)
    parallel_slot: int | None = Field(default=None, ge=0)
    active: bool = True
    dispatch_ready: bool = False

    status: NanobotRunStatusEnum = NanobotRunStatusEnum.QUEUED
    desired_state: NanobotRunDesiredStateEnum = NanobotRunDesiredStateEnum.RUNNING
    requested_reason: str | None = None
    user_prompt: str
    context: dict[str, Any] = Field(default_factory=dict)
    auto_approve: bool = False
    initiator_user_id: str | None = None

    worker_id: str | None = None
    lease_token: str | None = None
    lease_expires_at: datetime | None = None
    last_heartbeat_at: datetime | None = None
    attempt: int = 0
    max_attempts: int = Field(default=1, ge=1)

    result: dict[str, Any] | None = None
    error_message: str | None = None
    queued_at: datetime = Field(default_factory=datetime.now)
    started_at: datetime | None = None
    finished_at: datetime | None = None
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)

    class Settings:
        name = "nanobot_runs"
        indexes = [
            IndexModel(
                [("session_id", ASCENDING), ("generation", ASCENDING)],
                unique=True,
            ),
            IndexModel(
                [("session_id", ASCENDING), ("active", ASCENDING)],
                unique=True,
                partialFilterExpression={"active": True},
            ),
            IndexModel(
                [("agent_id", ASCENDING), ("parallel_slot", ASCENDING)],
                unique=True,
                partialFilterExpression={
                    "active": True,
                    "parallel_slot": {"$gte": 0},
                },
            ),
            IndexModel(
                [
                    ("status", ASCENDING),
                    ("dispatch_ready", ASCENDING),
                    ("queued_at", ASCENDING),
                ],
            ),
            IndexModel(
                [("active", ASCENDING), ("lease_expires_at", ASCENDING)],
            ),
            IndexModel(
                [("agent_id", ASCENDING), ("created_at", DESCENDING)],
            ),
        ]


class NanobotApprovalModel(Document):
    """不依赖进程内 Queue 的持久化审批请求。"""

    id: str = Field(alias="_id", description="approval_request_id")
    run_id: str
    session_id: str
    agent_id: str
    source: str
    payload: dict[str, Any] = Field(default_factory=dict)
    status: NanobotApprovalStatusEnum = NanobotApprovalStatusEnum.PENDING
    decisions: list[dict[str, Any]] = Field(default_factory=list)
    resolution: str | None = None
    reject_reasons: list[str] | None = None
    requested_at: datetime = Field(default_factory=datetime.now)
    resolved_at: datetime | None = None
    resolver_user_id: str | None = None
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)

    class Settings:
        name = "nanobot_approvals"
        indexes = [
            IndexModel(
                [("run_id", ASCENDING), ("status", ASCENDING)],
            ),
            IndexModel(
                [("session_id", ASCENDING), ("requested_at", DESCENDING)],
            ),
        ]


class NanobotToolExecutionModel(Document):
    """写工具按 run/tool_call 维度的幂等执行记录。"""

    id: str = Field(alias="_id", description="建议为 run_id:tool_call_id")
    run_id: str
    session_id: str
    agent_id: str
    tool_call_id: str
    tool_name: str
    arguments_hash: str
    status: NanobotToolExecutionStatusEnum = NanobotToolExecutionStatusEnum.CLAIMED
    lease_token: str
    result: Any = None
    error_message: str | None = None
    started_at: datetime = Field(default_factory=datetime.now)
    finished_at: datetime | None = None
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)

    class Settings:
        name = "nanobot_tool_executions"
        indexes = [
            IndexModel(
                [("run_id", ASCENDING), ("tool_call_id", ASCENDING)],
                unique=True,
            ),
            IndexModel(
                [("session_id", ASCENDING), ("created_at", ASCENDING)],
            ),
        ]


__all__ = [
    "NanobotApprovalModel",
    "NanobotRunModel",
    "NanobotToolExecutionModel",
]
