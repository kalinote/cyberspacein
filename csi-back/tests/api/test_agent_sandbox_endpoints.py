"""agent 沙盒接口路由注册与列表契约测试。"""

from __future__ import annotations

import pytest
from fastapi import FastAPI
from starlette.testclient import TestClient

from app.api.v1.endpoints import action as action_ep
from app.api.v1.endpoints import agent as agent_ep
import app.api.v1.endpoints.agent.sandbox as sandbox_ep


def _agent_client() -> TestClient:
    app = FastAPI()
    app.include_router(agent_ep.router, prefix="/api/v1")
    return TestClient(app)


def _action_client() -> TestClient:
    app = FastAPI()
    app.include_router(action_ep.router, prefix="/api/v1")
    return TestClient(app)


def _collect_agent_paths(app: FastAPI) -> list[tuple[str, str]]:
    paths: list[tuple[str, str]] = []
    for r in app.routes:
        methods = getattr(r, "methods", None)
        path = getattr(r, "path", "")
        if not methods or "/api/v1/agent/sandbox" not in path:
            continue
        for m in methods:
            if m in {"HEAD", "OPTIONS"}:
                continue
            paths.append((m, path))
    return paths


def test_sandbox_routes_registered_under_agent() -> None:
    app = FastAPI()
    app.include_router(agent_ep.router, prefix="/api/v1")
    paths = _collect_agent_paths(app)
    assert paths == [
        ("POST", "/api/v1/agent/sandbox/create"),
        ("DELETE", "/api/v1/agent/sandbox/{sandbox_id}"),
        ("GET", "/api/v1/agent/sandbox/list"),
        ("GET", "/api/v1/agent/sandbox/detail/{sandbox_id}"),
    ]


def test_sandbox_routes_not_registered_under_action() -> None:
    app = FastAPI()
    app.include_router(action_ep.router, prefix="/api/v1")
    paths = []
    for r in app.routes:
        methods = getattr(r, "methods", None)
        path = getattr(r, "path", "")
        if not methods or "/api/v1/action/sandbox" not in path:
            continue
        for m in methods:
            if m in {"HEAD", "OPTIONS"}:
                continue
            paths.append((m, path))
    assert paths == []


def test_list_sandboxes_returns_paginated_data(monkeypatch: pytest.MonkeyPatch) -> None:
    client = _agent_client()

    async def _list_sandboxes_from_db(skip: int, limit: int) -> tuple[list[dict], int]:
        assert skip == 0
        assert limit == 10
        return (
            [
                {
                    "sandbox_id": "abc123",
                    "name": "csi-sandbox-8080",
                    "display_name": "测试沙盒",
                    "image_type": "all-in-one",
                    "status": "running",
                    "sandbox_status": "deployed",
                    "image": "sandbox:latest",
                    "host_port": 8080,
                    "created_at": None,
                }
            ],
            1,
        )

    monkeypatch.setattr(sandbox_ep.sandbox_service, "list_sandboxes_from_db", _list_sandboxes_from_db)
    r = client.get("/api/v1/agent/sandbox/list?page=1&page_size=10")
    assert r.status_code == 200
    body = r.json()
    assert body["total"] == 1
    assert body["page"] == 1
    assert body["page_size"] == 10
    assert len(body["items"]) == 1
    assert body["items"][0]["sandbox_id"] == "abc123"
    assert body["items"][0]["sandbox_status"] == "deployed"


def test_old_action_sandbox_list_returns_404() -> None:
    client = _action_client()
    r = client.get("/api/v1/action/sandbox/list")
    assert r.status_code == 404
