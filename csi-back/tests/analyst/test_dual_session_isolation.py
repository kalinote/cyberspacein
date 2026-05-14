"""双会话：StatusHook 按 ContextVar 隔离 steps；cancel_agent 仅触碰目标 session 的子代理。"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from typing import Any, Iterable
from unittest.mock import AsyncMock, MagicMock

import pytest

import app.service.analyst.hooks as hooks_module
import app.service.analyst.service as service_module
from app.schemas.constants import NanobotSessionStatusEnum
from app.service.analyst.context import current_agent_id, current_session_id
from app.service.analyst.hooks import StatusHook
from app.service.nanobot.agent.hook import AgentHookContext


@dataclass
class FakeSessionDoc:
    id: str
    agent_id: str = "a1"
    steps: list[dict] = field(default_factory=list)

    async def save(self) -> None:
        FakeNanobotSessionModel._docs[self.id] = self


class FakeNanobotSessionModel:
    _docs: dict[str, FakeSessionDoc] = {}

    @classmethod
    async def find_one(cls, query: dict[str, Any]) -> FakeSessionDoc | None:
        return cls._docs.get(query.get("_id"))


@pytest.fixture
def _patch_session_model(monkeypatch: pytest.MonkeyPatch) -> Iterable[None]:
    monkeypatch.setattr(hooks_module, "NanobotSessionModel", FakeNanobotSessionModel)
    FakeNanobotSessionModel._docs = {
        "sa": FakeSessionDoc(id="sa"),
        "sb": FakeSessionDoc(id="sb"),
    }
    yield


@pytest.mark.asyncio
async def test_status_hook_steps_isolated_per_session(
    monkeypatch: pytest.MonkeyPatch, _patch_session_model: None
) -> None:
    monkeypatch.setattr(service_module.AnalystService, "broadcast_sse", AsyncMock())

    hook = StatusHook()
    ctx_a = AgentHookContext(iteration=0, messages=[])
    ctx_b = AgentHookContext(iteration=1, messages=[])

    ta = current_agent_id.set("a1")
    ts_a = current_session_id.set("sa")
    try:
        await hook.after_iteration(ctx_a)
    finally:
        current_session_id.reset(ts_a)
        current_agent_id.reset(ta)

    ts_b = current_session_id.set("sb")
    ta2 = current_agent_id.set("a1")
    try:
        await hook.after_iteration(ctx_b)
    finally:
        current_session_id.reset(ts_b)
        current_agent_id.reset(ta2)

    sa = FakeNanobotSessionModel._docs["sa"]
    sb = FakeNanobotSessionModel._docs["sb"]
    assert len(sa.steps) == 1
    assert len(sb.steps) == 1
    assert sa.steps[0]["iteration"] == 0
    assert sb.steps[0]["iteration"] == 1


@pytest.mark.asyncio
async def test_cancel_agent_only_triggers_subagent_cancel_for_target_session(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    @dataclass
    class Sess:
        id: str
        agent_id: str = "a1"
        status: NanobotSessionStatusEnum = NanobotSessionStatusEnum.RUNNING

    class FakeSessModel:
        @staticmethod
        async def find_one(query: dict[str, Any]) -> Sess | None:
            sid = query.get("_id")
            if sid == "s1":
                return Sess(id="s1")
            if sid == "s2":
                return Sess(id="s2")
            return None

    monkeypatch.setattr(service_module, "NanobotSessionModel", FakeSessModel)

    bot1 = MagicMock()
    bot1.loop.subagents.cancel_by_session = AsyncMock(return_value=0)
    bot2 = MagicMock()
    bot2.loop.subagents.cancel_by_session = AsyncMock(return_value=0)

    async def hang() -> None:
        await asyncio.sleep(3600)

    t1 = asyncio.create_task(hang())
    t2 = asyncio.create_task(hang())

    service_module.AnalystService._bots_lock = asyncio.Lock()
    service_module.AnalystService._task_lock = asyncio.Lock()
    async with service_module.AnalystService._bots_lock:
        service_module.AnalystService._bots["s1"] = bot1
        service_module.AnalystService._bots["s2"] = bot2
    async with service_module.AnalystService._task_lock:
        service_module.AnalystService._running_tasks["s1"] = t1
        service_module.AnalystService._running_tasks["s2"] = t2

    ok = await service_module.AnalystService.cancel_agent("a1", "s1")
    assert ok is True
    bot1.loop.subagents.cancel_by_session.assert_awaited_once_with("s1")
    bot2.loop.subagents.cancel_by_session.assert_not_called()

    with pytest.raises(asyncio.CancelledError):
        await t1
    t2.cancel()
    with pytest.raises(asyncio.CancelledError):
        await t2
