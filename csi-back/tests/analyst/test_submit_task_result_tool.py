"""submit_task_result 业务工具与 ContextVar。"""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

import app.service.analyst.context as ctx
import app.service.analyst.service as analyst_service
from app.service.analyst.tools import SubmitTaskResultTool


@pytest.mark.asyncio
async def test_submit_task_result_writes_context(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(analyst_service.AnalystService, "broadcast_sse", AsyncMock())
    tok_agent = ctx.current_agent_id.set("a1")
    tok_sess = ctx.current_session_id.set("s1")
    try:
        tool = SubmitTaskResultTool()
        out = await tool.execute(
            success=True,
            failure_reason=None,
            short_summary="摘要",
            payload={"x": 2},
        )
        assert "Markdown" in out
        got = ctx.get_current_task_completion()
        assert got is not None
        assert got["success"] is True
        assert got["payload"] == {"x": 2}
    finally:
        ctx.current_session_id.reset(tok_sess)
        ctx.current_agent_id.reset(tok_agent)
