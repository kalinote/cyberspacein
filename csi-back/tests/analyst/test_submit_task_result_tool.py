"""submit_task_result 业务工具、ContextVar 与 task_submissions 持久化。"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any
from unittest.mock import AsyncMock

import pytest

import app.service.analyst.context as ctx
import app.service.analyst.service as analyst_service
import app.service.analyst.tools.submit_task_result as submit_task_result_module
from app.service.analyst.tools import SubmitTaskResultTool


@dataclass
class FakeSessionDoc:
    id: str
    task_submissions: list[dict] = field(default_factory=list)
    updated_at: datetime = field(default_factory=datetime.now)

    async def save(self) -> None:
        FakeNanobotSessionModel._docs[self.id] = self


class FakeNanobotSessionModel:
    _docs: dict[str, FakeSessionDoc] = {}

    @classmethod
    async def find_one(cls, query: dict[str, Any]) -> FakeSessionDoc | None:
        return cls._docs.get(query.get("_id"))


@pytest.fixture(autouse=True)
def _patch_session_model(monkeypatch: pytest.MonkeyPatch) -> None:
    FakeNanobotSessionModel._docs = {"s1": FakeSessionDoc(id="s1")}
    monkeypatch.setattr(submit_task_result_module, "NanobotSessionModel", FakeNanobotSessionModel)


@pytest.mark.asyncio
async def test_submit_task_result_writes_context_and_db(monkeypatch: pytest.MonkeyPatch) -> None:
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
        assert "已记录" in out
        assert "不要调用任何工具" not in out
        got = ctx.get_current_task_completion()
        assert got is not None
        assert got["success"] is True
        assert got["payload"] == {"x": 2}
        assert got.get("id")
        doc = FakeNanobotSessionModel._docs["s1"]
        assert len(doc.task_submissions) == 1
        assert doc.task_submissions[0]["payload"] == {"x": 2}
    finally:
        ctx.current_session_id.reset(tok_sess)
        ctx.current_agent_id.reset(tok_agent)


@pytest.mark.asyncio
async def test_submit_task_result_appends_multiple(monkeypatch: pytest.MonkeyPatch) -> None:
    broadcast = AsyncMock()
    monkeypatch.setattr(analyst_service.AnalystService, "broadcast_sse", broadcast)
    tok_agent = ctx.current_agent_id.set("a1")
    tok_sess = ctx.current_session_id.set("s1")
    try:
        tool = SubmitTaskResultTool()
        await tool.execute(
            success=True,
            failure_reason=None,
            short_summary="第一次",
            payload={"n": 1},
        )
        await tool.execute(
            success=True,
            failure_reason=None,
            short_summary="第二次",
            payload={"n": 2},
        )
        doc = FakeNanobotSessionModel._docs["s1"]
        assert len(doc.task_submissions) == 2
        assert doc.task_submissions[0]["short_summary"] == "第一次"
        assert doc.task_submissions[1]["short_summary"] == "第二次"
        assert broadcast.await_count == 2
        second_call = broadcast.await_args_list[1].args[2]
        assert second_call["index"] == 1
    finally:
        ctx.current_session_id.reset(tok_sess)
        ctx.current_agent_id.reset(tok_agent)
