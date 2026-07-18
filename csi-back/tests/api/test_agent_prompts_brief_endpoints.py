"""GET /agent/configs/filter/agent-prompts"""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest
from fastapi.testclient import TestClient

from app.core.route_permissions import authorize_registered_route
from app.main import app

client = TestClient(app)


@pytest.mark.parametrize(
    "items",
    [
        [
            {"id": "111", "name": "identity", "description": "默认"},
            {"id": "222", "name": "_internal", "description": "应被过滤"},
        ],
    ],
)
def test_list_agent_prompt_brief(monkeypatch: pytest.MonkeyPatch, items: list[dict]) -> None:
    from app.api.v1.endpoints.agent import configs_templates as ep

    monkeypatch.setitem(app.dependency_overrides, authorize_registered_route, lambda: None)
    monkeypatch.setattr(
        ep.SystemPromptService,
        "list_agent_prompt_brief",
        AsyncMock(return_value=items),
    )
    r = client.get("/api/v1/agent/configs/filter/agent-prompts")
    assert r.status_code == 200
    body = r.json()
    assert body["code"] == 0
    assert len(body["data"]) == 2
    names = {row["name"] for row in body["data"]}
    assert names == {"identity", "_internal"}
