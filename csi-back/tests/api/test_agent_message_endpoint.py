"""POST /api/v1/agent/message 路由契约测试。"""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest
from fastapi import FastAPI
from starlette.testclient import TestClient

import app.utils.status_codes as status_codes
from app.api.v1.endpoints import agent as agent_ep
import app.api.v1.endpoints.agent.runtime as runtime_ep
from app.schemas.agent.nanobot_agent import AgentServiceError


def _app() -> TestClient:
    app = FastAPI()
    app.include_router(agent_ep.router, prefix="/api/v1")
    return TestClient(app)


def test_route_message_success(monkeypatch: pytest.MonkeyPatch) -> None:
    client = _app()

    async def _send_message(*, agent_id: str, session_id: str, user_prompt: str, context: dict):
        assert agent_id == "a1"
        assert session_id == "s1"
        assert user_prompt == "你好 v"
        assert context == {"k": "v"}
        return "s1"

    monkeypatch.setattr(runtime_ep.AnalystService, "send_message", _send_message)
    r = client.post(
        "/api/v1/agent/message",
        json={
            "agent_id": "a1",
            "session_id": "s1",
            "user_prompt": "你好 {{ k }}",
            "extra_context": {"k": "v"},
        },
    )
    assert r.status_code == 200
    body = r.json()
    assert body["code"] == 0
    assert body["data"]["agent_id"] == "a1"
    assert body["data"]["session_id"] == "s1"


def test_route_message_empty_prompt(monkeypatch: pytest.MonkeyPatch) -> None:
    client = _app()
    send_mock = AsyncMock()
    monkeypatch.setattr(runtime_ep.AnalystService, "send_message", send_mock)
    r = client.post(
        "/api/v1/agent/message",
        json={
            "agent_id": "a1",
            "session_id": "s1",
            "user_prompt": "   ",
            "extra_context": {},
        },
    )
    assert r.status_code == 200
    body = r.json()
    assert body["code"] == status_codes.INVALID_ARGUMENT
    send_mock.assert_not_called()


def test_route_message_conflict_running(monkeypatch: pytest.MonkeyPatch) -> None:
    client = _app()

    async def _send_message(**_kwargs):
        raise AgentServiceError(
            status_codes.CONFLICT_STATE,
            "会话仍在运行中，请等待输出完成后再提交消息",
        )

    monkeypatch.setattr(runtime_ep.AnalystService, "send_message", _send_message)
    r = client.post(
        "/api/v1/agent/message",
        json={
            "agent_id": "a1",
            "session_id": "s1",
            "user_prompt": "继续",
        },
    )
    assert r.status_code == 200
    body = r.json()
    assert body["code"] == status_codes.CONFLICT_STATE
