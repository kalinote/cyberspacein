"""分析引擎分布式运行时的持久化状态枚举。"""

from __future__ import annotations

from enum import Enum


class NanobotRunStatusEnum(str, Enum):
    """持久化 Run 的生命周期状态。"""

    QUEUED = "queued"
    RUNNING = "running"
    AWAITING_APPROVAL = "awaiting_approval"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    PAUSED = "paused"
    INTERRUPTED = "interrupted"


class NanobotRunDesiredStateEnum(str, Enum):
    """API 写入、Worker 消费的期望运行状态。"""

    RUNNING = "running"
    CANCELLED = "cancelled"
    PAUSED = "paused"


class NanobotApprovalStatusEnum(str, Enum):
    """持久化审批请求状态。"""

    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    MIXED = "mixed"
    CANCELLED = "cancelled"


class NanobotToolExecutionStatusEnum(str, Enum):
    """写工具幂等执行记录状态。"""

    CLAIMED = "claimed"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    UNKNOWN = "unknown"


ACTIVE_RUN_STATUSES = frozenset(
    {
        NanobotRunStatusEnum.QUEUED,
        NanobotRunStatusEnum.RUNNING,
        NanobotRunStatusEnum.AWAITING_APPROVAL,
    }
)


TERMINAL_RUN_STATUSES = frozenset(set(NanobotRunStatusEnum) - set(ACTIVE_RUN_STATUSES))


__all__ = [
    "ACTIVE_RUN_STATUSES",
    "TERMINAL_RUN_STATUSES",
    "NanobotApprovalStatusEnum",
    "NanobotRunDesiredStateEnum",
    "NanobotRunStatusEnum",
    "NanobotToolExecutionStatusEnum",
]
