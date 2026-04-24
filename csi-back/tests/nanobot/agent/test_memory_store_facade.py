"""MIGRATION_PLAN §12.7：MemoryStore（workspace 级记忆门面）单测（纯内存）。"""

from __future__ import annotations

from datetime import datetime
from typing import Any

import pytest

from app.service.nanobot.agent.memory import MemoryStore


class InMemoryBackend:
    """满足 MemoryBackend 的最小内存实现，用于验证 MemoryStore 行为。"""

    def __init__(self) -> None:
        self.docs: dict[tuple[str, str], str] = {}
        self.history: list[dict[str, Any]] = []
        self.last_cursor: dict[str, int] = {}
        self.last_dream_cursor: dict[str, int] = {}
        self.compact_called: int = 0

    async def read_doc(self, workspace_id: str, doc_type: str) -> str:
        return self.docs.get((workspace_id, doc_type), "")

    async def write_doc(self, workspace_id: str, doc_type: str, content: str) -> None:
        self.docs[(workspace_id, doc_type)] = content

    async def append_history(self, workspace_id: str, entry: str) -> int:
        cur = self.last_cursor.get(workspace_id, 0) + 1
        self.last_cursor[workspace_id] = cur
        self.history.append(
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
            {"cursor": h["cursor"], "content": h["content"], "created_at": h["created_at"]}
            for h in self.history
            if h["workspace_id"] == workspace_id and h["cursor"] > since_cursor
        ]
        rows.sort(key=lambda r: r["cursor"])
        if limit is not None:
            rows = rows[:limit]
        return rows

    async def compact_history(self, workspace_id: str, max_entries: int) -> int:
        self.compact_called += 1
        rows = [h for h in self.history if h["workspace_id"] == workspace_id]
        rows.sort(key=lambda r: r["cursor"])
        if len(rows) <= max_entries:
            return 0
        to_delete = len(rows) - max_entries
        cutoff = rows[to_delete - 1]["cursor"]
        before = len(self.history)
        self.history = [
            h
            for h in self.history
            if not (h["workspace_id"] == workspace_id and h["cursor"] <= cutoff)
        ]
        return before - len(self.history)

    async def get_cursors(self, workspace_id: str) -> tuple[int, int]:
        return (self.last_cursor.get(workspace_id, 0), self.last_dream_cursor.get(workspace_id, 0))

    async def set_dream_cursor(self, workspace_id: str, cursor: int) -> None:
        self.last_dream_cursor[workspace_id] = cursor


@pytest.mark.asyncio
async def test_memory_roundtrip() -> None:
    backend = InMemoryBackend()
    store = MemoryStore(backend=backend, workspace_id="ws1")

    await store.write_memory("m")
    await store.write_soul("s")
    await store.write_user("u")

    assert await store.read_memory() == "m"
    assert await store.read_soul() == "s"
    assert await store.read_user() == "u"


@pytest.mark.asyncio
async def test_memory_context_empty_vs_full() -> None:
    backend = InMemoryBackend()
    store = MemoryStore(backend=backend, workspace_id="ws1")

    assert await store.get_memory_context() == ""
    await store.write_memory("hello")
    assert await store.get_memory_context() == "## Long-term Memory\nhello"


@pytest.mark.asyncio
async def test_append_history_strips_think() -> None:
    backend = InMemoryBackend()
    store = MemoryStore(backend=backend, workspace_id="ws1")

    cur = await store.append_history("  <think>秘密</think>\n结论  \n")
    assert cur == 1
    rows = await backend.read_history("ws1", since_cursor=0)
    assert rows[0]["content"] == "结论"


@pytest.mark.asyncio
async def test_read_unprocessed_filter_and_count() -> None:
    backend = InMemoryBackend()
    store = MemoryStore(backend=backend, workspace_id="ws1")

    for i in range(5):
        await store.append_history(f"e{i}")

    rows = await store.read_unprocessed_history(since_cursor=2)
    assert [r["cursor"] for r in rows] == [3, 4, 5]

    assert await store.count_unprocessed_history(2) == 3


@pytest.mark.asyncio
async def test_compact_history_by_limit_and_disabled() -> None:
    backend = InMemoryBackend()
    store = MemoryStore(backend=backend, workspace_id="ws1", max_history_entries=5)
    for i in range(7):
        await store.append_history(f"x{i}")

    deleted = await store.compact_history()
    assert deleted == 2
    remaining = await backend.read_history("ws1", since_cursor=0)
    assert [r["cursor"] for r in remaining] == [3, 4, 5, 6, 7]

    backend2 = InMemoryBackend()
    store2 = MemoryStore(backend=backend2, workspace_id="ws1", max_history_entries=0)
    for i in range(3):
        await store2.append_history(f"y{i}")
    assert await store2.compact_history() == 0
    assert backend2.compact_called == 0


@pytest.mark.asyncio
async def test_cursor_dream_roundtrip() -> None:
    backend = InMemoryBackend()
    store = MemoryStore(backend=backend, workspace_id="ws1")

    await store.append_history("a")
    await store.append_history("b")
    assert await store.get_last_cursor() == 2
    assert await store.get_last_dream_cursor() == 0

    await store.set_last_dream_cursor(10)
    assert await store.get_last_dream_cursor() == 10
    assert await store.get_last_cursor() == 2


@pytest.mark.asyncio
async def test_raw_archive_fallback() -> None:
    backend = InMemoryBackend()
    store = MemoryStore(backend=backend, workspace_id="ws1")

    messages = [
        {"role": "user", "content": "u", "timestamp": "2026-01-01T00:00:00"},
        {"role": "assistant", "content": "a", "timestamp": "2026-01-01T00:00:01"},
    ]
    await store.raw_archive(messages)
    rows = await backend.read_history("ws1", since_cursor=0)
    assert rows and rows[0]["content"].startswith("[RAW] 2 messages\n")


@pytest.mark.asyncio
async def test_workspace_isolation() -> None:
    backend = InMemoryBackend()
    a = MemoryStore(backend=backend, workspace_id="wsA")
    b = MemoryStore(backend=backend, workspace_id="wsB")

    await a.write_memory("A")
    await b.write_memory("B")
    assert await a.read_memory() == "A"
    assert await b.read_memory() == "B"

    await a.append_history("ha")
    await b.append_history("hb")
    assert [r["content"] for r in await a.read_unprocessed_history(0)] == ["ha"]
    assert [r["content"] for r in await b.read_unprocessed_history(0)] == ["hb"]

    await a.set_last_dream_cursor(3)
    await b.set_last_dream_cursor(7)
    assert await a.get_last_dream_cursor() == 3
    assert await b.get_last_dream_cursor() == 7

