"""会话领域模型 + 协调层。

`Session` 不再承担持久化职责；所有落盘逻辑已迁移到 `storage.SessionStore`
（当前实现为 `MongoSessionStore`）。`SessionManager` 退化为 async 协调层：
负责生成 session_id、调用 SessionStore 的 CRUD，并透出 `Session` 领域对象。
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import TYPE_CHECKING, Any

from app.service.nanobot.utils.helpers import find_legal_message_start

if TYPE_CHECKING:
    from app.service.nanobot.storage.base import SessionStore


@dataclass
class Session:
    """会话领域对象

    - `id`：会话唯一标识，对应 `nanobot_sessions._id`；由 `SessionManager.create()` 生成，
      每次 `/agent/start` 都是一个新 id，不复用。
    - `agent_id`：所属 Agent，一个 Agent 同时最多只能有一个 session 在跑。
    - `workspace_id`：冗余，便于按 workspace 聚合查询、memory 隔离。
    """

    id: str
    agent_id: str
    workspace_id: str
    messages: list[dict[str, Any]] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    metadata: dict[str, Any] = field(default_factory=dict)
    # 已经被 Consolidator 合并进 history 的 message 数量上限
    last_consolidated: int = 0

    def add_message(self, role: str, content: Any, **kwargs: Any) -> None:
        """追加一条消息；seq 不在此处分配，由 SessionStore.save 时统一分配"""
        msg: dict[str, Any] = {
            "role": role,
            "content": content,
            "timestamp": datetime.now().isoformat(),
            **kwargs,
        }
        self.messages.append(msg)
        self.updated_at = datetime.now()

    def get_history(self, max_messages: int = 500) -> list[dict[str, Any]]:
        """返回供 LLM 使用的未合并消息切片，并对齐到合法的工具调用边界"""
        unconsolidated = self.messages[self.last_consolidated:]
        sliced = unconsolidated[-max_messages:]

        for i, message in enumerate(sliced):
            if message.get("role") == "user":
                sliced = sliced[i:]
                break

        start = find_legal_message_start(sliced)
        if start:
            sliced = sliced[start:]

        out: list[dict[str, Any]] = []
        for message in sliced:
            entry: dict[str, Any] = {"role": message["role"], "content": message.get("content", "")}
            for key in ("tool_calls", "tool_call_id", "name", "reasoning_content"):
                if key in message:
                    entry[key] = message[key]
            out.append(entry)
        return out

    def clear(self) -> None:
        """清空 messages（只动内存；DB 中的历史消息不会被删除）"""
        self.messages = []
        self.last_consolidated = 0
        self.updated_at = datetime.now()

    def retain_recent_legal_suffix(self, max_messages: int) -> None:
        """裁剪出近 max_messages 条消息并对齐到合法边界（只动内存）

        注意：DB 侧仍然保留完整历史；下次 load 会重新拉取所有消息，
        裁剪策略仅影响当前进程内的上下文窗口。
        """
        if max_messages <= 0:
            self.clear()
            return
        if len(self.messages) <= max_messages:
            return

        start_idx = max(0, len(self.messages) - max_messages)

        while start_idx > 0 and self.messages[start_idx].get("role") != "user":
            start_idx -= 1

        retained = self.messages[start_idx:]

        start = find_legal_message_start(retained)
        if start:
            retained = retained[start:]

        dropped = len(self.messages) - len(retained)
        self.messages = retained
        self.last_consolidated = max(0, self.last_consolidated - dropped)
        self.updated_at = datetime.now()


class SessionManager:
    """基于 SessionStore 的 session 协调层

    约束：一个 Agent 同一时刻只有一个活跃 session。本类不强制该约束，由上层
    `AnalystService` 在 `/agent/start` 处根据 `NanobotAgentModel.status /
    current_session_id` 判断后决定是否 `create` 新 session。
    """

    def __init__(self, store: SessionStore):
        self.store = store

    async def load(self, session_id: str) -> Session | None:
        """按 session_id 读取；不存在返回 None"""
        return await self.store.load(session_id)

    async def create(
        self,
        *,
        agent_id: str,
        workspace_id: str,
        session_id: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> Session:
        """创建新会话并落库（首次 save 只写元数据，messages 为空）

        session_id 缺省生成 uuid4；外部也可传入指定值（用于测试或会话幂等恢复）。
        """
        sid = session_id or uuid.uuid4().hex
        now = datetime.now()
        session = Session(
            id=sid,
            agent_id=agent_id,
            workspace_id=workspace_id,
            metadata=dict(metadata or {}),
            created_at=now,
            updated_at=now,
        )
        await self.store.save(session)
        return session

    async def save(self, session: Session) -> None:
        """持久化 session：upsert 元数据 + 增量 append 新 messages"""
        await self.store.save(session)

    async def list_by_agent(self, agent_id: str, limit: int = 20) -> list[dict[str, Any]]:
        """按 agent 列出最近的 session 元数据（不含 messages）"""
        return await self.store.list_by_agent(agent_id, limit)

    async def invalidate(self, session_id: str) -> None:
        """从 store 缓存中移除 session（DB 记录保留）"""
        await self.store.invalidate(session_id)
