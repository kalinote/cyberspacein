"""AgentPromptRepository 单元测试。"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.schemas.constants import NANOBOT_BUILTIN_WORKSPACE_ID, NanobotMemoryDocTypeEnum
from app.service.nanobot.agent.prompt_repository import (
    AgentPromptNotFoundError,
    AgentPromptRepository,
    build_builtin_jinja_context,
)


def test_render_template_string() -> None:
    repo = AgentPromptRepository()
    out = repo.render("hello {{ name }}", name="world")
    assert out == "hello world"


def test_render_strips_django_comment_tags() -> None:
    repo = AgentPromptRepository()
    tpl = "{% comment %}备注{% endcomment %}\n{% if system == 'Windows' %}win{% else %}posix{% endif %}"
    out = repo.render(tpl, system="Windows")
    assert "备注" not in out
    assert out.strip() == "win"


def test_build_builtin_jinja_context_keys() -> None:
    ctx = build_builtin_jinja_context(channel="cli", platform_policy="policy")
    assert ctx["channel"] == "cli"
    assert ctx["platform_policy"] == "policy"
    assert "runtime" in ctx
    assert "system" in ctx


@pytest.mark.asyncio
async def test_render_many_by_ids_preserves_order() -> None:
    repo = AgentPromptRepository()
    doc_a = MagicMock()
    doc_a.id = "aaa"
    doc_a.content = "A-{{ x }}"
    doc_a.type = NanobotMemoryDocTypeEnum.AGENT
    doc_a.workspace_id = NANOBOT_BUILTIN_WORKSPACE_ID

    doc_b = MagicMock()
    doc_b.id = "bbb"
    doc_b.content = "B-{{ x }}"
    doc_b.type = NanobotMemoryDocTypeEnum.AGENT
    doc_b.workspace_id = NANOBOT_BUILTIN_WORKSPACE_ID

    mock_find = MagicMock()
    mock_find.to_list = AsyncMock(return_value=[doc_a, doc_b])

    with patch(
        "app.service.nanobot.agent.prompt_repository.NanobotMemoryDocsModel.find",
        return_value=mock_find,
    ):
        parts = await repo.render_many_by_ids(["bbb", "aaa"], x=1)

    assert parts == ["B-1", "A-1"]


@pytest.mark.asyncio
async def test_resolve_builtin_render_context_only_selected_helpers() -> None:
    repo = AgentPromptRepository()
    identity = MagicMock()
    identity.id = "id1"
    identity.name = "identity"
    identity.content = "hi {{ platform_policy }}"
    identity.type = NanobotMemoryDocTypeEnum.AGENT
    identity.workspace_id = NANOBOT_BUILTIN_WORKSPACE_ID

    policy = MagicMock()
    policy.id = "id2"
    policy.name = "_platform_policy"
    policy.content = "{% if system == 'Windows' %}win-policy{% else %}posix{% endif %}"
    policy.type = NanobotMemoryDocTypeEnum.AGENT
    policy.workspace_id = NANOBOT_BUILTIN_WORKSPACE_ID

    skills_tpl = MagicMock()
    skills_tpl.id = "id3"
    skills_tpl.name = "_skills_section"
    skills_tpl.content = "{{ skills_summary }}"
    skills_tpl.type = NanobotMemoryDocTypeEnum.AGENT
    skills_tpl.workspace_id = NANOBOT_BUILTIN_WORKSPACE_ID

    async def _fetch(doc_ids: list[str]) -> list[MagicMock]:
        by_id = {"id1": identity, "id2": policy, "id3": skills_tpl}
        return [by_id[i] for i in doc_ids]

    repo.fetch_many_by_ids = _fetch  # type: ignore[method-assign]

    ctx_identity_only = await repo.resolve_builtin_render_context(
        ["id1"],
        skills_summary="- skill",
        max_iterations=5,
    )
    assert ctx_identity_only.get("platform_policy") == ""
    assert "skills_summary" not in ctx_identity_only

    ctx_with_policy = await repo.resolve_builtin_render_context(["id1", "id2"])
    assert "win-policy" in ctx_with_policy["platform_policy"] or ctx_with_policy["platform_policy"] == "posix"

    ctx_skills = await repo.resolve_builtin_render_context(
        ["id3"],
        skills_summary="- **x**",
    )
    assert ctx_skills["skills_summary"] == "- **x**"


@pytest.mark.asyncio
async def test_render_many_by_ids_missing_raises() -> None:
    repo = AgentPromptRepository()
    mock_find = MagicMock()
    mock_find.to_list = AsyncMock(return_value=[])

    with patch(
        "app.service.nanobot.agent.prompt_repository.NanobotMemoryDocsModel.find",
        return_value=mock_find,
    ):
        with pytest.raises(AgentPromptNotFoundError):
            await repo.render_many_by_ids(["missing-id"])
