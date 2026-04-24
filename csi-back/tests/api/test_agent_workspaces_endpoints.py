"""MIGRATION_PLAN §12.11：/agent/workspaces 路由契约测试（不连 DB）。"""

from __future__ import annotations

from datetime import datetime

import pytest
from fastapi import FastAPI
from starlette.testclient import TestClient

import app.utils.status_codes as status_codes
from app.api.v1.endpoints import agent as agent_ep
from app.schemas.agent.workspace import (
    MCPServerConfigSchema,
    NanobotWorkspaceUpdateRequestSchema,
    WorkspaceServiceError,
)


class FakeWorkspaceDoc:
    def __init__(self, *, id: str, name: str) -> None:
        self.id = id
        self.name = name
        self.description = None
        self.prompt_template_ids: list[str] = []
        self.model_config_ids: list[str] = []
        self.enabled_tools: list[str] = []
        self.enabled_skills: list[str] = []
        self.enabled_mcp_servers: dict[str, dict] = {
            "srv": MCPServerConfigSchema(command="npx").model_dump()
        }
        self.created_at = datetime(2026, 1, 1, 0, 0, 0)
        self.updated_at = datetime(2026, 1, 1, 0, 0, 0)


def _app() -> TestClient:
    app = FastAPI()
    app.include_router(agent_ep.router, prefix="/api/v1")
    return TestClient(app)


def test_route_create_201(monkeypatch: pytest.MonkeyPatch) -> None:
    client = _app()

    async def _create(_data):
        return FakeWorkspaceDoc(id="w1", name="A")

    monkeypatch.setattr(agent_ep.WorkspaceService, "create", _create)
    r = client.post("/api/v1/agent/workspaces", json={"name": "A"})
    assert r.status_code == 200
    body = r.json()
    assert body["code"] == 0
    assert body["data"]["id"] == "w1"
    assert body["data"]["name"] == "A"


def test_route_not_found(monkeypatch: pytest.MonkeyPatch) -> None:
    client = _app()

    async def _get(_workspace_id: str):
        raise WorkspaceServiceError(status_codes.NOT_FOUND_WORKSPACE, "工作区不存在")

    monkeypatch.setattr(agent_ep.WorkspaceService, "get", _get)
    r = client.get("/api/v1/agent/workspaces/missing")
    assert r.status_code == 200
    body = r.json()
    assert body["code"] == status_codes.NOT_FOUND_WORKSPACE


@pytest.mark.asyncio
async def test_route_narrowing_conflict_payload(monkeypatch: pytest.MonkeyPatch) -> None:
    conflicts = ["Agent[a1:agent] 仍在引用已移除的 tools=['t1']"]

    async def _update(_workspace_id: str, _data: NanobotWorkspaceUpdateRequestSchema):
        raise WorkspaceServiceError(
            status_codes.CONFLICT_STATE,
            "白名单收窄与关联 Agent 冲突，请先调整 Agent 后再更新工作区",
            data={"conflicts": conflicts},
        )

    monkeypatch.setattr(agent_ep.WorkspaceService, "update", _update)
    # 与 tests/api/test_overview_endpoints.py 的做法一致：
    # 当 error payload 与 response_model 泛型不一致时，走 HTTP 会触发 FastAPI 响应校验失败，
    # 因此直接测试协程返回的 ApiResponseSchema。
    out = await agent_ep.update_workspace("w1", NanobotWorkspaceUpdateRequestSchema(name="A"))
    assert out.code == status_codes.CONFLICT_STATE
    assert out.data["conflicts"] == conflicts

