"""GET /agent/sessions 路由契约测试（不连 DB）。"""

from __future__ import annotations

from datetime import datetime

import pytest
from fastapi import FastAPI
from starlette.testclient import TestClient

from app.api.v1.endpoints import agent as agent_ep
import app.api.v1.endpoints.agent.sessions as sessions_ep
from app.schemas.agent.nanobot_session import NanobotSessionSchema
from app.schemas.constants import NanobotSessionStatusEnum


def _app() -> TestClient:
    app = FastAPI()
    app.include_router(agent_ep.router, prefix="/api/v1")
    return TestClient(app)


def test_route_list_filter_query(monkeypatch: pytest.MonkeyPatch) -> None:
    client = _app()
    sample = NanobotSessionSchema(
        id="s1",
        agent_id="a1",
        agent_name="Agent1",
        workspace_id="w1",
        status=NanobotSessionStatusEnum.RUNNING,
        created_at=datetime(2026, 1, 1),
        updated_at=datetime(2026, 1, 1),
    )

    async def _list_page(
        *,
        page: int,
        page_size: int,
        agent_id: str | None = None,
        workspace_id: str | None = None,
        status: NanobotSessionStatusEnum | None = None,
    ):
        assert page == 2 and page_size == 5
        assert agent_id == "a1"
        assert workspace_id == "w1"
        assert status is NanobotSessionStatusEnum.COMPLETED
        return ([sample], 1)

    monkeypatch.setattr(sessions_ep.SessionService, "list_page", _list_page)
    r = client.get(
        "/api/v1/agent/sessions"
        "?page=2&page_size=5&agent_id=a1&workspace_id=w1&status=completed"
    )
    assert r.status_code == 200
    body = r.json()
    assert body["total"] == 1
    assert body["page"] == 2
    item = body["items"][0]
    assert item["id"] == "s1"
    assert item["agent_name"] == "Agent1"
    assert "steps" not in item
    assert "todos" not in item
    assert "user_prompt" not in item
