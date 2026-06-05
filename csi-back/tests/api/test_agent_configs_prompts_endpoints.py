from __future__ import annotations

import pytest
from fastapi import FastAPI
from starlette.testclient import TestClient

import app.utils.status_codes as status_codes
from app.api.v1.endpoints import agent as agent_ep
import app.api.v1.endpoints.agent.configs_prompts as prompts_ep


class FakePromptTemplateDoc:
    def __init__(self, *, id: str, name: str) -> None:
        self.id = id
        self.name = name
        self.deleted = False

    async def delete(self) -> None:
        self.deleted = True


def _app() -> TestClient:
    app = FastAPI()
    app.include_router(agent_ep.router, prefix="/api/v1")
    return TestClient(app)


def test_delete_prompt_template_success(monkeypatch: pytest.MonkeyPatch) -> None:
    client = _app()
    doc = FakePromptTemplateDoc(id="t1", name="模板一")

    async def _agent_find_one(_filter: dict) -> None:
        return None

    async def _workspace_find_one(_filter: dict) -> None:
        return None

    async def _template_find_one(_filter: dict) -> FakePromptTemplateDoc:
        assert _filter == {"_id": "t1"}
        return doc

    monkeypatch.setattr(prompts_ep.NanobotAgentModel, "find_one", _agent_find_one)
    monkeypatch.setattr(prompts_ep.NanobotWorkspaceModel, "find_one", _workspace_find_one)
    monkeypatch.setattr(prompts_ep.AgentPromptTemplateModel, "find_one", _template_find_one)

    r = client.delete("/api/v1/agent/configs/prompt-template/t1")
    assert r.status_code == 200
    body = r.json()
    assert body["code"] == 0
    assert body["message"] == "删除成功"
    assert doc.deleted is True


def test_delete_prompt_template_not_found(monkeypatch: pytest.MonkeyPatch) -> None:
    client = _app()

    async def _agent_find_one(_filter: dict) -> None:
        return None

    async def _workspace_find_one(_filter: dict) -> None:
        return None

    async def _template_find_one(_filter: dict) -> None:
        return None

    monkeypatch.setattr(prompts_ep.NanobotAgentModel, "find_one", _agent_find_one)
    monkeypatch.setattr(prompts_ep.NanobotWorkspaceModel, "find_one", _workspace_find_one)
    monkeypatch.setattr(prompts_ep.AgentPromptTemplateModel, "find_one", _template_find_one)

    r = client.delete("/api/v1/agent/configs/prompt-template/missing")
    assert r.status_code == 200
    assert r.json()["code"] == status_codes.NOT_FOUND_TEMPLATE


def test_delete_prompt_template_conflict_agent(monkeypatch: pytest.MonkeyPatch) -> None:
    client = _app()
    doc = FakePromptTemplateDoc(id="t1", name="模板一")

    class FakeAgent:
        id = "a1"

    async def _agent_find_one(_filter: dict) -> FakeAgent:
        return FakeAgent()

    async def _workspace_find_one(_filter: dict) -> None:
        return None

    async def _template_find_one(_filter: dict) -> FakePromptTemplateDoc:
        return doc

    monkeypatch.setattr(prompts_ep.NanobotAgentModel, "find_one", _agent_find_one)
    monkeypatch.setattr(prompts_ep.NanobotWorkspaceModel, "find_one", _workspace_find_one)
    monkeypatch.setattr(prompts_ep.AgentPromptTemplateModel, "find_one", _template_find_one)

    r = client.delete("/api/v1/agent/configs/prompt-template/t1")
    assert r.status_code == 200
    assert r.json()["code"] == status_codes.CONFLICT_STATE
    assert doc.deleted is False


def test_delete_prompt_template_conflict_workspace(monkeypatch: pytest.MonkeyPatch) -> None:
    client = _app()
    doc = FakePromptTemplateDoc(id="t1", name="模板一")

    class FakeWs:
        id = "w1"

    async def _agent_find_one(_filter: dict) -> None:
        return None

    async def _workspace_find_one(_filter: dict) -> FakeWs:
        return FakeWs()

    async def _template_find_one(_filter: dict) -> FakePromptTemplateDoc:
        return doc

    monkeypatch.setattr(prompts_ep.NanobotAgentModel, "find_one", _agent_find_one)
    monkeypatch.setattr(prompts_ep.NanobotWorkspaceModel, "find_one", _workspace_find_one)
    monkeypatch.setattr(prompts_ep.AgentPromptTemplateModel, "find_one", _template_find_one)

    r = client.delete("/api/v1/agent/configs/prompt-template/t1")
    assert r.status_code == 200
    assert r.json()["code"] == status_codes.CONFLICT_STATE
    assert doc.deleted is False
