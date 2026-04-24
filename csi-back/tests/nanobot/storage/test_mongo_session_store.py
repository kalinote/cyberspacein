"""MIGRATION_PLAN §12.3：MongoSessionStore 行为回归测试（纯 mock）。

约束：
- 不连接 MongoDB，不做任何真实数据库 CURD。
- 仅验证：元数据 upsert 分支、消息 seq 分配/增量 append、字段映射、缓存行为。
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta
from typing import Any

import pytest
from unittest.mock import AsyncMock, MagicMock

from app.schemas.constants import NanobotMessageRoleEnum
from app.service.nanobot.session.manager import Session
from app.service.nanobot.storage.mongo_session import MongoSessionStore


@pytest.fixture
def store_mocks(monkeypatch: pytest.MonkeyPatch) -> dict[str, Any]:
    """把 MongoSessionStore 所依赖的 Beanie 调用全部替换为 mock。"""

    import app.service.nanobot.storage.mongo_session as mongo_session_mod

    # --- NanobotSessionModel（在 mongo_session 模块内打桩） ---
    nanobot_session_find_one = AsyncMock(return_value=None)
    nanobot_session_insert = AsyncMock()

    class _FakeNanobotSessionModel:
        def __init__(self, **kwargs: Any) -> None:
            for k, v in kwargs.items():
                setattr(self, k, v)

        async def insert(self) -> None:
            await nanobot_session_insert()

        @staticmethod
        async def find_one(query: dict[str, Any]) -> Any:
            return await nanobot_session_find_one(query)

        @staticmethod
        def find(query: dict[str, Any]) -> Any:
            # 测试用：由用例在运行时 monkeypatch 这个方法
            raise NotImplementedError

    nanobot_session_existing = MagicMock()
    nanobot_session_existing.save = AsyncMock()

    monkeypatch.setattr(mongo_session_mod, "NanobotSessionModel", _FakeNanobotSessionModel)

    # --- NanobotSessionMessagesModel（在 mongo_session 模块内打桩） ---
    latest_docs = AsyncMock(return_value=[])
    by_session_docs = AsyncMock(return_value=[])

    class _Query:
        def __init__(self) -> None:
            self._sort: str | None = None

        def sort(self, expr: str) -> "_Query":
            self._sort = expr
            return self

        def limit(self, _n: int) -> "_Query":
            return self

        async def to_list(self) -> list[Any]:
            # save(): sort("-seq") 走 latest；load(): sort("+seq") 走 by_session
            if self._sort and self._sort.startswith("-"):
                return await latest_docs()
            return await by_session_docs()

    def _messages_find(_query: dict[str, Any]) -> Any:
        return _Query()

    insert_many = AsyncMock()

    class _FakeNanobotSessionMessagesModel:
        def __init__(self, **kwargs: Any) -> None:
            for k, v in kwargs.items():
                setattr(self, k, v)

        @staticmethod
        def find(query: dict[str, Any]) -> Any:
            return _messages_find(query)

        @staticmethod
        async def insert_many(docs: list[Any]) -> None:
            await insert_many(docs)

    monkeypatch.setattr(mongo_session_mod, "NanobotSessionMessagesModel", _FakeNanobotSessionMessagesModel)

    return {
        "nanobot_session_find_one": nanobot_session_find_one,
        "nanobot_session_insert": nanobot_session_insert,
        "nanobot_session_existing": nanobot_session_existing,
        "latest_docs": latest_docs,
        "by_session_docs": by_session_docs,
        "insert_many": insert_many,
    }


def _make_session(
    *,
    session_id: str | None = None,
    agent_id: str = "agent-1",
    workspace_id: str = "ws-1",
    created_at: datetime | None = None,
) -> Session:
    sid = session_id or f"s_{uuid.uuid4().hex[:10]}"
    now = datetime.now()
    return Session(
        id=sid,
        agent_id=agent_id,
        workspace_id=workspace_id,
        created_at=created_at or now,
        updated_at=created_at or now,
        metadata={},
        last_consolidated=0,
    )


@pytest.mark.asyncio
async def test_save_new_session(store_mocks: dict[str, Any]) -> None:
    store = MongoSessionStore()
    session = _make_session()
    session.add_message("user", "你好")
    session.add_message("assistant", "收到", tool_calls=[{"name": "x", "arguments": {}}])
    session.add_message("tool", {"ok": True}, tool_call_id="t1", name="x")

    await store.save(session)

    # 元数据走 insert 分支
    assert store_mocks["nanobot_session_insert"].await_count == 1
    # messages 插入 3 条，seq=1..3
    docs = store_mocks["insert_many"].await_args.args[0]
    assert [d.seq for d in docs] == [1, 2, 3]
    assert [m["seq"] for m in session.messages] == [1, 2, 3]


@pytest.mark.asyncio
async def test_save_incremental_append(store_mocks: dict[str, Any]) -> None:
    store = MongoSessionStore()
    session = _make_session()
    for i in range(3):
        session.add_message("user", f"m{i}")
    await store.save(session)

    # 第二次 save 前，模拟 DB 中已经存在 3 条，latest max(seq)=3
    latest_doc = MagicMock()
    latest_doc.seq = 3
    store_mocks["latest_docs"].return_value = [latest_doc]

    session.add_message("assistant", "a4")
    session.add_message("assistant", "a5")
    await store.save(session)

    # 第二次 insert_many 只应插入 2 条，seq=4..5
    # 注意：insert_many 会被调用两次（第一次 3 条、第二次 2 条）
    assert store_mocks["insert_many"].await_count == 2
    docs2 = store_mocks["insert_many"].await_args_list[1].args[0]
    assert [d.seq for d in docs2] == [4, 5]
    assert [m["seq"] for m in session.messages] == [1, 2, 3, 4, 5]


@pytest.mark.asyncio
async def test_save_inplace_seq(store_mocks: dict[str, Any]) -> None:
    store = MongoSessionStore()
    session = _make_session()
    session.add_message("user", "a")
    session.add_message("assistant", "b")
    await store.save(session)

    assert all("seq" in m for m in session.messages)
    assert [m["seq"] for m in session.messages] == [1, 2]


@pytest.mark.asyncio
async def test_save_meta_overwrite(store_mocks: dict[str, Any]) -> None:
    store = MongoSessionStore()
    session = _make_session()
    session.add_message("user", "x")
    await store.save(session)

    # 第二次 save：元数据应走 update 分支（existing.save）
    store_mocks["nanobot_session_find_one"].return_value = store_mocks["nanobot_session_existing"]

    session.metadata["k"] = "v"
    session.last_consolidated = 7
    await store.save(session)

    existing = store_mocks["nanobot_session_existing"]
    assert existing.metadata == {"k": "v"}
    assert existing.last_consolidated_seq == 7
    assert existing.save.await_count == 1


@pytest.mark.asyncio
async def test_load_existing_restores_optional_fields(store_mocks: dict[str, Any]) -> None:
    store = MongoSessionStore()
    session = _make_session()

    meta = MagicMock()
    meta.id = session.id
    meta.agent_id = session.agent_id
    meta.workspace_id = session.workspace_id
    meta.created_at = session.created_at
    meta.updated_at = session.updated_at
    meta.metadata = {"m": 1}
    meta.last_consolidated_seq = 0
    store_mocks["nanobot_session_find_one"].return_value = meta

    m1 = MagicMock()
    m1.seq = 1
    m1.role = NanobotMessageRoleEnum.ASSISTANT
    m1.content = "hi"
    m1.created_at = datetime.now()
    m1.sender_id = "u1"
    m1.injected_event = "evt"
    m1.subagent_task_id = "sub1"
    m1.tool_calls = [{"name": "tool", "arguments": {"a": 1}}]
    m1.reasoning_content = "rc"
    m1.thinking_blocks = [{"type": "thinking", "text": "t"}]
    m1.tool_call_id = None
    m1.tool_call_name = None

    m2 = MagicMock()
    m2.seq = 2
    m2.role = NanobotMessageRoleEnum.TOOL
    m2.content = "ok"
    m2.created_at = datetime.now()
    m2.sender_id = None
    m2.injected_event = None
    m2.subagent_task_id = None
    m2.tool_calls = []
    m2.reasoning_content = None
    m2.thinking_blocks = []
    m2.tool_call_id = "tc1"
    m2.tool_call_name = "tool"

    store_mocks["by_session_docs"].return_value = [m1, m2]

    loaded = await store.load(session.id)
    assert loaded is not None
    assert [m["seq"] for m in loaded.messages] == [1, 2]
    assert loaded.messages[0]["sender_id"] == "u1"
    assert loaded.messages[0]["injected_event"] == "evt"
    assert loaded.messages[0]["subagent_task_id"] == "sub1"
    assert loaded.messages[0]["tool_calls"][0]["name"] == "tool"
    assert loaded.messages[0]["reasoning_content"] == "rc"
    assert loaded.messages[0]["thinking_blocks"][0]["type"] == "thinking"
    assert loaded.messages[1]["tool_call_id"] == "tc1"
    assert loaded.messages[1]["tool_call_name"] == "tool"


@pytest.mark.asyncio
async def test_load_not_found(store_mocks: dict[str, Any]) -> None:
    store = MongoSessionStore()
    store_mocks["nanobot_session_find_one"].return_value = None
    assert await store.load("not_exist") is None


@pytest.mark.asyncio
async def test_load_roundtrip_save_load_consistent(store_mocks: dict[str, Any]) -> None:
    store = MongoSessionStore()
    session = _make_session()
    session.metadata["a"] = 1
    session.last_consolidated = 2
    session.add_message("user", "u")
    session.add_message("assistant", "a")
    # save 会把 session 放进 cache；load 直接命中 cache
    await store.save(session)
    s1 = await store.load(session.id)
    s2 = await store.load(session.id)
    assert s1 is s2
    assert s2.metadata == {"a": 1}
    assert s2.last_consolidated == 2


@pytest.mark.asyncio
async def test_list_by_agent_order_and_limit(store_mocks: dict[str, Any], monkeypatch: pytest.MonkeyPatch) -> None:
    store = MongoSessionStore()
    base = datetime(2026, 1, 1, 0, 0, 0)
    agent_id = "agent_list"

    s_old = MagicMock(id="s_old", agent_id=agent_id, workspace_id="ws", created_at=base, updated_at=base, last_consolidated_seq=0)
    s_mid = MagicMock(id="s_mid", agent_id=agent_id, workspace_id="ws", created_at=base + timedelta(seconds=1), updated_at=base, last_consolidated_seq=0)
    s_new = MagicMock(id="s_new", agent_id=agent_id, workspace_id="ws", created_at=base + timedelta(seconds=2), updated_at=base, last_consolidated_seq=0)

    q = MagicMock()
    q.sort.return_value = q
    q._limit = None

    def _limit(n: int) -> Any:
        q._limit = n
        return q

    q.limit.side_effect = _limit

    async def _to_list() -> list[Any]:
        rows = [s_new, s_mid, s_old]
        return rows[: q._limit] if q._limit else rows

    q.to_list = AsyncMock(side_effect=_to_list)
    import app.service.nanobot.storage.mongo_session as mongo_session_mod
    monkeypatch.setattr(mongo_session_mod.NanobotSessionModel, "find", MagicMock(return_value=q))

    rows = await store.list_by_agent(agent_id, limit=2)
    assert [r["id"] for r in rows] == ["s_new", "s_mid"]


@pytest.mark.asyncio
async def test_list_by_agent_isolation(monkeypatch: pytest.MonkeyPatch) -> None:
    store = MongoSessionStore()
    q1 = MagicMock()
    q1.sort.return_value = q1
    q1.limit.return_value = q1
    q1.to_list = AsyncMock(return_value=[MagicMock(id="s1", agent_id="a1", workspace_id="ws", created_at=datetime.now(), updated_at=datetime.now(), last_consolidated_seq=0)])
    q2 = MagicMock()
    q2.sort.return_value = q2
    q2.limit.return_value = q2
    q2.to_list = AsyncMock(return_value=[MagicMock(id="s2", agent_id="a2", workspace_id="ws", created_at=datetime.now(), updated_at=datetime.now(), last_consolidated_seq=0)])

    def _find(q: dict[str, Any]) -> Any:
        return q1 if q.get("agent_id") == "a1" else q2

    import app.service.nanobot.storage.mongo_session as mongo_session_mod
    monkeypatch.setattr(mongo_session_mod.NanobotSessionModel, "find", MagicMock(side_effect=_find))
    rows1 = await store.list_by_agent("a1")
    rows2 = await store.list_by_agent("a2")
    assert [r["id"] for r in rows1] == ["s1"]
    assert [r["id"] for r in rows2] == ["s2"]


@pytest.mark.asyncio
async def test_invalidate_cache_only(store_mocks: dict[str, Any]) -> None:
    store = MongoSessionStore()
    session = _make_session()
    session.add_message("user", "x")
    await store.save(session)

    s1 = await store.load(session.id)
    s2 = await store.load(session.id)
    assert s1 is s2  # 命中缓存

    await store.invalidate(session.id)
    # invalidate 后，cache miss，需要依赖 DB load 分支；这里直接让 find_one 返回 None，等价于未落库
    store_mocks["nanobot_session_find_one"].return_value = None
    assert await store.load(session.id) is None


@pytest.mark.asyncio
async def test_save_empty_messages(store_mocks: dict[str, Any]) -> None:
    store = MongoSessionStore()
    session = _make_session()
    await store.save(session)

    assert store_mocks["nanobot_session_insert"].await_count == 1
    assert store_mocks["insert_many"].await_count == 0

