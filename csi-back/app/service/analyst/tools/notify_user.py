"""notify_user 业务工具。"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from app.service.analyst.context import get_current_session_id
from app.service.analyst.tools._context import require_agent_id
from app.service.nanobot.agent.tools.base import Tool, tool_parameters


@tool_parameters({
    "type": "object",
    "properties": {
        "message": {
            "type": "string",
            "description": "通知内容（将通过 SSE 广播给前端）",
            "minLength": 1,
        },
        "level": {
            "type": "string",
            "enum": ["info", "warning", "error"],
            "description": "通知级别",
        },
    },
    "required": ["message"],
    "additionalProperties": False,
})
class NotifyUserTool(Tool):
    """通过 SSE 给前端推一条 `notification` 事件。"""

    @property
    def name(self) -> str:
        return "notify_user"

    @property
    def description(self) -> str:
        return "向用户推送一条实时通知消息。"

    async def execute(self, **kwargs: Any) -> str:
        from app.service.analyst.service import AnalystService

        agent_id = require_agent_id()
        message = str(kwargs.get("message") or "").strip()
        level = kwargs.get("level") or "info"
        if not message:
            return "[错误] message 不能为空"
        await AnalystService.broadcast_sse(
            agent_id,
            "notification",
            {
                "agent_id": agent_id,
                "session_id": get_current_session_id(),
                "level": level,
                "message": message,
                "created_at": datetime.now().isoformat(),
            },
        )
        return "通知已发送"
