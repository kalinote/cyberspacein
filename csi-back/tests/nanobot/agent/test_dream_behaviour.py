"""MIGRATION_PLAN §12.9：Dream（阈值触发 + 单次 LLM 回写）单测（纯 mock）。"""

from __future__ import annotations

from datetime import datetime
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.service.nanobot.agent.memory import Dream, MemoryStore
from app.service.nanobot.config.schema import DreamConfig


class DreamTestBackend:
    """最小 MemoryBackend：支撑 Dream 所需的 read/write/history/cursors。"""

    def __init__(self) -> None:
        self.docs: dict[tuple[str, str], str] = {}
        self.history: list[dict[str, Any]] = []
        self.dream_cursor: dict[str, int] = {}
        self.compact_calls: list[tuple[str, int]] = []
        self.writes: list[tuple[str, str, str]] = []

    async def read_doc(self, workspace_id: str, doc_type: str) -> str:
        return self.docs.get((workspace_id, doc_type), "")

    async def write_doc(self, workspace_id: str, doc_type: str, content: str) -> None:
        self.writes.append((doc_type, content))
        self.docs[(workspace_id, doc_type)] = content

    async def append_history(self, workspace_id: str, entry: str) -> int:
        cur = max((h["cursor"] for h in self.history if h["workspace_id"] == workspace_id), default=0) + 1
        self.history.append(
            {
                "workspace_id": workspace_id,
                "cursor": cur,
                "content": entry,
                "created_at": datetime(2026, 1, 1, 12, 0, 0),
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
        self.compact_calls.append((workspace_id, max_entries))
        return 0

    async def get_cursors(self, workspace_id: str) -> tuple[int, int]:
        last = max((h["cursor"] for h in self.history if h["workspace_id"] == workspace_id), default=0)
        return (last, self.dream_cursor.get(workspace_id, 0))

    async def set_dream_cursor(self, workspace_id: str, cursor: int) -> None:
        self.dream_cursor[workspace_id] = cursor


def _store(ws: str = "ws1", *, max_history: int = 1000) -> tuple[MemoryStore, DreamTestBackend]:
    backend = DreamTestBackend()
    return MemoryStore(backend, workspace_id=ws, max_history_entries=max_history), backend


def _dream(store: MemoryStore, provider: Any, **cfg_kw: Any) -> Dream:
    cfg = DreamConfig(**cfg_kw)
    return Dream(store=store, provider=provider, model="test-model", config=cfg)


@pytest.mark.asyncio
async def test_should_trigger_disabled() -> None:
    store, _ = _store()
    prov = MagicMock()
    d = _dream(store, prov, enabled=False, trigger_unprocessed_count=1, max_batch_size=10)
    assert await d.should_trigger() is False


@pytest.mark.asyncio
async def test_should_trigger_below_threshold() -> None:
    store, backend = _store()
    for _ in range(3):
        await store.append_history("x")
    prov = MagicMock()
    d = _dream(store, prov, enabled=True, trigger_unprocessed_count=5, max_batch_size=10)
    assert await d.should_trigger() is False
    assert backend.dream_cursor.get("ws1", 0) == 0


@pytest.mark.asyncio
async def test_should_trigger_at_threshold() -> None:
    store, _ = _store()
    for _ in range(5):
        await store.append_history("x")
    prov = MagicMock()
    d = _dream(store, prov, enabled=True, trigger_unprocessed_count=5, max_batch_size=10)
    assert await d.should_trigger() is True


@pytest.mark.asyncio
async def test_run_noop_when_disabled() -> None:
    store, backend = _store()
    await store.append_history("a")
    prov = MagicMock()
    d = _dream(store, prov, enabled=False, trigger_unprocessed_count=1, max_batch_size=10)
    assert await d.run() is False
    prov.chat_with_retry.assert_not_called()
    assert backend.compact_calls == []


@pytest.mark.asyncio
async def test_run_noop_when_no_entries() -> None:
    store, backend = _store()
    prov = MagicMock()
    d = _dream(store, prov, enabled=True, trigger_unprocessed_count=1, max_batch_size=10)
    assert await d.run() is False
    prov.chat_with_retry.assert_not_called()
    assert backend.compact_calls == []


@pytest.mark.asyncio
async def test_run_llm_failure_returns_false() -> None:
    store, backend = _store()
    for _ in range(3):
        await store.append_history("h")
    prov = MagicMock()
    prov.chat_with_retry = AsyncMock(side_effect=RuntimeError("LLM 失败"))
    d = _dream(store, prov, enabled=True, trigger_unprocessed_count=1, max_batch_size=10)

    assert await d.run() is False
    assert backend.writes == []
    assert backend.dream_cursor.get("ws1", 0) == 0
    assert backend.compact_calls == []


@pytest.mark.asyncio
async def test_run_no_change_preserves_docs() -> None:
    store, backend = _store()
    for _ in range(3):
        await store.append_history("e")
    await store.write_memory("M0")
    await store.write_soul("S0")
    await store.write_user("U0")
    backend.writes.clear()

    llm_out = (
        "## NEW_MEMORY\nNO_CHANGE\n"
        "## NEW_SOUL\nNO_CHANGE\n"
        "## NEW_USER\nNO_CHANGE\n"
    )
    prov = MagicMock()
    prov.chat_with_retry = AsyncMock(
        return_value=SimpleNamespace(finish_reason="stop", content=llm_out)
    )
    d = _dream(store, prov, enabled=True, trigger_unprocessed_count=1, max_batch_size=10)

    assert await d.run() is True
    assert backend.writes == []
    assert await store.read_memory() == "M0"
    assert backend.dream_cursor["ws1"] == 3
    assert len(backend.compact_calls) == 1


@pytest.mark.asyncio
async def test_run_partial_update() -> None:
    store, backend = _store()
    for _ in range(2):
        await store.append_history("x")
    await store.write_memory("old_m")
    await store.write_soul("old_s")
    await store.write_user("old_u")
    backend.writes.clear()

    llm_out = (
        "## NEW_MEMORY\n新记忆\n"
        "## NEW_SOUL\nNO_CHANGE\n"
        "## NEW_USER\n新用户\n"
    )
    prov = MagicMock()
    prov.chat_with_retry = AsyncMock(
        return_value=SimpleNamespace(finish_reason="stop", content=llm_out)
    )
    d = _dream(store, prov, enabled=True, trigger_unprocessed_count=1, max_batch_size=10)

    assert await d.run() is True
    assert [w[0] for w in backend.writes] == ["memory", "user"]
    assert await store.read_memory() == "新记忆"
    assert await store.read_soul() == "old_s"
    assert await store.read_user() == "新用户"
    assert backend.dream_cursor["ws1"] == 2


@pytest.mark.asyncio
async def test_run_advances_cursor_and_compacts() -> None:
    store, backend = _store(max_history=5)
    for _ in range(4):
        await store.append_history("row")
    prov = MagicMock()
    prov.chat_with_retry = AsyncMock(
        return_value=SimpleNamespace(
            finish_reason="stop",
            content="## NEW_MEMORY\nNO_CHANGE\n## NEW_SOUL\nNO_CHANGE\n## NEW_USER\nNO_CHANGE\n",
        )
    )
    d = _dream(store, prov, enabled=True, trigger_unprocessed_count=1, max_batch_size=10)

    assert await d.run() is True
    assert backend.compact_calls == [("ws1", 5)]


@pytest.mark.asyncio
async def test_batch_size_honored() -> None:
    store, backend = _store()
    for i in range(50):
        await store.append_history(f"e{i}")
    prov = MagicMock()
    captured: dict[str, Any] = {}

    async def _capture(**kw: Any) -> Any:
        captured["user"] = kw["messages"][1]["content"]
        return SimpleNamespace(
            finish_reason="stop",
            content="## NEW_MEMORY\nNO_CHANGE\n## NEW_SOUL\nNO_CHANGE\n## NEW_USER\nNO_CHANGE\n",
        )

    prov.chat_with_retry = AsyncMock(side_effect=_capture)
    d = _dream(store, prov, enabled=True, trigger_unprocessed_count=1, max_batch_size=20)

    assert await d.run() is True
    assert "e19" in captured["user"]
    assert "e20" not in captured["user"]
    assert backend.dream_cursor["ws1"] == 20


def test_parse_sections_basic() -> None:
    text = (
        "## NEW_MEMORY\nA\n\n"
        "## NEW_SOUL\nB\n\n"
        "## NEW_USER\nC\n"
    )
    got = Dream._parse_sections(text)
    assert got == {"memory": "A", "soul": "B", "user": "C"}


def test_parse_sections_no_change_case_insensitive() -> None:
    text = (
        "## NEW_MEMORY\nno_change\n"
        "## NEW_SOUL\nNo_Change\n"
        "## NEW_USER\nNO_CHANGE\n"
    )
    got = Dream._parse_sections(text)
    assert got == {"memory": None, "soul": None, "user": None}


def test_parse_sections_missing_section() -> None:
    text = "## NEW_MEMORY\n仅一段\n"
    got = Dream._parse_sections(text)
    assert got["memory"] == "仅一段"
    assert got["soul"] is None
    assert got["user"] is None


def test_parse_sections_extra_whitespace_and_markdown() -> None:
    text = (
        "  \n"
        "## NEW_MEMORY\n"
        "```markdown\n# 标题\n正文\n```\n\n"
        "## NEW_SOUL\nNO_CHANGE\n"
    )
    got = Dream._parse_sections(text)
    assert "```markdown" in got["memory"]
    assert "# 标题" in got["memory"]
    assert "正文" in got["memory"]
    assert got["soul"] is None


@pytest.mark.asyncio
async def test_run_llm_error_finish_reason_returns_false() -> None:
    store, backend = _store()
    await store.append_history("x")
    prov = MagicMock()
    prov.chat_with_retry = AsyncMock(
        return_value=SimpleNamespace(finish_reason="error", content="bad")
    )
    d = _dream(store, prov, enabled=True, trigger_unprocessed_count=1, max_batch_size=10)
    assert await d.run() is False
    assert backend.writes == []
    assert backend.dream_cursor.get("ws1", 0) == 0
