"""MIGRATION_PLAN §12.4：MongoMemoryBackend 行为回归测试（纯 mock）。

约束：不连接 MongoDB，不做任何真实数据库 CURD。
"""

from __future__ import annotations

import asyncio
from datetime import datetime
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.schemas.constants import NanobotMemoryDocTypeEnum
from app.service.nanobot.storage.mongo_memory import MongoMemoryBackend


@pytest.fixture
def backend_mocks(monkeypatch: pytest.MonkeyPatch) -> dict[str, Any]:
    import app.service.nanobot.storage.mongo_memory as mongo_memory_mod

    # -------------------------
    # NanobotMemoryDocsModel
    # -------------------------
    memory_find_one = AsyncMock(return_value=None)
    memory_insert = AsyncMock()

    class _FakeMemoryDoc:
        def __init__(self, **kwargs: Any) -> None:
            for k, v in kwargs.items():
                setattr(self, k, v)
            self.save = AsyncMock()

        async def insert(self) -> None:
            await memory_insert()

    class _FakeNanobotMemoryDocsModel:
        def __init__(self, **kwargs: Any) -> None:
            self._doc = _FakeMemoryDoc(**kwargs)

        async def insert(self) -> None:
            await self._doc.insert()

        @staticmethod
        async def find_one(query: dict[str, Any]) -> Any:
            return await memory_find_one(query)

    # -------------------------
    # NanobotHistoryStateModel
    # -------------------------
    state_find_one = AsyncMock(return_value=None)
    state_insert = AsyncMock()

    state_collection = MagicMock()
    state_collection.find_one_and_update = AsyncMock(return_value={"_id": "ws", "last_cursor": 1})

    class _FakeState:
        def __init__(self, **kwargs: Any) -> None:
            for k, v in kwargs.items():
                setattr(self, k, v)
            self.save = AsyncMock()

        async def insert(self) -> None:
            await state_insert()

    class _FakeNanobotHistoryStateModel:
        def __init__(self, **kwargs: Any) -> None:
            self._doc = _FakeState(**kwargs)

        async def insert(self) -> None:
            await self._doc.insert()

        @staticmethod
        async def find_one(query: dict[str, Any]) -> Any:
            return await state_find_one(query)

        @staticmethod
        def get_pymongo_collection() -> Any:
            return state_collection

    # -------------------------
    # NanobotHistoryModel
    # -------------------------
    history_insert = AsyncMock()
    history_delete_many = AsyncMock(return_value=MagicMock(deleted_count=0))
    history_collection = MagicMock(delete_many=history_delete_many)

    history_find_count = AsyncMock(return_value=0)

    class _FakeHistoryDoc:
        def __init__(self, cursor: int, content: str, created_at: datetime) -> None:
            self.cursor = cursor
            self.content = content
            self.created_at = created_at

    class _Query:
        def __init__(self, docs: list[Any]) -> None:
            self._docs = docs
            self._limit: int | None = None

        def sort(self, _expr: str) -> "_Query":
            return self

        def limit(self, n: int) -> "_Query":
            self._limit = n
            return self

        async def to_list(self) -> list[Any]:
            return self._docs[: self._limit] if self._limit is not None else list(self._docs)

        async def count(self) -> int:
            return await history_find_count()

    class _FakeNanobotHistoryModel:
        def __init__(self, **kwargs: Any) -> None:
            self._doc = _FakeHistoryDoc(
                cursor=kwargs["cursor"],
                content=kwargs["content"],
                created_at=kwargs["created_at"],
            )

        async def insert(self) -> None:
            await history_insert()

        @staticmethod
        def find(query: dict[str, Any]) -> Any:
            # compact/read_history 时会在用例里 monkeypatch 下面的 docs
            docs = getattr(_FakeNanobotHistoryModel, "_docs", [])
            return _Query(docs)

        @staticmethod
        def get_pymongo_collection() -> Any:
            return history_collection

    monkeypatch.setattr(mongo_memory_mod, "NanobotMemoryDocsModel", _FakeNanobotMemoryDocsModel)
    monkeypatch.setattr(mongo_memory_mod, "NanobotHistoryStateModel", _FakeNanobotHistoryStateModel)
    monkeypatch.setattr(mongo_memory_mod, "NanobotHistoryModel", _FakeNanobotHistoryModel)

    return {
        "memory_find_one": memory_find_one,
        "memory_insert": memory_insert,
        "state_find_one": state_find_one,
        "state_insert": state_insert,
        "state_collection": state_collection,
        "history_insert": history_insert,
        "history_find_count": history_find_count,
        "history_collection": history_collection,
        "history_delete_many": history_delete_many,
        "HistoryModel": _FakeNanobotHistoryModel,
    }


