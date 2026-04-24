"""MIGRATION_PLAN §12.16：AnalystService.run_analysis 结构化 result 落库与 SSE 载荷（纯 mock）。"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from types import SimpleNamespace
from typing import Any, Iterable
from unittest.mock import AsyncMock, MagicMock

import pytest

import app.service.analyst.service as service_module
from app.schemas.constants import NanobotAgentStatusEnum


@dataclass
class FakeAgentDoc:
    id: str
    status: NanobotAgentStatusEnum = NanobotAgentStatusEnum.RUNNING
    result: dict | None = None
    pending_approval: dict | None = None

    async def save(self) -> None:
        FakeNanobotAgentModel._docs[self.id] = self


class FakeNanobotAgentModel:
    _docs: dict[str, FakeAgentDoc] = {}

    @classmethod
    async def find_one(cls, query: dict[str, Any]) -> FakeAgentDoc | None:
        return cls._docs.get(query.get("_id"))


@pytest.fixture(autouse=True)
def _patch_model(monkeypatch: pytest.MonkeyPatch) -> Iterable[None]:
    FakeNanobotAgentModel._docs = {"a1": FakeAgentDoc(id="a1")}
    monkeypatch.setattr(service_module, "NanobotAgentModel", FakeNanobotAgentModel)
    # isolate locks/queues for each test
    service_module.AnalystService._sse_subscribers = {}
    service_module.AnalystService._sse_lock = asyncio.Lock()
    yield


@pytest.mark.asyncio
async def test_run_analysis_success_structured_result(monkeypatch: pytest.MonkeyPatch) -> None:
    bot = MagicMock()
    bot.run = AsyncMock(return_value=SimpleNamespace(content='{"summary":"x","success":true}', tools_used={"t"}))
    bot.close = AsyncMock()
    events: list[dict[str, Any]] = []

    async def _broadcast(agent_id: str, event: str, data: Any) -> None:
        events.append({"agent_id": agent_id, "event": event, "data": data})

    monkeypatch.setattr(service_module.AnalystService, "broadcast_sse", _broadcast)

    await service_module.AnalystService.run_analysis(
        agent_id="a1",
        session_id="s1",
        bot=bot,
        user_prompt="hi",
        context={},
    )
    doc = FakeNanobotAgentModel._docs["a1"]
    assert doc.status == NanobotAgentStatusEnum.COMPLETED
    assert doc.result and doc.result["parsed"] is True
    assert doc.result["summary"] == "x"
    # SSE result 事件里也应带 parsed=True
    result_events = [e for e in events if e["event"] == "result"]
    assert result_events
    assert result_events[-1]["data"]["result"]["parsed"] is True


@pytest.mark.asyncio
async def test_run_analysis_unparseable_result(monkeypatch: pytest.MonkeyPatch) -> None:
    bot = MagicMock()
    bot.run = AsyncMock(return_value=SimpleNamespace(content="not json", tools_used=set()))
    bot.close = AsyncMock()
    events: list[dict[str, Any]] = []

    async def _broadcast(agent_id: str, event: str, data: Any) -> None:
        events.append({"agent_id": agent_id, "event": event, "data": data})

    monkeypatch.setattr(service_module.AnalystService, "broadcast_sse", _broadcast)

    await service_module.AnalystService.run_analysis(
        agent_id="a1",
        session_id="s1",
        bot=bot,
        user_prompt="hi",
        context={},
    )
    doc = FakeNanobotAgentModel._docs["a1"]
    assert doc.status == NanobotAgentStatusEnum.COMPLETED
    assert doc.result and doc.result["parsed"] is False
    assert doc.result["success"] is False


@pytest.mark.asyncio
async def test_run_analysis_exception_result_shape(monkeypatch: pytest.MonkeyPatch) -> None:
    bot = MagicMock()

    async def _boom(*_a: Any, **_kw: Any) -> Any:
        raise RuntimeError("boom")

    bot.run = AsyncMock(side_effect=_boom)
    bot.close = AsyncMock()
    events: list[dict[str, Any]] = []

    async def _broadcast(agent_id: str, event: str, data: Any) -> None:
        events.append({"agent_id": agent_id, "event": event, "data": data})

    monkeypatch.setattr(service_module.AnalystService, "broadcast_sse", _broadcast)

    await service_module.AnalystService.run_analysis(
        agent_id="a1",
        session_id="s1",
        bot=bot,
        user_prompt="hi",
        context={},
    )
    doc = FakeNanobotAgentModel._docs["a1"]
    assert doc.status == NanobotAgentStatusEnum.FAILED
    assert doc.result and "error" in doc.result
    result_events = [e for e in events if e["event"] == "result"]
    assert result_events
    assert result_events[-1]["data"]["error"]

