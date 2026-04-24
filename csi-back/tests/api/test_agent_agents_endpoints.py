"""MIGRATION_PLAN §12.12：/agent/agents 路由契约测试（不连 DB）。"""

from __future__ import annotations

from datetime import datetime

import pytest
from fastapi import FastAPI
from starlette.testclient import TestClient

import app.utils.status_codes as status_codes
from app.api.v1.endpoints import agent as agent_ep
from app.schemas.agent.nanobot_agent import AgentServiceError
from app.schemas.constants import NanobotAgentStatusEnum


class FakeAgentDoc:
    def __init__(self, *, id: str, workspace_id: str, name: str) -> None:
        self.id = id
        self.workspace_id = workspace_id
        self.name = name
        self.description = None
        self.prompt_template_id = "p1"
        self.model_config_id = "m1"
        self.tools: list[str] = []
        self.skills: list[str] = []
        self.mcp_servers: list[str] = []
        self.llm_config: dict = {}
        self.status = NanobotAgentStatusEnum.IDLE
        self.current_session_id = None
        self.steps: list[dict] = []
        self.todos: list[dict] = []
        self.pending_approval = None
        self.result = None
        self.created_at = datetime(2026, 1, 1, 0, 0, 0)
        self.updated_at = datetime(2026, 1, 1, 0, 0, 0)


def _app() -> TestClient:
    app = FastAPI()
    app.include_router(agent_ep.router, prefix="/api/v1")
    return TestClient(app)


def test_route_create_201(monkeypatch: pytest.MonkeyPatch) -> None:
    client = _app()

    async def _create(_data):
        return FakeAgentDoc(id="a1", workspace_id="w1", name="A")

    monkeypatch.setattr(agent_ep.AgentService, "create", _create)
    r = client.post(
        "/api/v1/agent/agents",
        json={
            "workspace_id": "w1",
            "name": "A",
            "prompt_template_id": "p1",
            "model_config_id": "m1",
        },
    )
    assert r.status_code == 200
    body = r.json()
    assert body["code"] == 0
    assert body["data"]["id"] == "a1"
    assert body["data"]["workspace_id"] == "w1"


def test_route_not_found(monkeypatch: pytest.MonkeyPatch) -> None:
    client = _app()

    async def _get(_agent_id: str):
        raise AgentServiceError(status_codes.NOT_FOUND_AGENT, "Agent 不存在")

    monkeypatch.setattr(agent_ep.AgentService, "get", _get)
    r = client.get("/api/v1/agent/agents/missing")
    assert r.status_code == 200
    body = r.json()
    assert body["code"] == status_codes.NOT_FOUND_AGENT


@pytest.mark.asyncio
async def test_route_subset_violation_payload(monkeypatch: pytest.MonkeyPatch) -> None:
    violations = ["tools 不在 Workspace 白名单内: ['t2']"]

    async def _create(_data):
        raise AgentServiceError(
            status_codes.INVALID_ARGUMENT,
            "Agent 选定资源不满足 Workspace 白名单子集约束",
            data={"violations": violations},
        )

    monkeypatch.setattr(agent_ep.AgentService, "create", _create)
    out = await agent_ep.create_agent(
        agent_ep.NanobotAgentCreateRequestSchema(
            workspace_id="w1",
            name="A",
            prompt_template_id="p1",
            model_config_id="m1",
            tools=["t2"],
        )
    )
    assert out.code == status_codes.INVALID_ARGUMENT
    assert out.data["violations"] == violations


def test_route_list_filter_query(monkeypatch: pytest.MonkeyPatch) -> None:
    client = _app()

    async def _list_page(*, page: int, page_size: int, workspace_id: str | None = None, search: str | None = None):
        assert page == 2 and page_size == 3
        assert workspace_id == "w1"
        assert search == "foo"
        return ([FakeAgentDoc(id="a1", workspace_id="w1", name="foo")], 1)

    monkeypatch.setattr(agent_ep.AgentService, "list_page", _list_page)
    r = client.get("/api/v1/agent/agents?page=2&page_size=3&workspace_id=w1&search=foo")
    assert r.status_code == 200
    body = r.json()
    assert body["total"] == 1
    assert body["items"][0]["id"] == "a1"