@pytest.mark.asyncio
async def test_read_doc_default_empty(backend_mocks: dict[str, Any]) -> None:
    backend = MongoMemoryBackend()
    backend_mocks["memory_find_one"].return_value = None
    got = await backend.read_doc("ws1", "memory")
    assert got == ""


@pytest.mark.asyncio
async def test_write_doc_upsert_insert_then_update(backend_mocks: dict[str, Any]) -> None:
    backend = MongoMemoryBackend()

    # insert 分支
    backend_mocks["memory_find_one"].return_value = None
    await backend.write_doc("ws1", "memory", "v1")
    assert backend_mocks["memory_insert"].await_count == 1

    # update 分支（返回已有 doc）
    existing = MagicMock()
    existing.content = "old"
    existing.updated_at = datetime(2026, 1, 1)
    existing.save = AsyncMock()
    backend_mocks["memory_find_one"].return_value = existing
    await backend.write_doc("ws1", "memory", "v2")
    assert existing.content == "v2"
    assert existing.save.await_count == 1


@pytest.mark.asyncio
async def test_append_history_cursor_increment_and_state_autocreate(backend_mocks: dict[str, Any]) -> None:
    backend = MongoMemoryBackend()
    backend_mocks["state_collection"].find_one_and_update = AsyncMock(
        return_value={"_id": "ws1", "last_cursor": 9}
    )
    cur = await backend.append_history("ws1", "hello")
    assert cur == 9
    assert backend_mocks["history_insert"].await_count == 1


@pytest.mark.asyncio
async def test_read_history_filter_limit_and_order(backend_mocks: dict[str, Any]) -> None:
    backend = MongoMemoryBackend()
    now = datetime.now()
    backend_mocks["HistoryModel"]._docs = [
        MagicMock(cursor=2, content="b", created_at=now),
        MagicMock(cursor=3, content="c", created_at=now),
    ]
    rows = await backend.read_history("ws1", since_cursor=1, limit=1)
    assert rows == [{"cursor": 2, "content": "b", "created_at": now}]


@pytest.mark.asyncio
async def test_compact_history_under_limit_returns_0(backend_mocks: dict[str, Any]) -> None:
    backend = MongoMemoryBackend()
    backend_mocks["history_find_count"].return_value = 5
    deleted = await backend.compact_history("ws1", max_entries=10)
    assert deleted == 0


@pytest.mark.asyncio
async def test_compact_history_over_limit_deletes_oldest_by_cutoff(backend_mocks: dict[str, Any]) -> None:
    backend = MongoMemoryBackend()
    backend_mocks["history_find_count"].return_value = 20
    # oldest query 会 limit(to_delete=10)，取最后一个 cursor 作为 cutoff
    oldest = [MagicMock(cursor=i) for i in range(1, 11)]
    backend_mocks["HistoryModel"]._docs = oldest
    backend_mocks["history_delete_many"].return_value = MagicMock(deleted_count=10)

    deleted = await backend.compact_history("ws1", max_entries=10)
    assert deleted == 10
    backend_mocks["history_delete_many"].assert_awaited()
    query = backend_mocks["history_delete_many"].await_args.args[0]
    assert query["workspace_id"] == "ws1"
    assert query["cursor"]["$lte"] == 10


@pytest.mark.asyncio
async def test_get_cursors_default_when_missing_state(backend_mocks: dict[str, Any]) -> None:
    backend = MongoMemoryBackend()
    backend_mocks["state_find_one"].return_value = None
    assert await backend.get_cursors("ws1") == (0, 0)


@pytest.mark.asyncio
async def test_set_dream_cursor_insert_or_update(backend_mocks: dict[str, Any]) -> None:
    backend = MongoMemoryBackend()

    # insert 分支
    backend_mocks["state_find_one"].return_value = None
    await backend.set_dream_cursor("ws1", 7)
    assert backend_mocks["state_insert"].await_count == 1

    # update 分支
    existing = MagicMock()
    existing.last_dream_cursor = 0
    existing.updated_at = datetime(2026, 1, 1)
    existing.save = AsyncMock()
    backend_mocks["state_find_one"].return_value = existing
    await backend.set_dream_cursor("ws1", 8)
    assert existing.last_dream_cursor == 8
    assert existing.save.await_count == 1

