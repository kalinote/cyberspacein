"""MIGRATION_PLAN §12.14：业务 Hooks（Status/Todos/Approval/Result）。"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Iterable
from unittest.mock import AsyncMock

import pytest

import app.service.analyst.hooks as hooks_module
import app.service.analyst.context as ctx
from app.schemas.constants import NanobotAgentStatusEnum
from app.service.nanobot.agent.hook import AgentHookContext


@dataclass
class FakeAgentDoc:
    id: str
    status: NanobotAgentStatusEnum = NanobotAgentStatusEnum.RUNNING
    steps: list[dict] = field(default_factory=list)
    todos: list[dict] = field(default_factory=list)
    pending_approval: dict | None = None
    updated_at: datetime = field(default_factory=datetime.now)

    async def save(self) -> None:
        FakeNanobotAgentModel._docs[self.id] = self


class FakeNanobotAgentModel:
    _docs: dict[str, FakeAgentDoc] = {}

    @classmethod
    async def find_one(cls, query: dict[str, Any]) -> FakeAgentDoc | None:
        return cls._docs.get(query.get("_id"))


@pytest.fixture(autouse=True)
def _patch_models(monkeypatch: pytest.MonkeyPatch) -> Iterable[None]:
    FakeNanobotAgentModel._docs = {}
    monkeypatch.setattr(hooks_module, "NanobotAgentModel", FakeNanobotAgentModel)
    yield


@pytest.mark.asyncio
async def test_status_hook_before_execute_tools_broadcasts(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[tuple[str, str, Any]] = []

    async def _broadcast(agent_id: str, event: str, data: Any) -> None:
        calls.append((agent_id, event, data))

    monkeypatch.setattr(hooks_module, "_load_current_agent", AsyncMock(return_value=None))
    monkeypatch.setattr(
        "app.service.analyst.service.AnalystService.broadcast_sse",
        _broadcast,
    )

    tok_a = ctx.current_agent_id.set("a1")
    tok_s = ctx.current_session_id.set("s1")
    try:
        # ToolCallRequest 只用到 name/arguments，直接用简单对象代替
        tool_calls = [
            type("TC", (), {"name": "t1", "arguments": {"x": 1}})(),
            type("TC", (), {"name": "t2", "arguments": {}})(),
        ]
        hook = hooks_module.StatusHook()
        await hook.before_execute_tools(
            AgentHookContext(iteration=1, messages=[], tool_calls=tool_calls)
        )
    finally:
        ctx.current_session_id.reset(tok_s)
        ctx.current_agent_id.reset(tok_a)

    assert calls and calls[0][0] == "a1" and calls[0][1] == "step"
    assert calls[0][2]["phase"] == "before_tools"
    assert calls[0][2]["session_id"] == "s1"
    assert calls[0][2]["tool_calls"][0]["name"] == "t1"


@pytest.mark.asyncio
async def test_status_hook_after_iteration_appends_step_and_broadcasts(monkeypatch: pytest.MonkeyPatch) -> None:
    FakeNanobotAgentModel._docs["a1"] = FakeAgentDoc(id="a1")
    calls: list[tuple[str, str, Any]] = []

    async def _broadcast(agent_id: str, event: str, data: Any) -> None:
        calls.append((agent_id, event, data))

    monkeypatch.setattr(
        "app.service.analyst.service.AnalystService.broadcast_sse",
        _broadcast,
    )

    tok_a = ctx.current_agent_id.set("a1")
    tok_s = ctx.current_session_id.set("s1")
    try:
        hook = hooks_module.StatusHook()
        ctx_obj = AgentHookContext(
            iteration=2,
            messages=[],
            response=type("R", (), {"content": "ok"})(),
            tool_calls=[type("TC", (), {"name": "t1", "arguments": {}})()],
            tool_events=[{"tool": "x"}],
            usage={"in": 1},
            stop_reason="stop",
        )
        await hook.after_iteration(ctx_obj)
    finally:
        ctx.current_session_id.reset(tok_s)
        ctx.current_agent_id.reset(tok_a)

    doc = FakeNanobotAgentModel._docs["a1"]
    assert len(doc.steps) == 1
    assert doc.steps[0]["iteration"] == 2
    assert calls and calls[0][1] == "step"
    assert calls[0][2]["phase"] == "after_iteration"


@pytest.mark.asyncio
async def test_todos_hook_noop_without_write_todos(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[Any] = []

    async def _broadcast(*_a: Any, **_kw: Any) -> None:
        calls.append(1)

    monkeypatch.setattr(
        "app.service.analyst.service.AnalystService.broadcast_sse",
        _broadcast,
    )
    tok_a = ctx.current_agent_id.set("a1")
    tok_s = ctx.current_session_id.set("s1")
    try:
        hook = hooks_module.TodosHook()
        await hook.after_iteration(AgentHookContext(iteration=1, messages=[], tool_events=[{"tool": "x"}]))
    finally:
        ctx.current_session_id.reset(tok_s)
        ctx.current_agent_id.reset(tok_a)

    assert calls == []


@pytest.mark.asyncio
async def test_todos_hook_broadcasts_when_touched() -> None:
    FakeNanobotAgentModel._docs["a1"] = FakeAgentDoc(id="a1", todos=[{"id": "t"}])
    calls: list[tuple[str, str, Any]] = []

    async def _broadcast(agent_id: str, event: str, data: Any) -> None:
        calls.append((agent_id, event, data))

    # patch 目标方法（hooks.py 内部 import）
    import app.service.analyst.service as service_module
    monkeypatch = pytest.MonkeyPatch()
    monkeypatch.setattr(service_module.AnalystService, "broadcast_sse", _broadcast)

    tok_a = ctx.current_agent_id.set("a1")
    tok_s = ctx.current_session_id.set("s1")
    try:
        hook = hooks_module.TodosHook()
        await hook.after_iteration(
            AgentHookContext(iteration=1, messages=[], tool_events=[{"tool": "write_todos"}])
        )
    finally:
        ctx.current_session_id.reset(tok_s)
        ctx.current_agent_id.reset(tok_a)
        monkeypatch.undo()

    assert calls and calls[0][1] == "todos"
    assert calls[0][2]["todos"] == [{"id": "t"}]


@pytest.mark.asyncio
async def test_approval_hook_resets_pending_when_advanced() -> None:
    FakeNanobotAgentModel._docs["a1"] = FakeAgentDoc(
        id="a1",
        status=NanobotAgentStatusEnum.AWAITING_APPROVAL,
        pending_approval={"x": 1},
    )
    tok_a = ctx.current_agent_id.set("a1")
    try:
        hook = hooks_module.ApprovalHook()
        await hook.after_iteration(
            AgentHookContext(iteration=1, messages=[], stop_reason="stop")
        )
    finally:
        ctx.current_agent_id.reset(tok_a)

    doc = FakeNanobotAgentModel._docs["a1"]
    assert doc.status == NanobotAgentStatusEnum.RUNNING
    assert doc.pending_approval is None


def test_result_hook_strips() -> None:
    hook = hooks_module.ResultHook()
    out = hook.finalize_content(AgentHookContext(iteration=1, messages=[]), "  ok \n")
    assert out == "ok"


def test_default_analyst_hooks_shape() -> None:
    hooks = hooks_module.default_analyst_hooks()
    assert [type(h).__name__ for h in hooks] == [
        "StatusHook",
        "TodosHook",
        "ApprovalHook",
        "ResultHook",
    ]

