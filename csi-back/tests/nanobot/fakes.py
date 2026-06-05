"""nanobot 单测用内存 fake：MemoryBackend / SessionStore。"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from app.service.nanobot.agent.memory import MemoryStore
from app.service.nanobot.session.manager import Session, SessionManager


class FakeMemoryBackend:
    """满足 MemoryBackend 协议的最小内存实现。"""

    def __init__(self) -> None:
        self._docs: dict[tuple[str, str], str] = {}
        self._history: list[dict[str, Any]] = []
        self._last_cursor: dict[str, int] = {}
        self._dream_cursor: dict[str, int] = {}

    async def read_doc(self, workspace_id: str, doc_type: str) -> str:
        return self._docs.get((workspace_id, doc_type), "")

    async def write_doc(self, workspace_id: str, doc_type: str, content: str) -> None:
        self._docs[(workspace_id, doc_type)] = content

    async def append_history(self, workspace_id: str, entry: str) -> int:
        cur = self._last_cursor.get(workspace_id, 0) + 1
        self._last_cursor[workspace_id] = cur
        self._history.append(
            {
                "workspace_id": workspace_id,
                "cursor": cur,
                "content": entry,
                "created_at": datetime.now(),
            }
        )
        return cur

    async def read_history(
        self,
        workspace_id: str,
        since_cursor: int = 0,
        limit: int | None = None,
    ) -> list[dict[str, Any]]:
        rows = [
            h
            for h in self._history
            if h["workspace_id"] == workspace_id and h["cursor"] > since_cursor
        ]
        rows.sort(key=lambda h: h["cursor"])
        if limit is not None:
            rows = rows[:limit]
        return rows

    async def compact_history(self, workspace_id: str, max_entries: int) -> int:
        return 0

    async def get_cursors(self, workspace_id: str) -> tuple[int, int]:
        return (
            self._last_cursor.get(workspace_id, 0),
            self._dream_cursor.get(workspace_id, 0),
        )

    async def set_dream_cursor(self, workspace_id: str, cursor: int) -> None:
        self._dream_cursor[workspace_id] = cursor


class FakeSessionStore:
    """满足 SessionStore 协议的最小内存实现。"""

    def __init__(self) -> None:
        self._sessions: dict[str, Session] = {}

    async def load(self, session_id: str) -> Session | None:
        return self._sessions.get(session_id)

    async def save(self, session: Session) -> None:
        self._sessions[session.id] = session

    async def list_by_agent(self, agent_id: str, limit: int = 20) -> list[dict[str, Any]]:
        rows = [s for s in self._sessions.values() if s.agent_id == agent_id]
        rows.sort(key=lambda s: s.created_at, reverse=True)
        out: list[dict[str, Any]] = []
        for s in rows[:limit]:
            out.append(
                {
                    "id": s.id,
                    "agent_id": s.agent_id,
                    "workspace_id": s.workspace_id,
                    "created_at": s.created_at,
                    "updated_at": s.updated_at,
                    "metadata": s.metadata,
                }
            )
        return out

    async def invalidate(self, session_id: str) -> None:
        self._sessions.pop(session_id, None)


def make_memory_store(workspace_id: str = "ws_test") -> MemoryStore:
    return MemoryStore(FakeMemoryBackend(), workspace_id=workspace_id)


def make_session_manager() -> SessionManager:
    return SessionManager(FakeSessionStore())
