"""get_current_time 业务工具。"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from app.service.nanobot.agent.tools.base import Tool, tool_parameters


@tool_parameters({
    "type": "object",
    "properties": {},
    "additionalProperties": False,
})
class GetCurrentTimeTool(Tool):
    """返回当前服务器时间（ISO 8601），便于 LLM 进行时间推理。"""

    @property
    def name(self) -> str:
        return "get_current_time"

    @property
    def description(self) -> str:
        return "获取当前服务器时间（ISO 8601 字符串）。"

    @property
    def read_only(self) -> bool:
        return True

    async def execute(self, **kwargs: Any) -> str:
        return datetime.now().isoformat()
