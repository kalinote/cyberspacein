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
import app.service.analyst.hitl as hitl_module
import app.service.analyst.service as service_module
import app.service.analyst.tools as tools_module
from app.schemas.agent.hitl import HitlSource
from app.schemas.constants import EntityType, NanobotSessionStatusEnum
from app.service.analyst.hitl import HitlOutcome


@dataclass
class FakeSessionDoc:
    id: str
    agent_id: str = "a1"
    status: NanobotSessionStatusEnum = NanobotSessionStatusEnum.RUNNING
    pending_approval: dict | None = None
    todos: list[dict] = field(default_factory=list)
    updated_at: datetime = field(default_factory=datetime.now)

    async def save(self) -> None:
        FakeNanobotSessionModel._docs[self.id] = self


class FakeNanobotSessionModel:
    _docs: dict[str, FakeSessionDoc] = {}

    @classmethod
    async def find_one(cls, query: dict[str, Any]) -> FakeSessionDoc | None:
        return cls._docs.get(query.get("_id"))


@pytest.fixture(autouse=True)
def _patch_session_model(monkeypatch: pytest.MonkeyPatch) -> Iterable[None]:
    FakeNanobotSessionModel._docs = {}
    monkeypatch.setattr(tools_module, "NanobotSessionModel", FakeNanobotSessionModel)
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
        async def get(self, **kw):
            assert kw["index"] == "article" and kw["id"] == "1"
            assert "_source_includes" not in kw
            return {"_source": {"k": "v"}}

    monkeypatch.setattr("app.db.elasticsearch.get_es", lambda: _ES())
    out = await tools_module.GetEntityTool().execute(entity_type=EntityType.ARTICLE.value, entity_uuid="1")
    assert json.loads(out) == {"k": "v"}


@pytest.mark.asyncio
async def test_get_entity_with_fields_passes_source_includes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, Any] = {}

    class _ES:
        async def get(self, **kw):
            captured.clear()
            captured.update(kw)
            return {"_source": {"clean_content": "正文"}}

    monkeypatch.setattr("app.db.elasticsearch.get_es", lambda: _ES())
    out = await tools_module.GetEntityTool().execute(
        entity_type=EntityType.ARTICLE.value,
        entity_uuid="1",
        fields=["clean_content", "title"],
    )
    assert captured["_source_includes"] == ["clean_content", "title"]
    assert json.loads(out) == {"clean_content": "正文"}


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
    FakeNanobotSessionModel._docs["s1"] = FakeSessionDoc(id="s1", agent_id="a1")
    tokens = _set_agent_ctx()
    calls: list[tuple[str, str, Any]] = []

    async def _broadcast(agent_id: str, event: str, data: Any, *, persist: bool = True) -> None:
        calls.append((agent_id, event, data))

    monkeypatch.setattr(service_module.AnalystService, "broadcast_sse", _broadcast)
    try:
        out = await tools_module.WriteTodosTool().execute(
            todos=[{"content": "x", "status": "pending"}]
        )
    finally:
        _reset_agent_ctx(tokens)

    assert "已更新待办 1 条" in out
    assert FakeNanobotSessionModel._docs["s1"].todos[0]["content"] == "x"
    assert calls and calls[0][1] == "todos"
    assert calls[0][2]["todos"][0]["status"] == "pending"


@pytest.mark.asyncio
async def test_write_todos_normalizes_fields(monkeypatch: pytest.MonkeyPatch) -> None:
    FakeNanobotSessionModel._docs["s1"] = FakeSessionDoc(id="s1", agent_id="a1")
    tokens = _set_agent_ctx()
    monkeypatch.setattr(service_module.AnalystService, "broadcast_sse", AsyncMock())
    try:
        await tools_module.WriteTodosTool().execute(
            todos=[{"id": 1, "content": "  hello  ", "status": "completed", "x": "y"}]
        )
    finally:
        _reset_agent_ctx(tokens)
    todo = FakeNanobotSessionModel._docs["s1"].todos[0]
    assert set(todo.keys()) == {"id", "content", "status", "updated_at"}
    assert todo["id"] == "1"
    assert todo["content"] == "hello"


@pytest.mark.asyncio
async def test_write_todos_session_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    tokens = _set_agent_ctx(agent_id="a1", session_id="missing")
    monkeypatch.setattr(service_module.AnalystService, "broadcast_sse", AsyncMock())
    try:
        out = await tools_module.WriteTodosTool().execute(todos=[])
    finally:
        _reset_agent_ctx(tokens)
    assert "当前会话不存在" in out


@pytest.mark.asyncio
async def test_notify_user_broadcasts(monkeypatch: pytest.MonkeyPatch) -> None:
    tokens = _set_agent_ctx()
    calls: list[tuple[str, str, Any]] = []

    async def _broadcast(agent_id: str, event: str, data: Any, *, persist: bool = True) -> None:
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


def _hitl_outcome(
    *,
    approved: list[dict] | None = None,
    rejections: list[str] | None = None,
    resolution: str = "approved",
) -> HitlOutcome:
    approved = approved if approved is not None else [{"action": "approve"}]
    rejections = rejections if rejections is not None else []
    return HitlOutcome(
        approved=approved,
        rejections=rejections,
        resolution=resolution,
        approval_request_id="req-1",
        raw={"decisions": approved + [{"reason": r} for r in rejections]},
    )


@pytest.mark.asyncio
async def test_modify_entity_calls_hitl_with_source_and_payload(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    tokens = _set_agent_ctx()
    captured: dict[str, Any] = {}

    async def _request(
        agent_id: str,
        session_id: str,
        source: str,
        payload: dict[str, Any],
    ) -> HitlOutcome:
        captured.update(
            agent_id=agent_id,
            session_id=session_id,
            source=source,
            payload=payload,
        )
        return _hitl_outcome()

    monkeypatch.setattr(hitl_module.HitlService, "request_approval", _request)
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
    assert captured["source"] == HitlSource.TOOL_MODIFY_ENTITY
    assert captured["payload"]["entity_uuid"] == "u1"
    assert captured["payload"]["reason"] == "r"
    assert "approval_request_id" not in captured["payload"]


@pytest.mark.asyncio
async def test_modify_entity_handshake_reject(monkeypatch: pytest.MonkeyPatch) -> None:
    tokens = _set_agent_ctx()
    monkeypatch.setattr(
        hitl_module.HitlService,
        "request_approval",
        AsyncMock(
            return_value=_hitl_outcome(
                approved=[],
                rejections=["bad"],
                resolution="rejected",
            )
        ),
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
    tokens = _set_agent_ctx()
    monkeypatch.setattr(
        hitl_module.HitlService,
        "request_approval",
        AsyncMock(
            return_value=_hitl_outcome(approved=[], rejections=[], resolution="rejected")
        ),
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
    assert out == "修改未获得任何批准，未执行。"


@pytest.mark.asyncio
async def test_modify_entity_await_exception_returns(monkeypatch: pytest.MonkeyPatch) -> None:
    tokens = _set_agent_ctx()

    async def _boom(*_a: Any, **_k: Any) -> HitlOutcome:
        raise RuntimeError("x")

    monkeypatch.setattr(hitl_module.HitlService, "request_approval", _boom)
    try:
        out = await tools_module.ModifyEntityTool().execute(
            entity_type=EntityType.ARTICLE.value,
            entity_uuid="u1",
            modifications=[{"field": "x", "action": "set"}],
            reason="r",
        )
    finally:
        _reset_agent_ctx(tokens)
    assert out == "[错误] x"

