"""MIGRATION_PLAN §12.10：ContextBuilder + MemorySnapshot（纯 mock / 假 MemoryStore）。"""

from __future__ import annotations

import asyncio
from datetime import datetime
from typing import Any
from unittest.mock import MagicMock

import pytest

import app.service.nanobot.agent.context as context_module
from app.service.nanobot.agent.context import ContextBuilder, MemorySnapshot


class FakeMemoryStore:
    def __init__(
        self,
        *,
        memory: str = "",
        soul: str = "",
        user: str = "",
        dream_cursor: int = 0,
        history: list[dict[str, Any]] | None = None,
    ) -> None:
        self._memory = memory
        self._soul = soul
        self._user = user
        self._dream = dream_cursor
        self._history = history or []

    async def read_memory(self) -> str:
        return self._memory

    async def read_soul(self) -> str:
        return self._soul

    async def read_user(self) -> str:
        return self._user

    async def get_last_dream_cursor(self) -> int:
        return self._dream

    async def read_unprocessed_history(self, since_cursor: int) -> list[dict[str, Any]]:
        return [e for e in self._history if e["cursor"] > since_cursor]


def _builder(mem: FakeMemoryStore, **kw: Any) -> ContextBuilder:
    return ContextBuilder(mem, skills=kw.get("skills"), timezone=kw.get("timezone"), extra_system_suffix=kw.get("extra_system_suffix", ""))


@pytest.mark.asyncio
async def test_refresh_snapshot_concurrent(monkeypatch: pytest.MonkeyPatch) -> None:
    mem = FakeMemoryStore(
        memory="M",
        soul="S",
        user="U",
        dream_cursor=2,
        history=[{"cursor": 3, "content": "h", "created_at": datetime(2026, 2, 1, 10, 30)}],
    )
    sizes: list[int] = []
    orig_gather = asyncio.gather

    def _track_gather(*aws: Any, **kw: Any) -> Any:
        sizes.append(len(aws))
        return orig_gather(*aws, **kw)

    monkeypatch.setattr(context_module.asyncio, "gather", _track_gather)
    cb = _builder(mem)
    snap = await cb.refresh_memory_snapshot()

    assert sizes == [4]
    assert snap.memory == "M" and snap.soul == "S" and snap.user == "U"
    assert len(snap.recent_history) == 1
    assert snap.recent_history[0]["cursor"] == 3


@pytest.mark.asyncio
async def test_refresh_history_capped() -> None:
    rows = [
        {"cursor": i, "content": f"c{i}", "created_at": datetime(2026, 1, 1, 0, i % 60)}
        for i in range(1, 101)
    ]
    mem = FakeMemoryStore(dream_cursor=0, history=rows)
    cb = _builder(mem)
    snap = await cb.refresh_memory_snapshot()

    assert len(snap.recent_history) == 50
    assert snap.recent_history[0]["cursor"] == 51
    assert snap.recent_history[-1]["cursor"] == 100


def test_empty_snapshot_prompt() -> None:
    cb = _builder(FakeMemoryStore())
    prompt = cb.build_system_prompt()

    assert "## Search & Discovery" in prompt
    assert "# Memory\n\n## Long-term Memory" not in prompt
    assert "# Recent History" not in prompt
    assert "## SOUL\n\n" not in prompt
    assert "## USER\n\n" not in prompt


def test_persona_block_soul_only() -> None:
    cb = _builder(FakeMemoryStore())
    cb._snapshot = MemorySnapshot(memory="", soul="人格", user="  \n", recent_history=[])

    prompt = cb.build_system_prompt()
    assert "## SOUL" in prompt
    assert "人格" in prompt
    assert "## USER\n\n" not in prompt


def test_persona_block_user_only() -> None:
    cb = _builder(FakeMemoryStore())
    cb._snapshot = MemorySnapshot(memory="", soul="", user="画像内容", recent_history=[])

    prompt = cb.build_system_prompt()
    assert "## USER" in prompt
    assert "画像内容" in prompt
    assert "## SOUL\n\n" not in prompt


def test_memory_section_injection() -> None:
    cb = _builder(FakeMemoryStore())
    cb._snapshot = MemorySnapshot(memory="长期片段", soul="", user="", recent_history=[])

    prompt = cb.build_system_prompt()
    assert "# Memory\n\n## Long-term Memory\n长期片段" in prompt


def test_recent_history_render() -> None:
    cb = _builder(FakeMemoryStore())
    cb._snapshot = MemorySnapshot(
        recent_history=[
            {"content": "a", "created_at": datetime(2026, 3, 15, 14, 5)},
            {"content": "b", "created_at": "2026-03-16T09:30:00+00:00"},
            {"content": "c"},
        ],
    )

    prompt = cb.build_system_prompt()
    assert "- [2026-03-15 14:05] a" in prompt
    assert "- [2026-03-16T09:30] b" in prompt
    assert "- [?] c" in prompt


def test_build_messages_single_user_turn() -> None:
    cb = _builder(FakeMemoryStore())
    cb._snapshot = MemorySnapshot()

    history = [{"role": "user", "content": "第一轮"}]
    out = cb.build_messages(history, "第二轮", channel=None, chat_id=None, current_role="user")

    assert len(out) == 2
    assert out[-1]["role"] == "user"
    last = out[-1]["content"]
    assert isinstance(last, str)
    assert "第一轮" in last
    assert "第二轮" in last


def test_build_messages_runtime_ctx_merged() -> None:
    cb = _builder(FakeMemoryStore(), timezone="UTC")
    cb._snapshot = MemorySnapshot()

    history = [{"role": "assistant", "content": "ok"}]
    out = cb.build_messages(
        history,
        "问题",
        channel="telegram",
        chat_id="99",
        current_role="user",
    )

    assert len(out) == 3
    assert out[-1]["role"] == "user"
    body = out[-1]["content"]
    assert isinstance(body, str)
    assert context_module.ContextBuilder._RUNTIME_CONTEXT_TAG in body
    assert "Current Time:" in body
    assert "Channel: telegram" in body
    assert "Chat ID: 99" in body
    assert "问题" in body


def test_identity_no_workspace_path() -> None:
    cb = _builder(FakeMemoryStore())
    prompt = cb.build_system_prompt()

    assert "{{" not in prompt
    assert "}}" not in prompt
    assert "workspace_path" not in prompt.lower()


def test_skills_none_safely() -> None:
    cb = _builder(FakeMemoryStore(), skills=None)
    prompt = cb.build_system_prompt()
    assert "# Active Skills" not in prompt
    assert isinstance(prompt, str) and len(prompt) > 50
