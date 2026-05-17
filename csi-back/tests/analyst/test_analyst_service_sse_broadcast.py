from __future__ import annotations

import pytest

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
