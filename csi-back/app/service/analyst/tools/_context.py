"""业务工具共用的 ContextVar 校验。"""

from __future__ import annotations

from app.service.analyst.context import get_current_agent_id


def require_agent_id() -> str:
    agent_id = get_current_agent_id()
    if not agent_id:
        raise RuntimeError("业务工具必须在 AnalystService.run_analysis 的 ContextVar 作用域内调用")
    return agent_id
