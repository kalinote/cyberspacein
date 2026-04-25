"""MIGRATION_PLAN §12.13：/agent/start /agent/approve 路由契约测试（不连 DB）。"""

from __future__ import annotations

import pytest
from fastapi import FastAPI
from starlette.testclient import TestClient

import app.utils.status_codes as status_codes
from app.api.v1.endpoints import agent as agent_ep
from app.schemas.agent.nanobot_agent import AgentServiceError


def _app() -> TestClient:
    app = FastAPI()
    app.include_router(agent_ep.router, prefix="/api/v1")
    return TestClient(app)


def test_route_start_success(monkeypatch: pytest.MonkeyPatch) -> None:
    client = _app()

    async def _start_agent(*, agent_id: str, user_prompt: str, context: dict):
        assert agent_id == "a1"
        assert user_prompt == "hi"
        assert context["k"] == "v"
        return "s1"

    monkeypatch.setattr(agent_ep.AnalystService, "start_agent", _start_agent)
    r = client.post(
        "/api/v1/agent/start",
        json={"agent_id": "a1", "user_prompt": "hi", "extra_context": {"k": "v"}},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["code"] == 0
    assert body["data"]["agent_id"] == "a1"
    assert body["data"]["session_id"] == "s1"


def test_route_start_prompt_can_be_empty_and_fallback_and_inject(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = _app()

    class _FakeAgent:
        prompt_template_id = "tpl1"

    class _FakeTemplate:
        user_prompt = "你好 {{ k }} {{ missing }}"

    async def _agent_find_one(query: dict):
        assert query == {"_id": "a1"}
        return _FakeAgent()

    async def _tpl_find_one(query: dict):
        assert query == {"_id": "tpl1"}
        return _FakeTemplate()

    async def _start_agent(*, agent_id: str, user_prompt: str, context: dict):
        assert agent_id == "a1"
        assert context["k"] == "v"
        assert user_prompt == "你好 v !字段丢失或不存在!"
        return "s2"

    monkeypatch.setattr(agent_ep.NanobotAgentModel, "find_one", _agent_find_one)
    monkeypatch.setattr(agent_ep.AgentPromptTemplateModel, "find_one", _tpl_find_one)
    monkeypatch.setattr(agent_ep.AnalystService, "start_agent", _start_agent)
    r = client.post(
        "/api/v1/agent/start",
        json={"agent_id": "a1", "user_prompt": "   ", "extra_context": {"k": "v"}},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["code"] == 0
    assert body["data"]["agent_id"] == "a1"
    assert body["data"]["session_id"] == "s2"


def test_route_approve_success(monkeypatch: pytest.MonkeyPatch) -> None:
    client = _app()

    async def _submit(agent_id: str, decisions: list[dict]):
        assert agent_id == "a1"
        assert decisions == [{"id": "x", "approve": True}]

    monkeypatch.setattr(agent_ep.AnalystService, "submit_approval", _submit)
    r = client.post(
        "/api/v1/agent/approve",
        json={"agent_id": "a1", "decisions": [{"id": "x", "approve": True}]},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["code"] == 0


def test_route_start_not_found(monkeypatch: pytest.MonkeyPatch) -> None:
    client = _app()

    async def _start_agent(*, agent_id: str, user_prompt: str, context: dict):
        raise AgentServiceError(status_codes.NOT_FOUND_AGENT, "Agent 不存在")

    monkeypatch.setattr(agent_ep.AnalystService, "start_agent", _start_agent)
    r = client.post(
        "/api/v1/agent/start",
        json={"agent_id": "missing", "user_prompt": "hi", "extra_context": {}},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["code"] == status_codes.NOT_FOUND_AGENT


def test_route_approve_unknown_agent_404(monkeypatch: pytest.MonkeyPatch) -> None:
    client = _app()

    async def _submit(agent_id: str, decisions: list[dict]):
        raise AgentServiceError(status_codes.NOT_FOUND_AGENT, "Agent 不存在")

    monkeypatch.setattr(agent_ep.AnalystService, "submit_approval", _submit)
    r = client.post(
        "/api/v1/agent/approve",
        json={"agent_id": "missing", "decisions": []},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["code"] == status_codes.NOT_FOUND_AGENT

