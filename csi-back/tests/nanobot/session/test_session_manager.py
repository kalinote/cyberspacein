"""MIGRATION_PLAN §12.6：SessionManager（async 协调层）单测（纯 mock）。"""

from __future__ import annotations

import uuid
from typing import Any

import pytest
from pymongo.errors import DuplicateKeyError

from app.service.nanobot.session.manager import Session, SessionManager


class FakeCachedSessionStore:
    """内存 SessionStore：具备缓存语义 + 可选的冲突注入。"""

    def __init__(self) -> None:
        self._cache: dict[str, Session] = {}
        self._persisted: dict[str, Session] = {}
        self.raise_on_save_ids: set[str] = set()

    async def load(self, session_id: str) -> Session | None:
        cached = self._cache.get(session_id)
        if cached is not None:
            return cached
        sess = self._persisted.get(session_id)
        if sess is None:
            return None
        self._cache[session_id] = sess
        return sess

    async def save(self, session: Session) -> None:
        if session.id in self.raise_on_save_ids:
            raise DuplicateKeyError("duplicate key")
        # 模拟 mongo store：upsert 元数据 + 原地 messages 增量写回（这里不做 seq 分配）
        self._persisted[session.id] = session
        self._cache[session.id] = session

    async def list_by_agent(self, agent_id: str, limit: int = 20) -> list[dict[str, Any]]:
        rows = [s for s in self._persisted.values() if s.agent_id == agent_id]
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
                    "last_consolidated_seq": s.last_consolidated,
                }
            )
        return out

    async def invalidate(self, session_id: str) -> None:
        self._cache.pop(session_id, None)


@pytest.mark.asyncio
async def test_manager_create_assigns_uuid() -> None:
    store = FakeCachedSessionStore()
    mgr = SessionManager(store)

    sess = await mgr.create(agent_id="a1", workspace_id="w1")
    # uuid4.hex 长度 32
    assert isinstance(sess.id, str) and len(sess.id) == 32
    # 可解析为 uuid
    uuid.UUID(hex=sess.id)
    assert sess.metadata == {}


@pytest.mark.asyncio
async def test_manager_create_custom_id() -> None:
    store = FakeCachedSessionStore()
    mgr = SessionManager(store)

    sess = await mgr.create(agent_id="a1", workspace_id="w1", session_id="fixed")
    assert sess.id == "fixed"


@pytest.mark.asyncio
async def test_manager_create_conflict() -> None:
    store = FakeCachedSessionStore()
    mgr = SessionManager(store)

    store.raise_on_save_ids.add("fixed")
    with pytest.raises(DuplicateKeyError):
        await mgr.create(agent_id="a1", workspace_id="w1", session_id="fixed")


@pytest.mark.asyncio
async def test_manager_load_after_create_hits_store_cache() -> None:
    store = FakeCachedSessionStore()
    mgr = SessionManager(store)

    created = await mgr.create(agent_id="a1", workspace_id="w1", session_id="s1")
    loaded1 = await mgr.load("s1")
    loaded2 = await mgr.load("s1")
    assert loaded1 is created
    assert loaded2 is created


@pytest.mark.asyncio
async def test_manager_load_missing() -> None:
    store = FakeCachedSessionStore()
    mgr = SessionManager(store)
    assert await mgr.load("not_exist") is None


@pytest.mark.asyncio
async def test_manager_save_incremental() -> None:
    store = FakeCachedSessionStore()
    mgr = SessionManager(store)

    sess = await mgr.create(agent_id="a1", workspace_id="w1", session_id="s1")
    sess.add_message("user", "u1")
    await mgr.save(sess)
    sess.add_message("assistant", "a1")
    await mgr.save(sess)

    loaded = await mgr.load("s1")
    assert loaded is not None
    assert [m["content"] for m in loaded.messages] == ["u1", "a1"]


@pytest.mark.asyncio
async def test_manager_list_by_agent_and_limit() -> None:
    store = FakeCachedSessionStore()
    mgr = SessionManager(store)

    await mgr.create(agent_id="a1", workspace_id="w1", session_id="s1")
    await mgr.create(agent_id="a1", workspace_id="w1", session_id="s2")
    await mgr.create(agent_id="a1", workspace_id="w1", session_id="s3")

    rows = await mgr.list_by_agent("a1", limit=2)
    assert [r["id"] for r in rows] == ["s3", "s2"]


@pytest.mark.asyncio
async def test_manager_invalidate_causes_reload_new_object() -> None:
    store = FakeCachedSessionStore()
    mgr = SessionManager(store)

    sess = await mgr.create(agent_id="a1", workspace_id="w1", session_id="s1")
    sess.add_message("user", "u1")
    await mgr.save(sess)

    loaded1 = await mgr.load("s1")
    assert loaded1 is sess

    await mgr.invalidate("s1")
    # 模拟“重新从 DB 构造”：把 persisted 替换成一个等价但不同对象
    clone = Session(
        id=sess.id,
        agent_id=sess.agent_id,
        workspace_id=sess.workspace_id,
        messages=list(sess.messages),
        metadata=dict(sess.metadata),
        created_at=sess.created_at,
        updated_at=sess.updated_at,
        last_consolidated=sess.last_consolidated,
    )
    store._persisted["s1"] = clone
    loaded2 = await mgr.load("s1")
    assert loaded2 is clone
    assert loaded2 is not loaded1
    assert [m["content"] for m in loaded2.messages] == ["u1"]


@pytest.mark.asyncio
async def test_manager_agent_isolation() -> None:
    store = FakeCachedSessionStore()
    mgr = SessionManager(store)

    await mgr.create(agent_id="a1", workspace_id="w", session_id="s1")
    await mgr.create(agent_id="a2", workspace_id="w", session_id="s2")

    rows1 = await mgr.list_by_agent("a1")
    rows2 = await mgr.list_by_agent("a2")
    assert [r["id"] for r in rows1] == ["s1"]
    assert [r["id"] for r in rows2] == ["s2"]

