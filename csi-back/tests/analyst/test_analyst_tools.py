"""MIGRATION_PLAN §12.15：业务工具（tools.py）。"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime
from types import SimpleNamespace
from typing import Any, Iterable
from unittest.mock import AsyncMock

import pytest

import app.service.analyst.context as ctx
import app.service.analyst.service as service_module
import app.service.analyst.tools as tools_module
from app.schemas.constants import EntityType, NanobotAgentStatusEnum


@dataclass
class FakeAgentDoc:
    id: str
    workspace_id: str = "w1"
    status: NanobotAgentStatusEnum = NanobotAgentStatusEnum.RUNNING
    pending_approval: dict | None = None
    todos: list[dict] = field(default_factory=list)
    current_session_id: str | None = None
    updated_at: datetime = field(default_factory=datetime.now)

    async def save(self) -> None:
        FakeNanobotAgentModel._docs[self.id] = self


class FakeNanobotAgentModel:
    _docs: dict[str, FakeAgentDoc] = {}

    @classmethod
    async def find_one(cls, query: dict[str, Any]) -> FakeAgentDoc | None:
        return cls._docs.get(query.get("_id"))


@pytest.fixture(autouse=True)
def _patch_agent_model(monkeypatch: pytest.MonkeyPatch) -> Iterable[None]:
    FakeNanobotAgentModel._docs = {}
    monkeypatch.setattr(tools_module, "NanobotAgentModel", FakeNanobotAgentModel)
    yield


def _set_agent_ctx(agent_id: str = "a1", session_id: str = "s1") -> tuple[Any, Any]:
    t1 = ctx.current_agent_id.set(agent_id)
    t2 = ctx.current_session_id.set(session_id)
    return t1, t2


def _reset_agent_ctx(tokens: tuple[Any, Any]) -> None:
    t1, t2 = tokens
    ctx.current_session_id.reset(t2)
    ctx.current_agent_id.reset(t1)


def test_tool_schemas_valid() -> None:
    for name, cls in tools_module.BUSINESS_TOOL_CLASSES.items():
        tool = cls()
        schema = tool.to_schema()
        json.dumps(schema, ensure_ascii=False)
        assert schema["type"] == "function"
        assert schema["function"]["name"] == tool.name == name


def test_build_business_tools_whitelist(monkeypatch: pytest.MonkeyPatch) -> None:
    warns: list[str] = []
    monkeypatch.setattr(tools_module.logger, "warning", lambda msg: warns.append(str(msg)))
    tools = tools_module.build_business_tools(["notify_user", "write_todos", "unknown"])
    assert [t.name for t in tools] == ["notify_user", "write_todos"]
    assert warns and "unknown" in warns[0]


@pytest.mark.asyncio
async def test_get_current_time_returns_iso() -> None:
    out = await tools_module.GetCurrentTimeTool().execute()
    datetime.fromisoformat(out)


@pytest.mark.asyncio
async def test_get_entity_missing_type() -> None:
    out = await tools_module.GetEntityTool().execute(entity_type="x", entity_uuid="1")
    assert "不支持的实体类型" in out


@pytest.mark.asyncio
async def test_get_entity_es_not_initialized(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("app.db.elasticsearch.get_es", lambda: None)
    out = await tools_module.GetEntityTool().execute(entity_type=EntityType.ARTICLE.value, entity_uuid="1")
    assert "Elasticsearch 未初始化" in out


@pytest.mark.asyncio
async def test_get_entity_success(monkeypatch: pytest.MonkeyPatch) -> None:
    class _ES:
        async def get(self, *, index: str, id: str):
            assert index == "article" and id == "1"
            return {"_source": {"k": "v"}}

    monkeypatch.setattr("app.db.elasticsearch.get_es", lambda: _ES())
    out = await tools_module.GetEntityTool().execute(entity_type=EntityType.ARTICLE.value, entity_uuid="1")
    assert "{'k': 'v'}" in out


@pytest.mark.asyncio
async def test_get_entity_es_exception_returns_error_str(monkeypatch: pytest.MonkeyPatch) -> None:
    class _ES:
        async def get(self, *, index: str, id: str):
            raise RuntimeError("boom")

    monkeypatch.setattr("app.db.elasticsearch.get_es", lambda: _ES())
    out = await tools_module.GetEntityTool().execute(entity_type=EntityType.ARTICLE.value, entity_uuid="1")
    assert out.startswith("[错误] 查询实体失败:")


@pytest.mark.asyncio
async def test_tool_requires_context_var() -> None:
    with pytest.raises(RuntimeError):
        await tools_module.WriteTodosTool().execute(todos=[])


@pytest.mark.asyncio
async def test_write_todos_updates_db_and_broadcasts(monkeypatch: pytest.MonkeyPatch) -> None:
    FakeNanobotAgentModel._docs["a1"] = FakeAgentDoc(id="a1")
    tokens = _set_agent_ctx()
    calls: list[tuple[str, str, Any]] = []

    async def _broadcast(agent_id: str, event: str, data: Any) -> None:
        calls.append((agent_id, event, data))

    monkeypatch.setattr(service_module.AnalystService, "broadcast_sse", _broadcast)
    try:
        out = await tools_module.WriteTodosTool().execute(
            todos=[{"content": "x", "status": "pending"}]
        )
    finally:
        _reset_agent_ctx(tokens)

    assert "已更新待办 1 条" in out
    assert FakeNanobotAgentModel._docs["a1"].todos[0]["content"] == "x"
    assert calls and calls[0][1] == "todos"
    assert calls[0][2]["todos"][0]["status"] == "pending"


@pytest.mark.asyncio
async def test_write_todos_normalizes_fields(monkeypatch: pytest.MonkeyPatch) -> None:
    FakeNanobotAgentModel._docs["a1"] = FakeAgentDoc(id="a1")
    tokens = _set_agent_ctx()
    monkeypatch.setattr(service_module.AnalystService, "broadcast_sse", AsyncMock())
    try:
        await tools_module.WriteTodosTool().execute(
            todos=[{"id": 1, "content": "  hello  ", "status": "completed", "x": "y"}]
        )
    finally:
        _reset_agent_ctx(tokens)
    todo = FakeNanobotAgentModel._docs["a1"].todos[0]
    assert set(todo.keys()) == {"id", "content", "status", "updated_at"}
    assert todo["id"] == "1"
    assert todo["content"] == "hello"


@pytest.mark.asyncio
async def test_write_todos_agent_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    tokens = _set_agent_ctx(agent_id="missing")
    monkeypatch.setattr(service_module.AnalystService, "broadcast_sse", AsyncMock())
    try:
        out = await tools_module.WriteTodosTool().execute(todos=[])
    finally:
        _reset_agent_ctx(tokens)
    assert "当前 agent 不存在" in out


@pytest.mark.asyncio
async def test_notify_user_broadcasts(monkeypatch: pytest.MonkeyPatch) -> None:
    tokens = _set_agent_ctx()
    calls: list[tuple[str, str, Any]] = []

    async def _broadcast(agent_id: str, event: str, data: Any) -> None:
        calls.append((agent_id, event, data))

    monkeypatch.setattr(service_module.AnalystService, "broadcast_sse", _broadcast)
    try:
        out = await tools_module.NotifyUserTool().execute(message="hi", level="warning")
    finally:
        _reset_agent_ctx(tokens)
    assert out == "通知已发送"
    assert calls and calls[0][1] == "notification"
    assert calls[0][2]["level"] == "warning"
    assert calls[0][2]["message"] == "hi"


@pytest.mark.asyncio
async def test_notify_user_empty_message(monkeypatch: pytest.MonkeyPatch) -> None:
    tokens = _set_agent_ctx()
    monkeypatch.setattr(service_module.AnalystService, "broadcast_sse", AsyncMock())
    try:
        out = await tools_module.NotifyUserTool().execute(message="   ")
    finally:
        _reset_agent_ctx(tokens)
    assert "message 不能为空" in out


@pytest.mark.asyncio
async def test_modify_entity_handshake_approve(monkeypatch: pytest.MonkeyPatch) -> None:
    FakeNanobotAgentModel._docs["a1"] = FakeAgentDoc(id="a1")
    tokens = _set_agent_ctx()
    calls: list[tuple[str, str, Any]] = []

    async def _broadcast(agent_id: str, event: str, data: Any) -> None:
        calls.append((agent_id, event, data))

    async def _await(_agent_id: str) -> dict:
        return {"decisions": [{"action": "approve"}]}

    monkeypatch.setattr(service_module.AnalystService, "broadcast_sse", _broadcast)
    monkeypatch.setattr(service_module.AnalystService, "await_approval", _await)
    try:
        out = await tools_module.ModifyEntityTool().execute(
            entity_type=EntityType.ARTICLE.value,
            entity_uuid="u1",
            modifications=[{"field": "x", "action": "set", "value": 1}],
            reason="r",
        )
    finally:
        _reset_agent_ctx(tokens)

    assert "修改已获批准" in out
    assert FakeNanobotAgentModel._docs["a1"].status == NanobotAgentStatusEnum.RUNNING
    assert FakeNanobotAgentModel._docs["a1"].pending_approval is None
    events = [c[1] for c in calls]
    assert "approval_required" in events
    assert events.count("status") >= 2


@pytest.mark.asyncio
async def test_modify_entity_handshake_reject(monkeypatch: pytest.MonkeyPatch) -> None:
    FakeNanobotAgentModel._docs["a1"] = FakeAgentDoc(id="a1")
    tokens = _set_agent_ctx()
    monkeypatch.setattr(service_module.AnalystService, "broadcast_sse", AsyncMock())
    monkeypatch.setattr(
        service_module.AnalystService,
        "await_approval",
        AsyncMock(return_value={"decisions": [{"action": "reject", "reason": "bad"}]}),
    )
    try:
        out = await tools_module.ModifyEntityTool().execute(
            entity_type=EntityType.ARTICLE.value,
            entity_uuid="u1",
            modifications=[{"field": "x", "action": "set"}],
            reason="r",
        )
    finally:
        _reset_agent_ctx(tokens)
    assert out == "修改被拒绝：bad"


@pytest.mark.asyncio
async def test_modify_entity_empty_decisions(monkeypatch: pytest.MonkeyPatch) -> None:
    FakeNanobotAgentModel._docs["a1"] = FakeAgentDoc(id="a1")
    tokens = _set_agent_ctx()
    monkeypatch.setattr(service_module.AnalystService, "broadcast_sse", AsyncMock())
    monkeypatch.setattr(service_module.AnalystService, "await_approval", AsyncMock(return_value={"decisions": []}))
    try:
        out = await tools_module.ModifyEntityTool().execute(
            entity_type=EntityType.ARTICLE.value,
            entity_uuid="u1",
            modifications=[{"field": "x", "action": "set"}],
            reason="r",
        )
    finally:
        _reset_agent_ctx(tokens)
    assert out == "修改未获得任何批准，未执行。"


def test_modify_entity_decision_parser_variants() -> None:
    approved, rejections = tools_module._parse_approval_decisions(
        [{"action": "approve"}, {"approved": True}, {"action": "reject", "reason": "bad"}]
    )
    assert len(approved) == 2
    assert rejections == ["bad"]


@pytest.mark.asyncio
async def test_modify_entity_await_exception_returns(monkeypatch: pytest.MonkeyPatch) -> None:
    FakeNanobotAgentModel._docs["a1"] = FakeAgentDoc(id="a1")
    tokens = _set_agent_ctx()
    monkeypatch.setattr(service_module.AnalystService, "broadcast_sse", AsyncMock())

    async def _boom(_agent_id: str) -> dict:
        raise RuntimeError("x")

    monkeypatch.setattr(service_module.AnalystService, "await_approval", _boom)
    try:
        out = await tools_module.ModifyEntityTool().execute(
            entity_type=EntityType.ARTICLE.value,
            entity_uuid="u1",
            modifications=[{"field": "x", "action": "set"}],
            reason="r",
        )
    finally:
        _reset_agent_ctx(tokens)
    assert out.startswith("[错误] 等待审批异常:")

