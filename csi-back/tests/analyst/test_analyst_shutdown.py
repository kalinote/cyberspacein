"""AnalystService 进程退出时的优雅关闭。"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Iterable
from unittest.mock import AsyncMock, MagicMock

import pytest

import app.service.analyst.hitl as hitl_module
import app.service.analyst.service as service_module
from app.schemas.constants import NanobotSessionStatusEnum


@dataclass
class FakeSessionDoc:
    id: str
    agent_id: str = "a1"
    status: NanobotSessionStatusEnum = NanobotSessionStatusEnum.RUNNING
    steps: list[dict] = field(default_factory=list)
    todos: list[dict] = field(default_factory=list)
    pending_approval: dict | None = None
    result: dict | None = None
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
    yield


@pytest.mark.asyncio
async def test_shutdown_empty_noop() -> None:
    await service_module.AnalystService.shutdown_running_agents(timeout=1.0)


@pytest.mark.asyncio
async def test_shutdown_clears_hitl_queues() -> None:
    hitl_module.HitlService._pending_resumes["s1"] = asyncio.Queue()
    await service_module.AnalystService.shutdown_running_agents(timeout=1.0)
    assert hitl_module.HitlService._pending_resumes == {}


@pytest.mark.asyncio
async def test_shutdown_cancels_hanging_run_analysis() -> None:
    FakeNanobotSessionModel._docs["s1"] = FakeSessionDoc(id="s1", agent_id="a1")
    bot = MagicMock()
    bot.agent_id = "a1"
    bot.loop.process_direct = None
    bot.loop.model = "test-model"
    bot.loop.subagents.cancel_by_session = AsyncMock(return_value=0)
    bot.loop.context.refresh_memory_snapshot = AsyncMock()
    bot.loop.context.build_system_prompt = MagicMock(return_value="sys")
    bot.loop.context.extra_system_suffix = ""
    bot.loop.context.snapshot = MagicMock(
        memory="", soul="", user="", recent_history=[]
    )

    async def _hang(*_a: Any, **_kw: Any) -> None:
        await asyncio.sleep(3600)

    bot.run = AsyncMock(side_effect=_hang)
    bot.close = AsyncMock()

    task = asyncio.create_task(
        service_module.AnalystService.run_analysis(
            agent_id="a1",
            session_id="s1",
            bot=bot,
            user_prompt="hi",
            context={},
        ),
        name="analyst-run:a1:s1",
    )
    async with service_module.AnalystService._bots_lock:
        service_module.AnalystService._bots["s1"] = bot
    async with service_module.AnalystService._task_lock:
        service_module.AnalystService._running_tasks["s1"] = task

    await asyncio.sleep(0.05)
    await service_module.AnalystService.shutdown_running_agents(timeout=2.0)

    with pytest.raises(asyncio.CancelledError):
        await task
    bot.close.assert_awaited()
    doc = FakeNanobotSessionModel._docs["s1"]
    assert doc.status == NanobotSessionStatusEnum.CANCELLED


@pytest.mark.asyncio
async def test_shutdown_cancels_orphan_task_without_session_doc() -> None:
    async def _hang() -> None:
        await asyncio.sleep(3600)

    task = asyncio.create_task(_hang(), name="analyst-run:a1:s1")
    async with service_module.AnalystService._task_lock:
        service_module.AnalystService._running_tasks["s1"] = task

    await service_module.AnalystService.shutdown_running_agents(timeout=2.0)

    assert task.done()
    with pytest.raises(asyncio.CancelledError):
        await task
