"""双会话：StatusHook 按 ContextVar 隔离 steps；cancel_agent 仅触碰目标 session 的子代理。"""

from __future__ import annotations

from dataclasses import dataclass, field
from types import SimpleNamespace
from typing import Any, Iterable
from unittest.mock import AsyncMock

import pytest

import app.service.analyst.hooks as hooks_module
import app.service.analyst.service as service_module
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

    @classmethod
    def get_motor_collection(cls) -> Any:
        class _Collection:
            async def update_one(
                self, query: dict[str, Any], update: dict[str, Any]
            ) -> Any:
                doc = cls._docs.get(query.get("_id"))
                if doc is None:
                    return SimpleNamespace(matched_count=0)
                for field_name, value in update.get("$push", {}).items():
                    getattr(doc, field_name).append(value)
                return SimpleNamespace(matched_count=1)

        return _Collection()


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
