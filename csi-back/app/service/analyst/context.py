"""ContextVar 绑定：在一次 `run_analysis` 协程内把 `agent_id / session_id` 暴露给业务工具。

业务工具（`modify_entity / notify_user / write_todos` 等，TODO #20）通过这些 ContextVar
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

current_agent_id: ContextVar[str | None] = ContextVar("current_agent_id", default=None)
current_session_id: ContextVar[str | None] = ContextVar("current_session_id", default=None)


def get_current_agent_id() -> str | None:
    """读取当前协程上下文中的 agent_id（未绑定时返回 None）。"""
    return current_agent_id.get()


def get_current_session_id() -> str | None:
    """读取当前协程上下文中的 session_id（未绑定时返回 None）。"""
    return current_session_id.get()
