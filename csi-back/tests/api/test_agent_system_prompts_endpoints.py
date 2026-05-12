from __future__ import annotations

from datetime import datetime
from typing import Any

import pytest
from fastapi import FastAPI
from starlette.testclient import TestClient

import app.utils.status_codes as status_codes
from app.api.v1.endpoints import agent as agent_ep
import app.api.v1.endpoints.agent.configs_templates as templates_ep
from app.schemas.agent.configs import SystemPromptCreateRequestSchema
from app.schemas.constants import NanobotMemoryDocTypeEnum


class FakeSystemPromptDoc:
    def __init__(
        self,
        *,
        id: str,
        workspace_id: str,
        type: NanobotMemoryDocTypeEnum,
        content: str,
    ) -> None:
        self.id = id
        self.workspace_id = workspace_id
        self.type = type
        self.content = content
        self.created_at = datetime(2026, 1, 1, 0, 0, 0)
        self.updated_at = datetime(2026, 1, 1, 0, 0, 0)


def _app() -> TestClient:
    app = FastAPI()
    app.include_router(agent_ep.router, prefix="/api/v1")
    return TestClient(app)


def test_create_system_prompt(monkeypatch: pytest.MonkeyPatch) -> None:
    client = _app()

    async def _create(data: SystemPromptCreateRequestSchema) -> FakeSystemPromptDoc:
        assert data.workspace_id == "w1"
        assert data.type is NanobotMemoryDocTypeEnum.MEMORY
        return FakeSystemPromptDoc(
            id="sp1",
            workspace_id=data.workspace_id,
            type=data.type,
            content=data.content,
        )

    monkeypatch.setattr(templates_ep.SystemPromptService, "create", _create)
    r = client.post(
        "/api/v1/agent/configs/system-prompts",
        json={"workspace_id": "w1", "type": "memory", "content": "规则"},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["code"] == 0
    assert body["data"]["id"] == "sp1"
    assert body["data"]["type"] == "memory"


def test_create_system_prompt_conflict(monkeypatch: pytest.MonkeyPatch) -> None:
    client = _app()

    async def _create(_data: SystemPromptCreateRequestSchema) -> Any:
        raise templates_ep.SystemPromptServiceError(
            status_codes.CONFLICT_EXISTS,
            "系统指令模板已存在",
        )

    monkeypatch.setattr(templates_ep.SystemPromptService, "create", _create)
    r = client.post(
        "/api/v1/agent/configs/system-prompts",
        json={"workspace_id": "w1", "type": "memory", "content": "规则"},
    )
    assert r.status_code == 200
    assert r.json()["code"] == status_codes.CONFLICT_EXISTS


def test_get_system_prompt_list_filters(monkeypatch: pytest.MonkeyPatch) -> None:
    client = _app()

    async def _list_page(
        *,
        page: int,
        page_size: int,
        workspace_id: str | None = None,
        type: NanobotMemoryDocTypeEnum | None = None,
        search: str | None = None,
    ) -> tuple[list[FakeSystemPromptDoc], int]:
        assert page == 2 and page_size == 3
        assert workspace_id == "w1"
        assert type is NanobotMemoryDocTypeEnum.SOUL
        assert search == "报告"
        return (
            [
                FakeSystemPromptDoc(
                    id="sp1",
                    workspace_id="w1",
                    type=NanobotMemoryDocTypeEnum.SOUL,
                    content="报告风格",
                )
            ],
            1,
        )

    monkeypatch.setattr(templates_ep.SystemPromptService, "list_page", _list_page)
    r = client.get(
        "/api/v1/agent/configs/system-prompts?page=2&page_size=3&workspace_id=w1&type=soul&search=报告"
    )
    assert r.status_code == 200
    body = r.json()
    assert body["total"] == 1
    assert body["items"][0]["content"] == "报告风格"


def test_get_system_prompt_detail_not_found(monkeypatch: pytest.MonkeyPatch) -> None:
    client = _app()

    async def _get(_system_prompt_id: str) -> Any:
        raise templates_ep.SystemPromptServiceError(
            status_codes.NOT_FOUND,
            "系统指令模板不存在",
        )

    monkeypatch.setattr(templates_ep.SystemPromptService, "get", _get)
    r = client.get("/api/v1/agent/configs/system-prompts/missing")
    assert r.status_code == 200
    assert r.json()["code"] == status_codes.NOT_FOUND


def test_delete_system_prompt(monkeypatch: pytest.MonkeyPatch) -> None:
    client = _app()
    called: dict[str, str] = {}

    async def _delete(system_prompt_id: str) -> None:
        called["id"] = system_prompt_id

    monkeypatch.setattr(templates_ep.SystemPromptService, "delete", _delete)
    r = client.delete("/api/v1/agent/configs/system-prompts/sp1")
    assert r.status_code == 200
    body = r.json()
    assert body["code"] == 0
    assert body["message"] == "删除成功"
    assert called == {"id": "sp1"}
