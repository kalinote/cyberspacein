"""MIGRATION_PLAN §12.17：/agent/cancel、tools/tools-list、statistics 路由契约测试。"""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import pytest
from fastapi import FastAPI
from starlette.testclient import TestClient

from app.api.v1.endpoints import agent as agent_ep
import app.api.v1.endpoints.agent.configs_tools as configs_tools_ep
import app.api.v1.endpoints.agent.runtime as runtime_ep
import app.models.agent.skill as skill_models
import app.utils.status_codes as status_codes


def _app() -> TestClient:
    app = FastAPI()
    app.include_router(agent_ep.router, prefix="/api/v1")
    return TestClient(app)


class _CountQuery:
    def __init__(self, n: int) -> None:
        self._n = n

    async def count(self) -> int:
        return self._n


def test_get_tools_list_returns_business_names(monkeypatch: pytest.MonkeyPatch) -> None:
    client = _app()
    monkeypatch.setattr(configs_tools_ep, "BUSINESS_TOOL_CLASSES", {"a": object(), "b": object()})
    r = client.get("/api/v1/agent/configs/tools-list")
    assert r.status_code == 200
    body = r.json()
    assert body["code"] == 0
    assert set(body["data"]) == {"a", "b"}


def test_get_tools_returns_descriptors(monkeypatch: pytest.MonkeyPatch) -> None:
    client = _app()

    class _T:
        def __init__(self, *, name: str, desc: str, read_only: bool, exclusive: bool) -> None:
            self.name = name
            self.description = desc
            self.read_only = read_only
            self.exclusive = exclusive

    monkeypatch.setattr(
        configs_tools_ep,
        "BUSINESS_TOOL_CLASSES",
        {
            "get_current_time": lambda: _T(name="get_current_time", desc="d1", read_only=True, exclusive=False),
            "modify_entity": lambda: _T(name="modify_entity", desc="d2", read_only=False, exclusive=True),
        },
    )
    r = client.get("/api/v1/agent/configs/tools")
    assert r.status_code == 200
    body = r.json()
    assert body["code"] == 0
    data = {x["name"]: x for x in body["data"]}
    assert data["get_current_time"]["read_only"] is True
    assert data["modify_entity"]["exclusive"] is True


def test_get_tools_instance_failure_skipped(monkeypatch: pytest.MonkeyPatch) -> None:
    client = _app()

    def _bad():
        raise RuntimeError("boom")

    class _Good:
        def __init__(self) -> None:
            self.name = "good"
            self.description = "ok"
            self.read_only = True
            self.exclusive = False

    monkeypatch.setattr(
        configs_tools_ep,
        "BUSINESS_TOOL_CLASSES",
        {"bad": _bad, "good": _Good},
    )
    r = client.get("/api/v1/agent/configs/tools")
    assert r.status_code == 200
    body = r.json()
    assert body["code"] == 0
    assert [x["name"] for x in body["data"]] == ["good"]


def test_get_skills_list_returns_brief_items(monkeypatch: pytest.MonkeyPatch) -> None:
    client = _app()

    class _Skill:
        def __init__(self, *, id: str, name: str, description: str, always: bool) -> None:
            self.id = id
            self.name = name
            self.description = description
            self.always = always

    async def _list_all_brief():
        return [
            _Skill(id="s1", name="alpha", description="desc-a", always=True),
            _Skill(id="s2", name="beta", description="desc-b", always=False),
        ]

    monkeypatch.setattr(configs_tools_ep.SkillService, "list_all_brief", _list_all_brief)
    r = client.get("/api/v1/agent/configs/skills-list")
    assert r.status_code == 200
    body = r.json()
    assert body["code"] == 0
    assert body["data"] == [
        {"id": "s1", "name": "alpha", "description": "desc-a", "always": True},
        {"id": "s2", "name": "beta", "description": "desc-b", "always": False},
    ]


def test_get_skills_filter_by_workspace(monkeypatch: pytest.MonkeyPatch) -> None:
    client = _app()

    class _Workspace:
        enabled_skills = ["s2", "s1"]

    class _Skill:
        def __init__(self, *, id: str, name: str, description: str, always: bool) -> None:
            self.id = id
            self.name = name
            self.description = description
            self.always = always

    async def _get(_workspace_id: str):
        assert _workspace_id == "w1"
        return _Workspace()

    async def _list_brief_by_ids(skill_ids: list[str]):
        assert skill_ids == ["s2", "s1"]
        return [
            _Skill(id="s2", name="beta", description="desc-b", always=False),
            _Skill(id="s1", name="alpha", description="desc-a", always=True),
        ]

    monkeypatch.setattr(configs_tools_ep.WorkspaceService, "get", _get)
    monkeypatch.setattr(configs_tools_ep.SkillService, "list_brief_by_ids", _list_brief_by_ids)
    r = client.get("/api/v1/agent/configs/filter/skills", params={"workspace_id": "w1"})
    assert r.status_code == 200
    body = r.json()
    assert body["code"] == 0
    assert body["data"] == [
        {"id": "s2", "name": "beta", "description": "desc-b", "always": False},
        {"id": "s1", "name": "alpha", "description": "desc-a", "always": True},
    ]


