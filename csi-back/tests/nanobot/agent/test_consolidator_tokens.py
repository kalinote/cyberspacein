"""MIGRATION_PLAN §12.8：Consolidator（token 预算滚动归档）单测（纯 mock）。"""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any, Callable
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.service.nanobot.agent.memory import Consolidator
from app.service.nanobot.session.manager import Session


class FakeMemoryStore:
    def __init__(self) -> None:
        self.appended: list[str] = []
        self.raw_archived: list[list[dict[str, Any]]] = []

    async def append_history(self, entry: str) -> int:
        self.appended.append(entry)
        return len(self.appended)

    async def raw_archive(self, messages: list[dict[str, Any]]) -> None:
        self.raw_archived.append(list(messages))


class FakeSessionManager:
    def __init__(self) -> None:
        self.saved: list[Session] = []

    async def save(self, session: Session) -> None:
        self.saved.append(session)


def _build_messages(**_kwargs: Any) -> list[dict[str, Any]]:
    # token probe 的内容对本组单测不重要
    return [{"role": "user", "content": "probe"}]


def _tools() -> list[dict[str, Any]]:
    return []


def _make_consolidator(
    *,
    store: FakeMemoryStore | None = None,
    sessions: FakeSessionManager | None = None,
    provider: Any | None = None,
    context_window_tokens: int = 20_000,
    max_completion_tokens: int = 1000,
) -> Consolidator:
    st = store or FakeMemoryStore()
    sm = sessions or FakeSessionManager()
    prov = provider or MagicMock()
    prov.generation.max_tokens = max_completion_tokens
    return Consolidator(
        store=st,  # type: ignore[arg-type]
        provider=prov,
        model="test",
        sessions=sm,  # type: ignore[arg-type]
        context_window_tokens=context_window_tokens,
        build_messages=_build_messages,
        get_tool_definitions=_tools,
        max_completion_tokens=max_completion_tokens,
    )


def _session_with_roles(roles: list[str]) -> Session:
    s = Session(id="s1", agent_id="a1", workspace_id="w1")
    for r in roles:
        s.messages.append({"role": r, "content": r})
    return s


def test_lock_per_session_id() -> None:
    c = _make_consolidator()
    assert c.get_lock("s1") is c.get_lock("s1")
    assert c.get_lock("s1") is not c.get_lock("s2")


def test_pick_boundary_at_user_turn(monkeypatch: pytest.MonkeyPatch) -> None:
    # 用 message['t'] 控制 token 计数
    import app.service.nanobot.agent.memory as mem_mod

    monkeypatch.setattr(mem_mod, "estimate_message_tokens", lambda m: int(m.get("t", 1)))

    s = Session(id="s1", agent_id="a1", workspace_id="w1")
    s.messages = [
        {"role": "user", "content": "u0", "t": 5},
        {"role": "assistant", "content": "a0", "t": 5},
        {"role": "user", "content": "u1", "t": 5},
        {"role": "assistant", "content": "a1", "t": 5},
    ]
    c = _make_consolidator()
    # tokens_to_remove=8：应在 idx=2（第二个 user）处命中边界
    boundary = c.pick_consolidation_boundary(s, tokens_to_remove=8)
    assert boundary is not None
    assert boundary[0] == 2


def test_cap_chunk_size_preserves_user_boundary() -> None:
    c = _make_consolidator()
    s = Session(id="s1", agent_id="a1", workspace_id="w1")
    # 构造 0..80，其中 user 在 0, 10, 30, 59, 60, 70
    s.messages = []
    for i in range(81):
        role = "user" if i in (0, 10, 30, 59, 60, 70) else "assistant"
        s.messages.append({"role": role, "content": str(i)})

    # end_idx 太大时应 cap 到 start+60=60，然后回退到 60 处 user
    end = c._cap_consolidation_boundary(s, end_idx=80)
    assert end == 60


@pytest.mark.asyncio
async def test_archive_success_appends_history() -> None:
    store = FakeMemoryStore()
    provider = MagicMock()
    provider.chat_with_retry = AsyncMock(
        return_value=SimpleNamespace(finish_reason="stop", content="摘要")
    )
    c = _make_consolidator(store=store, provider=provider)

    summary = await c.archive([{"role": "user", "content": "u"}])
    assert summary == "摘要"
    assert store.appended == ["摘要"]


@pytest.mark.asyncio
async def test_archive_failure_raw_dump() -> None:
    store = FakeMemoryStore()
    provider = MagicMock()
    provider.chat_with_retry = AsyncMock(side_effect=RuntimeError("boom"))
    c = _make_consolidator(store=store, provider=provider)

    summary = await c.archive([{"role": "user", "content": "u"}])
    assert summary is None
    assert store.raw_archived and store.raw_archived[0][0]["content"] == "u"


@pytest.mark.asyncio
async def test_maybe_consolidate_noop_under_budget(monkeypatch: pytest.MonkeyPatch) -> None:
    c = _make_consolidator(context_window_tokens=10_000, max_completion_tokens=1000)
    s = _session_with_roles(["user", "assistant", "user"])

    monkeypatch.setattr(c, "estimate_session_prompt_tokens", lambda *_a, **_k: (100, "x"))
    archive = AsyncMock()
    monkeypatch.setattr(c, "archive", archive)

    await c.maybe_consolidate_by_tokens(s)
    assert archive.await_count == 0


@pytest.mark.asyncio
async def test_maybe_consolidate_updates_last_consolidated_and_last_summary(monkeypatch: pytest.MonkeyPatch) -> None:
    store = FakeMemoryStore()
    sessions = FakeSessionManager()
    c = _make_consolidator(store=store, sessions=sessions, context_window_tokens=10_000, max_completion_tokens=1000)

    # 消息：u0 a0 u1 a1 u2 a2
    s = _session_with_roles(["user", "assistant", "user", "assistant", "user", "assistant"])

    # 强行让 token 估算：第一次超 budget，第二次低于 target
    seq = [(9500, "probe1"), (3000, "probe2")]

    def _estimate(*_a, **_k):
        return seq.pop(0)

    monkeypatch.setattr(c, "estimate_session_prompt_tokens", _estimate)

    # 边界选到 idx=2（第二个 user）
    monkeypatch.setattr(c, "pick_consolidation_boundary", lambda *_a, **_k: (2, 0))
    monkeypatch.setattr(c, "_cap_consolidation_boundary", lambda *_a, **_k: 2)
    monkeypatch.setattr(c, "archive", AsyncMock(return_value="S1"))

    await c.maybe_consolidate_by_tokens(s)

    assert s.last_consolidated == 2
    # sessions.save 至少调用 2 次：一次推进 last_consolidated、一次写 _last_summary
    assert len(sessions.saved) >= 2
    assert s.metadata.get("_last_summary", {}).get("text") == "S1"


@pytest.mark.asyncio
async def test_maybe_consolidate_stops_on_archive_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    sessions = FakeSessionManager()
    c = _make_consolidator(sessions=sessions, context_window_tokens=10_000, max_completion_tokens=1000)
    s = _session_with_roles(["user", "assistant", "user", "assistant"])

    monkeypatch.setattr(c, "estimate_session_prompt_tokens", lambda *_a, **_k: (9500, "x"))
    monkeypatch.setattr(c, "pick_consolidation_boundary", lambda *_a, **_k: (2, 0))
    monkeypatch.setattr(c, "_cap_consolidation_boundary", lambda *_a, **_k: 2)
    monkeypatch.setattr(c, "archive", AsyncMock(return_value=None))

    await c.maybe_consolidate_by_tokens(s)
    assert s.last_consolidated == 0
    assert sessions.saved == []

