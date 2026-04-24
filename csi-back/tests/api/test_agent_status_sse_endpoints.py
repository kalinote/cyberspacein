"""MIGRATION_PLAN §12.13：/agent/status SSE 路由（事件格式、keep-alive、断线清理）。"""

from __future__ import annotations

import asyncio
from typing import Any

import pytest

from app.api.v1.endpoints import agent as agent_ep


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

    async def _subscribe(_agent_id: str) -> asyncio.Queue:
        return queue

    async def _unsubscribe(_agent_id: str, _queue: asyncio.Queue) -> None:
        return None

    monkeypatch.setattr(agent_ep.AnalystService, "subscribe", _subscribe)
    monkeypatch.setattr(agent_ep.AnalystService, "unsubscribe", _unsubscribe)

    await queue.put({"event": "status", "data": {"x": 1}})
    req = _FakeRequest(disconnect_after=2)  # 第一轮不断开，第二轮断开
    resp = await agent_ep.get_agent_status(req, agent_id="a1")

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

    async def _subscribe(_agent_id: str) -> asyncio.Queue:
        return queue

    async def _unsubscribe(_agent_id: str, _queue: asyncio.Queue) -> None:
        return None

    monkeypatch.setattr(agent_ep.AnalystService, "subscribe", _subscribe)
    monkeypatch.setattr(agent_ep.AnalystService, "unsubscribe", _unsubscribe)

    # 让 wait_for 立刻超时一次，触发 keep-alive，然后下一轮断开退出
    called = {"n": 0}
    orig_wait_for = asyncio.wait_for

    async def _wait_for(awaitable: Any, timeout: float):
        called["n"] += 1
        if called["n"] == 1:
            # 模拟超时前需要关闭 coroutine，避免 pytest 报 “coroutine was never awaited”
            if hasattr(awaitable, "close"):
                awaitable.close()
            raise asyncio.TimeoutError()
        return await orig_wait_for(awaitable, timeout=0.01)

    monkeypatch.setattr(agent_ep.asyncio, "wait_for", _wait_for)

    req = _FakeRequest(disconnect_after=2)
    resp = await agent_ep.get_agent_status(req, agent_id="a1")
    chunk = await anext(resp.body_iterator)
    text = chunk.decode() if isinstance(chunk, (bytes, bytearray)) else str(chunk)
    assert text.strip() == ": keep-alive"


@pytest.mark.asyncio
async def test_route_status_unsubscribes_on_disconnect(monkeypatch: pytest.MonkeyPatch) -> None:
    queue: asyncio.Queue = asyncio.Queue()
    calls: list[tuple[str, asyncio.Queue]] = []

    async def _subscribe(_agent_id: str) -> asyncio.Queue:
        return queue

    async def _unsubscribe(agent_id: str, q: asyncio.Queue) -> None:
        calls.append((agent_id, q))

    monkeypatch.setattr(agent_ep.AnalystService, "subscribe", _subscribe)
    monkeypatch.setattr(agent_ep.AnalystService, "unsubscribe", _unsubscribe)

    req = _FakeRequest(disconnect_after=1)  # 立刻断开，走 finally
    resp = await agent_ep.get_agent_status(req, agent_id="a1")

    # 消费完 body_iterator 才会触发 finally（unsubscribe）
    async for _ in resp.body_iterator:
        pass

    assert calls == [("a1", queue)]

