from __future__ import annotations

from datetime import datetime

import pytest
from fastapi import FastAPI
from starlette.testclient import TestClient

import app.utils.status_codes as status_codes
from app.api.v1.endpoints import agent as agent_ep
import app.api.v1.endpoints.agent.configs_models as models_ep
from app.dependencies.auth import get_current_user
from app.models.auth.user import UserModel


class FakeModelConfigDoc:
    def __init__(self, *, id: str, name: str) -> None:
        self.id = id
        self.name = name
        self.description = None
        self.base_url = "https://example.com"
        self.api_key = "k"
        self.model = "m1"
        self.created_at = datetime(2026, 1, 1, 0, 0, 0)
        self.updated_at = datetime(2026, 1, 1, 0, 0, 0)
        self.deleted = False
        self.saved = False

    async def delete(self) -> None:
        self.deleted = True

    async def save(self) -> None:
        self.saved = True


def _app() -> TestClient:
    app = FastAPI()
    app.dependency_overrides[get_current_user] = lambda: UserModel.model_construct(
        id="user-1",
        username="tester",
        display_name="Tester",
        password_hash="h",
        enabled=True,
        is_system=True,
    )
    app.include_router(agent_ep.router, prefix="/api/v1")
    return TestClient(app)


def test_get_model_config_detail_not_found(monkeypatch: pytest.MonkeyPatch) -> None:
    client = _app()

    async def _find_one(_filter: dict) -> None:
        assert _filter == {"_id": "missing"}
        return None

    monkeypatch.setattr(models_ep.AgentModelConfigModel, "find_one", _find_one)
    r = client.get("/api/v1/agent/configs/model/missing")
    assert r.status_code == 200
    body = r.json()
    assert body["code"] == status_codes.NOT_FOUND_MODEL_CONFIG


def test_update_model_config_conflict_name(monkeypatch: pytest.MonkeyPatch) -> None:
    client = _app()
    doc = FakeModelConfigDoc(id="c1", name="旧名")
    other = FakeModelConfigDoc(id="c2", name="新名")

    async def _find_one(_filter: dict):
        if _filter == {"_id": "c1"}:
            return doc
        if _filter == {"name": "新名"}:
            return other
        raise AssertionError(f"unexpected filter: {_filter}")

    monkeypatch.setattr(models_ep.AgentModelConfigModel, "find_one", _find_one)
    r = client.put(
        "/api/v1/agent/configs/model/c1",
        json={
            "name": "新名",
            "description": None,
            "base_url": "https://example.com",
            "api_key": "k",
            "model": "m1",
        },
    )
    assert r.status_code == 200
    body = r.json()
    assert body["code"] == status_codes.CONFLICT_NAME
    assert doc.saved is False


def test_delete_model_config_success(monkeypatch: pytest.MonkeyPatch) -> None:
    client = _app()
    doc = FakeModelConfigDoc(id="c1", name="模型一")

    async def _agent_find_one(_filter: dict) -> None:
        return None

    async def _workspace_find_one(_filter: dict) -> None:
        return None

    async def _config_find_one(_filter: dict):
        assert _filter == {"_id": "c1"}
        return doc

    monkeypatch.setattr(models_ep.NanobotAgentModel, "find_one", _agent_find_one)
    monkeypatch.setattr(models_ep.NanobotWorkspaceModel, "find_one", _workspace_find_one)
    monkeypatch.setattr(models_ep.AgentModelConfigModel, "find_one", _config_find_one)

    r = client.delete("/api/v1/agent/configs/model/c1")
    assert r.status_code == 200
    body = r.json()
    assert body["code"] == 0
    assert body["message"] == "删除成功"
    assert doc.deleted is True


def test_delete_model_config_not_found(monkeypatch: pytest.MonkeyPatch) -> None:
    client = _app()

    async def _agent_find_one(_filter: dict) -> None:
        return None

    async def _workspace_find_one(_filter: dict) -> None:
        return None

    async def _config_find_one(_filter: dict) -> None:
        return None

    monkeypatch.setattr(models_ep.NanobotAgentModel, "find_one", _agent_find_one)
    monkeypatch.setattr(models_ep.NanobotWorkspaceModel, "find_one", _workspace_find_one)
    monkeypatch.setattr(models_ep.AgentModelConfigModel, "find_one", _config_find_one)

    r = client.delete("/api/v1/agent/configs/model/missing")
    assert r.status_code == 200
    assert r.json()["code"] == status_codes.NOT_FOUND_MODEL_CONFIG


def test_delete_model_config_conflict_agent(monkeypatch: pytest.MonkeyPatch) -> None:
    client = _app()
    doc = FakeModelConfigDoc(id="c1", name="模型一")

    class FakeAgent:
        id = "a1"

    async def _agent_find_one(_filter: dict) -> FakeAgent:
        return FakeAgent()

    async def _workspace_find_one(_filter: dict) -> None:
        return None

    async def _config_find_one(_filter: dict):
        return doc

    monkeypatch.setattr(models_ep.NanobotAgentModel, "find_one", _agent_find_one)
    monkeypatch.setattr(models_ep.NanobotWorkspaceModel, "find_one", _workspace_find_one)
    monkeypatch.setattr(models_ep.AgentModelConfigModel, "find_one", _config_find_one)

    r = client.delete("/api/v1/agent/configs/model/c1")
    assert r.status_code == 200
    assert r.json()["code"] == status_codes.CONFLICT_STATE
    assert doc.deleted is False


def test_delete_model_config_conflict_workspace(monkeypatch: pytest.MonkeyPatch) -> None:
    client = _app()
    doc = FakeModelConfigDoc(id="c1", name="模型一")

    class FakeWs:
        id = "w1"

    async def _agent_find_one(_filter: dict) -> None:
        return None

    async def _workspace_find_one(_filter: dict) -> FakeWs:
        return FakeWs()

    async def _config_find_one(_filter: dict):
        return doc

    monkeypatch.setattr(models_ep.NanobotAgentModel, "find_one", _agent_find_one)
    monkeypatch.setattr(models_ep.NanobotWorkspaceModel, "find_one", _workspace_find_one)
    monkeypatch.setattr(models_ep.AgentModelConfigModel, "find_one", _config_find_one)

    r = client.delete("/api/v1/agent/configs/model/c1")
    assert r.status_code == 200
    assert r.json()["code"] == status_codes.CONFLICT_STATE
    assert doc.deleted is False

