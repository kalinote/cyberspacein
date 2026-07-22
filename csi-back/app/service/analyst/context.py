"""ContextVar 绑定：在一次 `run_analysis` 协程内把 `agent_id / session_id` 暴露给业务工具。

业务工具（`modify_entity / notify_user / write_todos / submit_task_result` 等）通过这些 ContextVar
读取当前运行的 agent / session，从而：
- 按 `agent_id` 把状态写回 `NanobotAgentModel`
- 按 `agent_id` 把事件通过 `AnalystService.broadcast_sse` 推给前端
- 按 `agent_id` 从 `AnalystService.pending_resumes` 等审批决策

使用方式（由 `AnalystService.run_analysis` 在 await `bot.run(...)` 外层统一管理）::

    token_agent = current_agent_id.set(agent_id)
    token_session = current_session_id.set(session_id)
    try:
        await bot.run(...)
    finally:
        current_session_id.reset(token_session)
        current_agent_id.reset(token_agent)
"""
from __future__ import annotations

from contextvars import ContextVar
from typing import Any

current_agent_id: ContextVar[str | None] = ContextVar("current_agent_id", default=None)
current_session_id: ContextVar[str | None] = ContextVar("current_session_id", default=None)
current_run_id: ContextVar[str | None] = ContextVar("current_run_id", default=None)
current_run_worker_id: ContextVar[str | None] = ContextVar(
    "current_run_worker_id", default=None
)
current_run_lease_token: ContextVar[str | None] = ContextVar(
    "current_run_lease_token", default=None
)
current_initiator_user_id: ContextVar[str | None] = ContextVar(
    "current_initiator_user_id", default=None
)
current_task_completion: ContextVar[dict[str, Any] | None] = ContextVar(
    "current_task_completion", default=None
)
current_auto_approve_hitl: ContextVar[bool] = ContextVar(
    "current_auto_approve_hitl", default=False
)


def get_current_agent_id() -> str | None:
    """读取当前协程上下文中的 agent_id（未绑定时返回 None）。"""
    return current_agent_id.get()


def get_current_session_id() -> str | None:
    """读取当前协程上下文中的 session_id（未绑定时返回 None）。"""
    return current_session_id.get()


def get_current_run_id() -> str | None:
    """读取当前协程绑定的持久化 Run ID。"""
    return current_run_id.get()


def get_current_run_worker_id() -> str | None:
    """读取当前 Run 的 Worker ID。"""
    return current_run_worker_id.get()


def get_current_run_lease_token() -> str | None:
    """读取当前 Run 的 fencing lease token。"""
    return current_run_lease_token.get()


def get_current_initiator_user_id() -> str | None:
    """读取当前 Run 的发起用户 ID。"""
    return current_initiator_user_id.get()


def get_current_task_completion() -> dict[str, Any] | None:
    """读取当前 run 内最后一次 `submit_task_result` 写入的快照（权威列表见 session.task_submissions）。"""
    return current_task_completion.get()


def get_current_auto_approve_hitl() -> bool:
    """读取当前 run 是否开启 HITL 自动批准（由 /agent/start 或 /agent/message 的 auto_approve 设置）。"""
    return current_auto_approve_hitl.get()
