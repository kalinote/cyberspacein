"""MIGRATION_PLAN §12.13：AnalystService 核心能力（ContextVar / SSE / HITL / run_analysis）。"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from datetime import datetime
from types import SimpleNamespace
from typing import Any, Iterable
from unittest.mock import AsyncMock, MagicMock

import pytest

import app.utils.status_codes as status_codes
import app.service.analyst.context as ctx
import app.service.analyst.hitl as hitl_module
import app.service.analyst.service as service_module
from app.schemas.agent.nanobot_agent import AgentServiceError
from app.schemas.constants import NanobotSessionStatusEnum


@dataclass
class FakeSessionDoc:
    id: str
    agent_id: str = "a1"
    status: NanobotSessionStatusEnum = NanobotSessionStatusEnum.IDLE
    active_run_id: str | None = None
    steps: list[dict] = field(default_factory=list)
    todos: list[dict] = field(default_factory=list)
    pending_approval: dict | None = None
    result: dict | None = None
    task_submissions: list[dict] = field(default_factory=list)
    error_message: str | None = None
    finished_at: datetime | None = None
    updated_at: datetime = field(default_factory=datetime.now)

    async def save(self) -> None:
        FakeNanobotSessionModel._docs[self.id] = self


class FakeNanobotSessionModel:
    _docs: dict[str, FakeSessionDoc] = {}

    @classmethod
    async def find_one(cls, query: dict[str, Any]) -> FakeSessionDoc | None:
        return cls._docs.get(query.get("_id"))


@pytest.fixture(autouse=True)
def _reset_singletons(monkeypatch: pytest.MonkeyPatch) -> Iterable[None]:
    service_module.AnalystService._bots = {}
    service_module.AnalystService._sse_subscribers = {}
    service_module.AnalystService._running_tasks = {}
    service_module.AnalystService._cancel_reasons = {}
    service_module.AnalystService._memory_backend = None
    service_module.AnalystService._session_store = None
    service_module.AnalystService._bots_lock = asyncio.Lock()
    service_module.AnalystService._sse_lock = asyncio.Lock()
    service_module.AnalystService._task_lock = asyncio.Lock()
    hitl_module.HitlService._pending_resumes = {}
    hitl_module.HitlService._resume_lock = asyncio.Lock()

    FakeNanobotSessionModel._docs = {}
    monkeypatch.setattr(hitl_module, "NanobotSessionModel", FakeNanobotSessionModel)
    monkeypatch.setattr(service_module, "NanobotSessionModel", FakeNanobotSessionModel)
    monkeypatch.setattr(service_module.AnalystService, "_persist_sse_event", AsyncMock())
    monkeypatch.setattr(service_module.AnalystService, "_load_replay_events", AsyncMock(return_value=[]))
    monkeypatch.setattr(service_module.AnalystService, "_build_session_fallback_replay", AsyncMock(return_value=[]))
    monkeypatch.setattr(service_module.AnalystService, "_latest_persisted_sse_seq", AsyncMock(return_value=0))
    monkeypatch.setattr(service_module.AnalystService, "_flush_stream_buffer", AsyncMock())
    monkeypatch.setattr(service_module.AnalystService, "_flush_reasoning_stream_buffer", AsyncMock())
    monkeypatch.setattr(service_module.AnalystEventBus, "prepare_subscription", AsyncMock(return_value=None))
    monkeypatch.setattr(service_module.AnalystEventBus, "publish", AsyncMock(return_value=False))
    yield


def test_context_set_reset() -> None:
    assert ctx.get_current_agent_id() is None
    assert ctx.get_current_session_id() is None
    t1 = ctx.current_agent_id.set("a1")
    t2 = ctx.current_session_id.set("s1")
    try:
        assert ctx.get_current_agent_id() == "a1"
        assert ctx.get_current_session_id() == "s1"
    finally:
        ctx.current_session_id.reset(t2)
        ctx.current_agent_id.reset(t1)
    assert ctx.get_current_agent_id() is None
    assert ctx.get_current_session_id() is None


@pytest.mark.asyncio
async def test_context_isolation_between_tasks() -> None:
    async def _worker(agent_id: str) -> str:
        token = ctx.current_agent_id.set(agent_id)
        try:
            await asyncio.sleep(0)
            return ctx.get_current_agent_id() or ""
        finally:
            ctx.current_agent_id.reset(token)

    a, b = await asyncio.gather(_worker("a1"), _worker("a2"))
    assert a == "a1"
    assert b == "a2"
    assert ctx.get_current_agent_id() is None


@pytest.mark.asyncio
async def test_sse_subscribe_and_broadcast() -> None:
    FakeNanobotSessionModel._docs["s1"] = FakeSessionDoc(id="s1", agent_id="a1")
    q = await service_module.AnalystService.subscribe("a1", "s1")
    await service_module.AnalystService.broadcast_sse(
        "a1", "status", {"session_id": "s1", "x": 1}
    )
    got = await asyncio.wait_for(q.get(), timeout=1.0)
    assert got["event"] == "status"
    assert got["data"] == {"session_id": "s1", "x": 1}


@pytest.mark.asyncio
async def test_sse_multiple_subscribers() -> None:
    FakeNanobotSessionModel._docs["s1"] = FakeSessionDoc(id="s1", agent_id="a1")
    q1 = await service_module.AnalystService.subscribe("a1", "s1")
    q2 = await service_module.AnalystService.subscribe("a1", "s1")
    await service_module.AnalystService.broadcast_sse(
        "a1", "msg", {"session_id": "s1", "ok": True}
    )
    got1 = await asyncio.wait_for(q1.get(), timeout=1.0)
    got2 = await asyncio.wait_for(q2.get(), timeout=1.0)
    assert got1 == got2

    await service_module.AnalystService.unsubscribe("a1", "s1", q1)
    await service_module.AnalystService.broadcast_sse(
        "a1", "msg2", {"session_id": "s1", "v": 2}
    )
    got2b = await asyncio.wait_for(q2.get(), timeout=1.0)
    assert got2b["event"] == "msg2"


@pytest.mark.asyncio
async def test_sse_unsubscribe_cleans_subs_map() -> None:
    FakeNanobotSessionModel._docs["s1"] = FakeSessionDoc(id="s1", agent_id="a1")
    q = await service_module.AnalystService.subscribe("a1", "s1")
    await service_module.AnalystService.unsubscribe("a1", "s1", q)
    assert ("a1", "s1") not in service_module.AnalystService._sse_subscribers


@pytest.mark.asyncio
async def test_submit_approval_puts_queue() -> None:
    from app.service.analyst.hitl import HitlService

    await HitlService.clear_session("s1")
    FakeNanobotSessionModel._docs["s1"] = FakeSessionDoc(
        id="s1",
        agent_id="a1",
        status=NanobotSessionStatusEnum.AWAITING_APPROVAL,
        pending_approval={"approval_request_id": "req-1"},
    )
    decisions = [{"id": "x", "approve": True}]
    await service_module.AnalystService.submit_approval(
        "a1", "s1", "req-1", decisions
    )
    payload = await HitlService._await_decisions("s1")
    assert payload["decisions"] == decisions
    assert "submitted_at" in payload


@pytest.mark.asyncio
async def test_submit_approval_not_found_session() -> None:
    with pytest.raises(AgentServiceError) as e:
        await service_module.AnalystService.submit_approval(
            "a1", "missing", "req-1", []
        )
    assert e.value.code == status_codes.NOT_FOUND_AGENT


@pytest.mark.asyncio
async def test_submit_approval_non_awaiting_rejected() -> None:
    FakeNanobotSessionModel._docs["s1"] = FakeSessionDoc(
        id="s1",
        agent_id="a1",
        status=NanobotSessionStatusEnum.RUNNING,
    )
    with pytest.raises(AgentServiceError) as exc_info:
        await service_module.AnalystService.submit_approval(
            "a1", "s1", "req-1", [{"id": "x"}]
        )
    assert exc_info.value.code == status_codes.CONFLICT_STATE


@pytest.mark.asyncio
async def test_run_analysis_success_sets_result_and_resets_context(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    FakeNanobotSessionModel._docs["s1"] = FakeSessionDoc(id="s1", agent_id="a1")
    bot = MagicMock()
    bot.loop.process_direct = None
    bot.close = AsyncMock()

    async def _run_ok(*_a: Any, **_kw: Any) -> Any:
        ctx.current_task_completion.set(
            {
                "id": "sub-1",
                "success": True,
                "failure_reason": None,
                "short_summary": "完成",
                "payload": {"k": 1},
                "submitted_at": datetime.now().isoformat(),
            }
        )
        return SimpleNamespace(
            content="用户总结",
            tools_used=["submit_task_result"],
            stop_reason="completed",
        )

    bot.run = AsyncMock(side_effect=_run_ok)

    await service_module.AnalystService.run_analysis(
        agent_id="a1",
        session_id="s1",
        bot=bot,
        user_prompt="hi",
        context={},
    )
    doc = FakeNanobotSessionModel._docs["s1"]
    assert doc.status == NanobotSessionStatusEnum.COMPLETED
    assert doc.result and doc.result.get("completion_received") is True
    assert doc.result.get("success") is True
    assert doc.result.get("user_markdown") == "用户总结"
    assert ctx.get_current_agent_id() is None
    assert ctx.get_current_session_id() is None
    assert ctx.get_current_task_completion() is None
    bot.close.assert_awaited()


@pytest.mark.asyncio
async def test_run_analysis_without_submit_marks_completed(monkeypatch: pytest.MonkeyPatch) -> None:
    FakeNanobotSessionModel._docs["s1"] = FakeSessionDoc(id="s1", agent_id="a1")
    bot = MagicMock()
    bot.loop.process_direct = None
    bot.run = AsyncMock(
        return_value=SimpleNamespace(content="直接回复", tools_used=[], stop_reason="completed")
    )
    bot.close = AsyncMock()

    await service_module.AnalystService.run_analysis(
        agent_id="a1",
        session_id="s1",
        bot=bot,
        user_prompt="hi",
        context={},
    )
    doc = FakeNanobotSessionModel._docs["s1"]
    assert doc.status == NanobotSessionStatusEnum.COMPLETED
    assert doc.result and doc.result.get("completion_received") is False
    assert doc.result.get("success") is True
    assert doc.result.get("user_markdown") == "直接回复"


@pytest.mark.asyncio
async def test_run_analysis_submit_failure_marks_failed(monkeypatch: pytest.MonkeyPatch) -> None:
    FakeNanobotSessionModel._docs["s1"] = FakeSessionDoc(id="s1", agent_id="a1")
    bot = MagicMock()
    bot.loop.process_direct = None
    bot.close = AsyncMock()

    async def _run_fail(*_a: Any, **_kw: Any) -> Any:
        ctx.current_task_completion.set(
            {
                "id": "sub-fail",
                "success": False,
                "failure_reason": "无法完成",
                "short_summary": "失败",
                "payload": {},
                "submitted_at": datetime.now().isoformat(),
            }
        )
        return SimpleNamespace(content="说明", tools_used=["submit_task_result"], stop_reason="completed")

    bot.run = AsyncMock(side_effect=_run_fail)

    await service_module.AnalystService.run_analysis(
        agent_id="a1",
        session_id="s1",
        bot=bot,
        user_prompt="hi",
        context={},
    )
    doc = FakeNanobotSessionModel._docs["s1"]
    assert doc.status == NanobotSessionStatusEnum.FAILED
    assert doc.result and doc.result.get("completion_received") is True
    assert doc.result.get("success") is False


@pytest.mark.asyncio
async def test_run_analysis_closes_bot_on_any_exit(monkeypatch: pytest.MonkeyPatch) -> None:
    FakeNanobotSessionModel._docs["s1"] = FakeSessionDoc(id="s1", agent_id="a1")
    bot = MagicMock()
    bot.loop.process_direct = None
    bot.close = AsyncMock()

    async def _boom(*_a: Any, **_kw: Any) -> Any:
        raise RuntimeError("boom")

    bot.run = AsyncMock(side_effect=_boom)
    await service_module.AnalystService.run_analysis(
        agent_id="a1",
        session_id="s1",
        bot=bot,
        user_prompt="hi",
        context={},
    )
    bot.close.assert_awaited()
    assert FakeNanobotSessionModel._docs["s1"].status == NanobotSessionStatusEnum.FAILED


@pytest.mark.asyncio
async def test_run_analysis_cancelled_pause_sets_paused(monkeypatch: pytest.MonkeyPatch) -> None:
    FakeNanobotSessionModel._docs["s1"] = FakeSessionDoc(id="s1", agent_id="a1")
    bot = MagicMock()
    bot.loop.process_direct = None

    async def _raise_cancel(*_a: Any, **_kw: Any) -> Any:
        raise asyncio.CancelledError()

    bot.run = AsyncMock(side_effect=_raise_cancel)
    bot.close = AsyncMock()
    service_module.AnalystService._cancel_reasons["s1"] = "pause"

    with pytest.raises(asyncio.CancelledError):
        await service_module.AnalystService.run_analysis(
            agent_id="a1",
            session_id="s1",
            bot=bot,
            user_prompt="hi",
            context={},
        )
    doc = FakeNanobotSessionModel._docs["s1"]
    assert doc.status == NanobotSessionStatusEnum.PAUSED
    bot.close.assert_awaited()


@pytest.mark.asyncio
async def test_cancel_agent_calls_subagent_cancel_by_session() -> None:
    FakeNanobotSessionModel._docs["s1"] = FakeSessionDoc(id="s1", agent_id="a1")
    bot = MagicMock()
    bot.loop.subagents.cancel_by_session = AsyncMock(return_value=0)

    async def _hang() -> None:
        await asyncio.sleep(3600)

    task = asyncio.create_task(_hang())
    async with service_module.AnalystService._bots_lock:
        service_module.AnalystService._bots["s1"] = bot
    async with service_module.AnalystService._task_lock:
        service_module.AnalystService._running_tasks["s1"] = task

    ok = await service_module.AnalystService.cancel_agent("a1", "s1")
    assert ok is True
    bot.loop.subagents.cancel_by_session.assert_awaited_once_with("s1")
    with pytest.raises(asyncio.CancelledError):
        await task


@pytest.mark.asyncio
async def test_cancel_agent_subagent_cleanup_error_still_cancels_task() -> None:
    FakeNanobotSessionModel._docs["s1"] = FakeSessionDoc(id="s1", agent_id="a1")
    bot = MagicMock()
    bot.loop.subagents.cancel_by_session = AsyncMock(side_effect=RuntimeError("boom"))

    async def _hang() -> None:
        await asyncio.sleep(3600)

    task = asyncio.create_task(_hang())
    async with service_module.AnalystService._bots_lock:
        service_module.AnalystService._bots["s1"] = bot
    async with service_module.AnalystService._task_lock:
        service_module.AnalystService._running_tasks["s1"] = task

    ok = await service_module.AnalystService.cancel_agent("a1", "s1")
    assert ok is True
    with pytest.raises(asyncio.CancelledError):
        await task
