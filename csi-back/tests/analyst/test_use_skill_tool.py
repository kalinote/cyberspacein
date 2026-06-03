from __future__ import annotations

from dataclasses import dataclass, field
from unittest.mock import AsyncMock

import pytest

import app.service.analyst.tools.use_skill as use_skill_module
from app.service.analyst.context import current_agent_id
from app.service.analyst.tools.use_skill import UseSkillTool


@dataclass
class FakeAgent:
    id: str = "a1"
    workspace_id: str = "w1"
    skills: list[str] = field(default_factory=lambda: ["skill:1"])


@dataclass
class FakeWorkspace:
    id: str = "w1"
    enabled_skills: list[str] = field(default_factory=lambda: ["skill:1"])


@pytest.mark.asyncio
async def test_use_skill_allowed(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        use_skill_module.NanobotAgentModel,
        "find_one",
        AsyncMock(return_value=FakeAgent()),
    )
    monkeypatch.setattr(
        use_skill_module.NanobotWorkspaceModel,
        "find_one",
        AsyncMock(return_value=FakeWorkspace()),
    )
    monkeypatch.setattr(
        use_skill_module.SkillService,
        "load_for_tool",
        AsyncMock(return_value=("skill body", None)),
    )
    monkeypatch.setattr(
        use_skill_module.SkillService,
        "get_by_id",
        AsyncMock(return_value=type("S", (), {"name": "demo"})()),
    )

    token = current_agent_id.set("a1")
    try:
        out = await UseSkillTool().execute(skill_id="skill:1")
    finally:
        current_agent_id.reset(token)

    assert "skill body" in out
    assert "skill:1" in out


@pytest.mark.asyncio
async def test_use_skill_denied_when_not_in_whitelist(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        use_skill_module.NanobotAgentModel,
        "find_one",
        AsyncMock(return_value=FakeAgent(skills=[])),
    )
    monkeypatch.setattr(
        use_skill_module.NanobotWorkspaceModel,
        "find_one",
        AsyncMock(return_value=FakeWorkspace()),
    )

    token = current_agent_id.set("a1")
    try:
        out = await UseSkillTool().execute(skill_id="skill:1")
    finally:
        current_agent_id.reset(token)

    assert "Error" in out
    assert "白名单" in out
