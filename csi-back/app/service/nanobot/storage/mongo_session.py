"""SessionStore 的 MongoDB 实现

集合对应关系：
  - nanobot_sessions          ↔ NanobotSessionModel
  - nanobot_session_messages  ↔ NanobotSessionMessagesModel

写入策略：
  - session 元数据采用 upsert 语义，每次 save 覆盖 metadata / updated_at / last_consolidated_seq；
  - session.messages 采用**增量 append**：已带 seq 的 message 视作已落库，不重复写；
    无 seq 的 message 依次分配递增的 seq 后一次性 insert_many，并原地写回 seq。
"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Any

from loguru import logger

from app.models.agent.nanobot import (
    NanobotSessionMessagesModel,
    NanobotSessionModel,
)
from app.schemas.constants import NanobotMessageRoleEnum

if TYPE_CHECKING:
    from app.service.nanobot.session.manager import Session


logger = logger.bind(name=__name__)


class MongoSessionStore:
    """SessionStore 的 MongoDB 实现"""

    def __init__(self) -> None:
        # 进程内 session 缓存，key = session_id
        self._cache: dict[str, "Session"] = {}

    async def load(self, session_id: str) -> "Session | None":
        # 先命中进程内缓存，保证同一个 session 在进程内被共享（messages 原地写回语义依赖此）
        cached = self._cache.get(session_id)
        if cached is not None:
            return cached

        meta = await NanobotSessionModel.find_one({"_id": session_id})
        if meta is None:
            return None

        msg_docs = (
            await NanobotSessionMessagesModel
            .find({"session_id": session_id})
            .sort("+seq")
            .to_list()
        )

        messages: list[dict[str, Any]] = []
        for m in msg_docs:
            msg: dict[str, Any] = {
                "seq": m.seq,
                "role": m.role.value if hasattr(m.role, "value") else m.role,
                "content": m.content,
                "timestamp": m.created_at.isoformat(),
            }
            if m.sender_id is not None:
                msg["sender_id"] = m.sender_id
            if m.injected_event is not None:
                msg["injected_event"] = m.injected_event
            if m.subagent_task_id is not None:
                msg["subagent_task_id"] = m.subagent_task_id
            if m.tool_calls:
                msg["tool_calls"] = m.tool_calls
            if m.reasoning_content is not None:
                msg["reasoning_content"] = m.reasoning_content
            if m.thinking_blocks:
                msg["thinking_blocks"] = m.thinking_blocks
            if m.tool_call_id is not None:
                msg["tool_call_id"] = m.tool_call_id
            if m.tool_call_name is not None:
                msg["tool_call_name"] = m.tool_call_name
            messages.append(msg)

        # 延迟 import 避免与 session/manager.py 形成循环依赖
        from app.service.nanobot.session.manager import Session

        session = Session(
            id=meta.id,
            agent_id=meta.agent_id,
            workspace_id=meta.workspace_id,
            messages=messages,
            created_at=meta.created_at,
            updated_at=meta.updated_at,
            metadata=dict(meta.metadata or {}),
            last_consolidated=meta.last_consolidated_seq,
        )
        self._cache[session_id] = session
        return session

    async def save(self, session: "Session") -> None:
        now = datetime.now()
        session.updated_at = now

        # 1) upsert 元数据
        existing = await NanobotSessionModel.find_one({"_id": session.id})
        if existing is None:
            await NanobotSessionModel(
                id=session.id,
                agent_id=session.agent_id,
                workspace_id=session.workspace_id,
                metadata=session.metadata,
                last_consolidated_seq=session.last_consolidated,
                created_at=session.created_at,
                updated_at=now,
            ).insert()
        else:
            existing.metadata = session.metadata
            existing.last_consolidated_seq = session.last_consolidated
            existing.updated_at = now
            await existing.save()

        # 2) 增量 append 消息
        pending = [m for m in session.messages if "seq" not in m]
        if not pending:
            self._cache[session.id] = session
            return

        # 查询当前 max(seq) 作为起始点
        latest = (
            await NanobotSessionMessagesModel
            .find({"session_id": session.id})
            .sort("-seq")
            .limit(1)
            .to_list()
        )
        current_max = latest[0].seq if latest else 0

        docs: list[NanobotSessionMessagesModel] = []
        for offset, msg in enumerate(pending, start=1):
            seq = current_max + offset
            msg["seq"] = seq  # 原地写回，下次 save 时不会被重复插入

            role_raw = msg.get("role", "user")
            role = (
                role_raw
                if isinstance(role_raw, NanobotMessageRoleEnum)
                else NanobotMessageRoleEnum(role_raw)
            )

            docs.append(
                NanobotSessionMessagesModel(
                    session_id=session.id,
                    seq=seq,
                    role=role,
                    content=msg.get("content", ""),
                    sender_id=msg.get("sender_id"),
                    injected_event=msg.get("injected_event"),
                    subagent_task_id=msg.get("subagent_task_id"),
                    tool_calls=msg.get("tool_calls") or [],
                    reasoning_content=msg.get("reasoning_content"),
                    thinking_blocks=msg.get("thinking_blocks") or [],
                    tool_call_id=msg.get("tool_call_id"),
                    tool_call_name=msg.get("tool_call_name"),
                )
            )

        await NanobotSessionMessagesModel.insert_many(docs)
        logger.debug(
            "session {} 新增 {} 条消息 (seq {}..{})",
            session.id,
            len(docs),
            current_max + 1,
            current_max + len(docs),
        )
        self._cache[session.id] = session

    async def list_by_agent(
        self, agent_id: str, limit: int = 20
    ) -> list[dict[str, Any]]:
        docs = (
            await NanobotSessionModel
            .find({"agent_id": agent_id})
            .sort("-created_at")
            .limit(limit)
            .to_list()
        )
        return [
            {
                "id": d.id,
                "agent_id": d.agent_id,
                "workspace_id": d.workspace_id,
                "created_at": d.created_at,
                "updated_at": d.updated_at,
                "last_consolidated_seq": d.last_consolidated_seq,
            }
            for d in docs
        ]

    async def invalidate(self, session_id: str) -> None:
        self._cache.pop(session_id, None)
