from __future__ import annotations

import pytest

from app.service.analyst.service import AnalystService


@pytest.mark.asyncio
async def test_sse_debug_subscriber_only_receives_debug_events() -> None:
    agent_id = "a_debug"
    q_normal = await AnalystService.subscribe(agent_id, debug=False)
    q_debug = await AnalystService.subscribe(agent_id, debug=True)
    try:
        await AnalystService.broadcast_sse(agent_id, "status", {"x": 1})
        await AnalystService.broadcast_debug_sse(agent_id, "debug_prompt", {"p": 1})

        payload1 = await q_normal.get()
        assert payload1["event"] == "status"

        payload2 = await q_debug.get()
        assert payload2["event"] == "status"

        payload3 = await q_debug.get()
        assert payload3["event"] == "debug_prompt"

        # 普通订阅者不应收到 debug 事件
        assert q_normal.empty()
    finally:
        await AnalystService.unsubscribe(agent_id, q_normal)
        await AnalystService.unsubscribe(agent_id, q_debug)

