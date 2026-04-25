from __future__ import annotations

from datetime import datetime
from typing import Any

from beanie import Document
from pydantic import Field
from pymongo import ASCENDING, IndexModel


class NanobotAgentSseEventStateModel(Document):
    """SSE 事件序号状态：用于原子分配 (agent_id, session_id) 维度的递增 seq。"""

    id: str = Field(alias="_id", description="状态ID（建议为 agent_id:session_id）")
    last_seq: int = Field(default=0, description="已分配的最大 seq")
    updated_at: datetime = Field(default_factory=datetime.now, description="更新时间")

    class Settings:
        name = "nanobot_agent_sse_event_state"
        indexes = [
            "updated_at",
        ]


class NanobotAgentSseEventModel(Document):
    """Agent SSE 事件日志：用于订阅时回放历史事件流。"""

    agent_id: str = Field(description="AgentID")
    session_id: str = Field(description="会话ID")
    seq: int = Field(description="同一 (agent_id, session_id) 下递增序号")

    event: str = Field(description="SSE event 字段")
    data: Any = Field(description="SSE data 字段（JSON 可序列化对象）")

    is_debug: bool = Field(default=False, description="是否为调试事件（仅 debug 订阅者可见）")
    compressed: bool = Field(
        default=False, description="是否为合并后的流式块（例如 stream delta 合并）"
    )

    created_at: datetime = Field(default_factory=datetime.now, description="创建时间")

    class Settings:
        name = "nanobot_agent_sse_events"
        indexes = [
            IndexModel([("agent_id", ASCENDING), ("session_id", ASCENDING), ("seq", ASCENDING)], unique=True),
            IndexModel([("created_at", ASCENDING)], expireAfterSeconds=60 * 60 * 24),
        ]


__all__ = [
    "NanobotAgentSseEventModel",
    "NanobotAgentSseEventStateModel",
]

