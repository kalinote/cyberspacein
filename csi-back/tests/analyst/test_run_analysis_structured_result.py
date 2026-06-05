"""AnalystService.run_analysis 结果落库与 SSE 载荷（纯 mock）。"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import datetime
from types import SimpleNamespace
from typing import Any, Iterable
from unittest.mock import AsyncMock, MagicMock

import pytest

import app.service.analyst.context as actx
import app.service.analyst.service as service_module
from app.schemas.constants import NanobotSessionStatusEnum


@dataclass
class FakeSessionDoc:
    id: str
    status: NanobotSessionStatusEnum = NanobotSessionStatusEnum.RUNNING
    result: dict | None = None
    pending_approval: dict | None = None
    error_message: str | None = None
    finished_at: Any = None

    async def save(self) -> None:
        FakeNanobotSessionModel._docs[self.id] = self


class FakeNanobotSessionModel:
    _docs: dict[str, FakeSessionDoc] = {}

    @classmethod
    async def find_one(cls, query: dict[str, Any]) -> FakeSessionDoc | None:
        return cls._docs.get(query.get("_id"))


@pytest.fixture(autouse=True)
def _patch_model(monkeypatch: pytest.MonkeyPatch) -> Iterable[None]:
    FakeNanobotSessionModel._docs = {"s1": FakeSessionDoc(id="s1")}
    monkeypatch.setattr(service_module, "NanobotSessionModel", FakeNanobotSessionModel)
    service_module.AnalystService._sse_subscribers = {}
    service_module.AnalystService._sse_lock = asyncio.Lock()
    yield


@pytest.mark.asyncio
async def test_run_analysis_success_with_submit_tool_payload(monkeypatch: pytest.MonkeyPatch) -> None:
    bot = MagicMock()
    bot.loop.process_direct = None
    bot.close = AsyncMock()

    async def _run(*_a: Any, **_kw: Any) -> Any:
        actx.current_task_completion.set(
            {
                "id": "sub-1",
                "success": True,
                "failure_reason": None,
                "short_summary": "x",
                "payload": {"k": 1},
                "submitted_at": datetime.now().isoformat(),
            }
        )
        return SimpleNamespace(
            content="## 用户可见",
            tools_used=["submit_task_result"],
            stop_reason="completed",
        )

    bot.run = AsyncMock(side_effect=_run)
    events: list[dict[str, Any]] = []

    async def _broadcast(agent_id: str, event: str, data: Any, *, persist: bool = True) -> None:
        events.append({"agent_id": agent_id, "event": event, "data": data})

    monkeypatch.setattr(service_module.AnalystService, "broadcast_sse", _broadcast)

    await service_module.AnalystService.run_analysis(
        agent_id="a1",
        session_id="s1",
        bot=bot,
        user_prompt="hi",
        context={},
    )
    doc = FakeNanobotSessionModel._docs["s1"]
    assert doc.status == NanobotSessionStatusEnum.COMPLETED
    assert doc.result and doc.result["completion_received"] is True
    assert doc.result["success"] is True
    assert doc.result["user_markdown"] == "## 用户可见"
    assert doc.result["payload"] == {"k": 1}
    result_events = [e for e in events if e["event"] == "result"]
    assert result_events
    assert result_events[-1]["data"]["result"]["completion_received"] is True


@pytest.mark.asyncio
async def test_run_analysis_user_markdown_not_json_still_ok_when_submit_ok(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    bot = MagicMock()
    bot.loop.process_direct = None
    bot.close = AsyncMock()

    async def _run(*_a: Any, **_kw: Any) -> Any:
        actx.current_task_completion.set(
            {
                "id": "sub-2",
                "success": True,
                "failure_reason": None,
                "short_summary": "y",
                "payload": {},
                "submitted_at": datetime.now().isoformat(),
            }
        )
        return SimpleNamespace(content="plain text 不是 json", tools_used=[], stop_reason="completed")

    bot.run = AsyncMock(side_effect=_run)
    monkeypatch.setattr(service_module.AnalystService, "broadcast_sse", AsyncMock())

    await service_module.AnalystService.run_analysis(
        agent_id="a1",
        session_id="s1",
        bot=bot,
        user_prompt="hi",
        context={},
    )
    doc = FakeNanobotSessionModel._docs["s1"]
    assert doc.status == NanobotSessionStatusEnum.COMPLETED
    assert doc.result and doc.result["success"] is True
    assert doc.result["user_markdown"] == "plain text 不是 json"


@pytest.mark.asyncio
async def test_run_analysis_exception_result_shape(monkeypatch: pytest.MonkeyPatch) -> None:
    bot = MagicMock()
    bot.loop.process_direct = None

    async def _boom(*_a: Any, **_kw: Any) -> Any:
        raise RuntimeError("boom")

    bot.run = AsyncMock(side_effect=_boom)
    bot.close = AsyncMock()
    events: list[dict[str, Any]] = []

    async def _broadcast(agent_id: str, event: str, data: Any, *, persist: bool = True) -> None:
        events.append({"agent_id": agent_id, "event": event, "data": data})

    monkeypatch.setattr(service_module.AnalystService, "broadcast_sse", _broadcast)

    await service_module.AnalystService.run_analysis(
        agent_id="a1",
        session_id="s1",
        bot=bot,
        user_prompt="hi",
        context={},
    )
    doc = FakeNanobotSessionModel._docs["s1"]
    assert doc.status == NanobotSessionStatusEnum.FAILED
    assert doc.result and "error" in doc.result
    result_events = [e for e in events if e["event"] == "result"]
    assert result_events
    assert result_events[-1]["data"]["error"]
