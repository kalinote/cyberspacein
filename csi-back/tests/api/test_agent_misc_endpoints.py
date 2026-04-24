"""MIGRATION_PLAN §12.17：/agent/cancel、tools/tools-list、statistics 路由契约测试。"""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import pytest
from fastapi import FastAPI
from starlette.testclient import TestClient

from app.api.v1.endpoints import agent as agent_ep


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
    monkeypatch.setattr(agent_ep, "BUSINESS_TOOL_CLASSES", {"a": object(), "b": object()})
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
        agent_ep,
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
        agent_ep,
        "BUSINESS_TOOL_CLASSES",
        {"bad": _bad, "good": _Good},
    )
    r = client.get("/api/v1/agent/configs/tools")
    assert r.status_code == 200
    body = r.json()
    assert body["code"] == 0
    assert [x["name"] for x in body["data"]] == ["good"]


def test_get_statistics_aggregates_counts(monkeypatch: pytest.MonkeyPatch) -> None:
    client = _app()
    monkeypatch.setattr(agent_ep, "BUSINESS_TOOL_CLASSES", {"a": object(), "b": object(), "c": object()})
    monkeypatch.setattr(agent_ep.AgentModelConfigModel, "find", lambda *_a, **_k: _CountQuery(1))
    monkeypatch.setattr(agent_ep.AgentPromptTemplateModel, "find", lambda *_a, **_k: _CountQuery(2))
    monkeypatch.setattr(agent_ep.NanobotWorkspaceModel, "find", lambda *_a, **_k: _CountQuery(3))
    monkeypatch.setattr(agent_ep.NanobotAgentModel, "find", lambda *_a, **_k: _CountQuery(4))

    r = client.get("/api/v1/agent/configs/statistics")
    assert r.status_code == 200
    body = r.json()
    assert body["code"] == 0
    assert body["data"] == {
        "model_configs": 1,
        "prompt_templates": 2,
        "workspaces": 3,
        "agents": 4,
        "business_tools": 3,
    }


def test_post_cancel_with_running_task(monkeypatch: pytest.MonkeyPatch) -> None:
    client = _app()
    called: dict[str, Any] = {}

    async def _cancel(agent_id: str, *, reason: str = "cancel") -> bool:
        called["agent_id"] = agent_id
        called["reason"] = reason
        return True

    monkeypatch.setattr(agent_ep.AnalystService, "cancel_agent", _cancel)
    r = client.post("/api/v1/agent/cancel", json={"agent_id": "a1", "reason": "x"})
    assert r.status_code == 200
    body = r.json()
    assert body["code"] == 0
    assert body["data"]["agent_id"] == "a1"
    assert body["data"]["cancelled"] is True
    assert "取消请求已发送" in body["message"]
    assert called == {"agent_id": "a1", "reason": "x"}


def test_post_cancel_without_running_task(monkeypatch: pytest.MonkeyPatch) -> None:
    client = _app()

    async def _cancel(agent_id: str, *, reason: str = "cancel") -> bool:
        return False

    monkeypatch.setattr(agent_ep.AnalystService, "cancel_agent", _cancel)
    r = client.post("/api/v1/agent/cancel", json={"agent_id": "a1", "reason": "x"})
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

    async def _cancel(agent_id: str, *, reason: str = "cancel") -> bool:
        called["reason"] = reason
        return True

    monkeypatch.setattr(agent_ep.AnalystService, "cancel_agent", _cancel)
    r = client.post("/api/v1/agent/cancel", json={"agent_id": "a1"})
    assert r.status_code == 200
    assert called["reason"] == "user cancel"