def test_get_skills_filter_workspace_not_found(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.schemas.agent.workspace import WorkspaceServiceError

    client = _app()

    async def _get(_workspace_id: str):
        raise WorkspaceServiceError(status_codes.NOT_FOUND_WORKSPACE, "工作区不存在")

    monkeypatch.setattr(configs_tools_ep.WorkspaceService, "get", _get)
    r = client.get("/api/v1/agent/configs/filter/skills", params={"workspace_id": "missing"})
    assert r.status_code == 200
    body = r.json()
    assert body["code"] == status_codes.NOT_FOUND_WORKSPACE
    assert "工作区不存在" in body["message"]


def test_get_statistics_aggregates_counts(monkeypatch: pytest.MonkeyPatch) -> None:
    client = _app()
    monkeypatch.setattr(configs_tools_ep, "BUSINESS_TOOL_CLASSES", {"a": object(), "b": object(), "c": object()})
    monkeypatch.setattr(configs_tools_ep.AgentModelConfigModel, "find", lambda *_a, **_k: _CountQuery(1))
    monkeypatch.setattr(configs_tools_ep.AgentPromptTemplateModel, "find", lambda *_a, **_k: _CountQuery(2))
    monkeypatch.setattr(configs_tools_ep.NanobotMemoryDocsModel, "find", lambda *_a, **_k: _CountQuery(5))
    monkeypatch.setattr(configs_tools_ep.NanobotWorkspaceModel, "find", lambda *_a, **_k: _CountQuery(3))
    monkeypatch.setattr(configs_tools_ep.NanobotAgentModel, "find", lambda *_a, **_k: _CountQuery(4))
    monkeypatch.setattr(skill_models.NanobotSkillModel, "find", lambda *_a, **_k: _CountQuery(6))

    r = client.get("/api/v1/agent/configs/statistics")
    assert r.status_code == 200
    body = r.json()
    assert body["code"] == 0
    assert body["data"] == {
        "model_configs": 1,
        "prompt_templates": 2,
        "system_prompts": 5,
        "skills": 6,
        "workspaces": 3,
        "agents": 4,
        "business_tools": 3,
    }


def test_post_cancel_with_running_task(monkeypatch: pytest.MonkeyPatch) -> None:
    client = _app()
    called: dict[str, Any] = {}

    async def _cancel(agent_id: str, session_id: str, *, reason: str = "cancel") -> bool:
        called["agent_id"] = agent_id
        called["session_id"] = session_id
        called["reason"] = reason
        return True

    monkeypatch.setattr(runtime_ep.AnalystService, "cancel_agent", _cancel)
    r = client.post(
        "/api/v1/agent/cancel",
        json={"agent_id": "a1", "session_id": "s1", "reason": "x"},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["code"] == 0
    assert body["data"]["agent_id"] == "a1"
    assert body["data"]["cancelled"] is True
    assert "取消请求已发送" in body["message"]
    assert called == {"agent_id": "a1", "session_id": "s1", "reason": "x"}


def test_post_cancel_without_running_task(monkeypatch: pytest.MonkeyPatch) -> None:
    client = _app()

    async def _cancel(agent_id: str, session_id: str, *, reason: str = "cancel") -> bool:
        return False

    monkeypatch.setattr(runtime_ep.AnalystService, "cancel_agent", _cancel)
    r = client.post(
        "/api/v1/agent/cancel",
        json={"agent_id": "a1", "session_id": "s1", "reason": "x"},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["code"] == 0
    assert body["data"]["cancelled"] is False
    assert "没有正在运行的任务" in body["message"]


def test_post_cancel_missing_agent_id_422() -> None:
    client = _app()
    r = client.post("/api/v1/agent/cancel", json={})
    assert r.status_code == 422


def test_post_cancel_default_reason(monkeypatch: pytest.MonkeyPatch) -> None:
    client = _app()
    called: dict[str, Any] = {}

    async def _cancel(agent_id: str, session_id: str, *, reason: str = "cancel") -> bool:
        called["reason"] = reason
        return True

    monkeypatch.setattr(runtime_ep.AnalystService, "cancel_agent", _cancel)
    r = client.post("/api/v1/agent/cancel", json={"agent_id": "a1", "session_id": "s1"})
    assert r.status_code == 200
    assert called["reason"] == "user cancel"

