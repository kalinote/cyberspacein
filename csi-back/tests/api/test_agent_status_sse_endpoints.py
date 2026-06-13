"""MIGRATION_PLAN §12.13：/agent/status SSE 路由（事件格式、keep-alive、断线清理）。"""

from __future__ import annotations

import asyncio
from typing import Any

import pytest

import app.api.v1.endpoints.agent.runtime as runtime_ep


class _FakeRequest:
    def __init__(self, disconnect_after: int) -> None:
        self._n = 0
        self._after = disconnect_after

    async def is_disconnected(self) -> bool:
        self._n += 1
        return self._n >= self._after


@pytest.mark.asyncio
async def test_route_status_sse_event_stream_format(monkeypatch: pytest.MonkeyPatch) -> None:
    queue: asyncio.Queue = asyncio.Queue()

    async def _subscribe(
        _agent_id: str,
        _session_id: str,
        *,
        limit: int | None = None,
        offset: int = 0,
    ) -> asyncio.Queue:
        return queue

    async def _unsubscribe(_agent_id: str, _session_id: str, _queue: asyncio.Queue) -> None:
        return None

    monkeypatch.setattr(runtime_ep.AnalystService, "subscribe", _subscribe)
    monkeypatch.setattr(runtime_ep.AnalystService, "unsubscribe", _unsubscribe)

    await queue.put({"event": "status", "data": {"x": 1}})
    req = _FakeRequest(disconnect_after=2)
    resp = await runtime_ep.get_agent_status(req, agent_id="a1", session_id="s1")

    chunks: list[str] = []
    async for b in resp.body_iterator:
        chunks.append(b.decode() if isinstance(b, (bytes, bytearray)) else str(b))
        break

    assert chunks
    text = "".join(chunks)
    assert "event: status" in text
    assert "data: " in text


@pytest.mark.asyncio
async def test_route_status_sse_keepalive_on_idle(monkeypatch: pytest.MonkeyPatch) -> None:
    queue: asyncio.Queue = asyncio.Queue()

    async def _subscribe(
        _agent_id: str,
        _session_id: str,
        *,
        limit: int | None = None,
        offset: int = 0,
    ) -> asyncio.Queue:
        return queue

    async def _unsubscribe(_agent_id: str, _session_id: str, _queue: asyncio.Queue) -> None:
        return None

    monkeypatch.setattr(runtime_ep.AnalystService, "subscribe", _subscribe)
    monkeypatch.setattr(runtime_ep.AnalystService, "unsubscribe", _unsubscribe)

    called = {"n": 0}
    orig_wait_for = asyncio.wait_for

    async def _wait_for(awaitable: Any, timeout: float):
        called["n"] += 1
        if called["n"] == 1:
            if hasattr(awaitable, "close"):
                awaitable.close()
            raise asyncio.TimeoutError()
        return await orig_wait_for(awaitable, timeout=0.01)

    monkeypatch.setattr(runtime_ep.asyncio, "wait_for", _wait_for)

    req = _FakeRequest(disconnect_after=2)
    resp = await runtime_ep.get_agent_status(req, agent_id="a1", session_id="s1")
    chunk = await anext(resp.body_iterator)
    text = chunk.decode() if isinstance(chunk, (bytes, bytearray)) else str(chunk)
    assert text.strip() == ": keep-alive"


@pytest.mark.asyncio
async def test_route_status_unsubscribes_on_disconnect(monkeypatch: pytest.MonkeyPatch) -> None:
    queue: asyncio.Queue = asyncio.Queue()
    calls: list[tuple[str, str, asyncio.Queue]] = []

    async def _subscribe(
        _agent_id: str,
        _session_id: str,
        *,
        limit: int | None = None,
        offset: int = 0,
    ) -> asyncio.Queue:
        return queue

    async def _unsubscribe(agent_id: str, session_id: str, q: asyncio.Queue) -> None:
        calls.append((agent_id, session_id, q))

    monkeypatch.setattr(runtime_ep.AnalystService, "subscribe", _subscribe)
    monkeypatch.setattr(runtime_ep.AnalystService, "unsubscribe", _unsubscribe)

    req = _FakeRequest(disconnect_after=1)
    resp = await runtime_ep.get_agent_status(req, agent_id="a1", session_id="s1")

    async for _ in resp.body_iterator:
        pass

    assert calls == [("a1", "s1", queue)]


@pytest.mark.asyncio
async def test_route_status_passes_replay_pagination_params(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    queue: asyncio.Queue = asyncio.Queue()
    captured: dict[str, int | None] = {}

    async def _subscribe(
        _agent_id: str,
        _session_id: str,
        *,
        limit: int | None = None,
        offset: int = 0,
    ) -> asyncio.Queue:
        captured["limit"] = limit
        captured["offset"] = offset
        return queue

    async def _unsubscribe(_agent_id: str, _session_id: str, _queue: asyncio.Queue) -> None:
        return None

    monkeypatch.setattr(runtime_ep.AnalystService, "subscribe", _subscribe)
    monkeypatch.setattr(runtime_ep.AnalystService, "unsubscribe", _unsubscribe)

    req = _FakeRequest(disconnect_after=1)
    await runtime_ep.get_agent_status(
        req, agent_id="a1", session_id="s1", limit=50, offset=10
    )

    assert captured == {"limit": 50, "offset": 10}
