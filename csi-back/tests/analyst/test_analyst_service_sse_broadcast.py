from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock

import pytest

import app.service.analyst.hitl as hitl_module
import app.service.analyst.service as service_module
from app.service.analyst.service import AnalystService


@pytest.mark.asyncio
async def test_sse_subscriber_receives_debug_prompt_via_broadcast_sse() -> None:
    agent_id = "a1"
    session_id = "s1"
    q = await AnalystService.subscribe(agent_id, session_id)
    try:
        await AnalystService.broadcast_sse(
            agent_id, "status", {"session_id": session_id, "x": 1}
        )
        await AnalystService.broadcast_sse(
            agent_id, "debug_prompt", {"session_id": session_id, "p": 1}
        )

        assert (await q.get())["event"] == "status"
        assert (await q.get())["event"] == "debug_prompt"
        assert q.empty()
    finally:
        await AnalystService.unsubscribe(agent_id, session_id, q)


@pytest.mark.asyncio
async def test_launch_background_run_emits_user_message_before_status(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    events: list[tuple[str, dict]] = []

    async def _broadcast(
        agent_id: str, event: str, data: dict, *, persist: bool = True
    ) -> None:
        events.append((event, data))

    monkeypatch.setattr(service_module.AnalystService, "broadcast_sse", _broadcast)
    monkeypatch.setattr(hitl_module.HitlService, "clear_session", AsyncMock())
    monkeypatch.setattr(service_module.AnalystService, "run_analysis", AsyncMock())

    service_module.AnalystService._bots = {}
    service_module.AnalystService._running_tasks = {}
    service_module.AnalystService._cancel_reasons = {}
    service_module.AnalystService._bots_lock = asyncio.Lock()
    service_module.AnalystService._task_lock = asyncio.Lock()

    pending: list[asyncio.Task] = []
    real_create_task = asyncio.create_task

    def _capture_task(coro, **kwargs):
        task = real_create_task(coro, **kwargs)
        pending.append(task)
        return task

    monkeypatch.setattr(asyncio, "create_task", _capture_task)

    await AnalystService._launch_background_run(
        agent_id="a1",
        session_id="s1",
        bot=object(),
        user_prompt="继续分析",
        context={},
    )

    for task in pending:
        task.cancel()
    if pending:
        await asyncio.gather(*pending, return_exceptions=True)

    assert [e for e, _ in events] == ["user_message", "status"]
    assert events[0][1] == {
        "agent_id": "a1",
        "session_id": "s1",
        "content": "继续分析",
    }


@pytest.mark.asyncio
async def test_broadcast_sse_reasoning_stream_event() -> None:
    agent_id = "a1"
    session_id = "s1"
    q = await AnalystService.subscribe(agent_id, session_id)
    try:
        await AnalystService.broadcast_sse(
            agent_id,
            "reasoning_stream",
            {"agent_id": agent_id, "session_id": session_id, "delta": "思考中…"},
        )
        payload = await q.get()
        assert payload["event"] == "reasoning_stream"
        assert payload["data"]["delta"] == "思考中…"
        assert q.empty()
    finally:
        await AnalystService.unsubscribe(agent_id, session_id, q)
