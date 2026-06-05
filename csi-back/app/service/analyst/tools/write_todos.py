"""write_todos 业务工具。"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from app.models.agent.nanobot import NanobotSessionModel
from app.service.analyst.context import get_current_session_id
from app.service.analyst.tools._context import require_agent_id
from app.service.nanobot.agent.tools.base import Tool, tool_parameters


def _normalize_todo(item: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": str(item.get("id") or ""),
        "content": str(item.get("content") or "").strip(),
        "status": str(item.get("status") or "pending"),
        "updated_at": datetime.now().isoformat(),
    }


@tool_parameters({
    "type": "object",
    "properties": {
        "todos": {
            "type": "array",
            "description": "任务项列表，完整覆盖当前会话 todos",
            "items": {
                "type": "object",
                "properties": {
                    "content": {"type": "string", "minLength": 1},
                    "status": {
                        "type": "string",
                        "enum": ["pending", "in_progress", "completed", "cancelled"],
                    },
                    "id": {"type": "string"},
                },
                "required": ["content", "status"],
                "additionalProperties": True,
            },
            "minItems": 0,
        },
    },
    "required": ["todos"],
    "additionalProperties": False,
})
class WriteTodosTool(Tool):
    """写入当前会话的 todos 列表（完整覆盖），并 SSE 广播给前端。"""

    @property
    def name(self) -> str:
        return "write_todos"

    @property
    def description(self) -> str:
        return "更新当前会话的待办事项列表（会完全覆盖旧列表）。"

    @property
    def exclusive(self) -> bool:
        return True

    async def execute(self, **kwargs: Any) -> str:
        from app.service.analyst.service import AnalystService

        agent_id = require_agent_id()
        sid = get_current_session_id()
        if not sid:
            return "[错误] 缺少 session 上下文"
        todos = kwargs.get("todos") or []
        normalized = [_normalize_todo(item) for item in todos]

        session = await NanobotSessionModel.find_one({"_id": sid})
        if session is None:
            return f"[错误] 当前会话不存在: {sid}"
        session.todos = normalized
        session.updated_at = datetime.now()
        await session.save()

        await AnalystService.broadcast_sse(
            agent_id,
            "todos",
            {
                "agent_id": agent_id,
                "session_id": sid,
                "todos": normalized,
            },
        )
        return f"已更新待办 {len(normalized)} 条"
