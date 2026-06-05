"""MIGRATION_PLAN §12.15：AnalystService.build_bot 装配（hooks + tools + suffix）。"""

from __future__ import annotations

from dataclasses import dataclass, field
from types import SimpleNamespace
from typing import Any, Iterable
from unittest.mock import AsyncMock

import pytest

import app.service.analyst.service as service_module
from app.schemas.constants import NanobotLLMProviderEnum, ReasoningEffortEnum
from app.service.nanobot.providers.base import GenerationSettings, LLMProvider


@dataclass
class FakeAgent:
    id: str = "a1"
    workspace_id: str = "w1"
    model_config_id: str = "m1"
    prompt_template_id: str = "p1"
    llm_provider: NanobotLLMProviderEnum = NanobotLLMProviderEnum.OPENAI_COMPAT
    llm_config: dict[str, Any] = field(default_factory=dict)
    reasoning_effort: ReasoningEffortEnum | None = None
    tools: list[str] = field(default_factory=lambda: ["notify_user", "write_todos"])
    skills: list[str] = field(default_factory=list)
    mcp_servers: list[str] = field(default_factory=lambda: ["srv1"])
    agent_builtin_prompt_ids: list[str] = field(default_factory=list)
    updated_at: Any = None

    async def save(self) -> None:
        return None


@dataclass
class FakeWorkspace:
    id: str = "w1"
    enabled_skills: list[str] = field(default_factory=list)
    enabled_mcp_servers: dict[str, dict] = field(default_factory=lambda: {"srv1": {"command": "npx"}, "srv2": {"command": "node"}})


class FakeRegistry:
    def __init__(self) -> None:
        self._tools: dict[str, Any] = {}

    def register(self, tool: Any) -> None:
        self._tools[tool.name] = tool


class FakeBot:
    def __init__(self, **kw: Any) -> None:
        self.loop = SimpleNamespace(
            tools=FakeRegistry(),
            context=SimpleNamespace(
                extra_system_suffix="",
                builtin_prompt_sections=list(kw.get("builtin_prompt_sections") or []),
                always_skills_content=kw.get("always_skills_content", ""),
            ),
            provider=kw["provider"],
            _extra_hooks=list(kw.get("hooks") or []),
        )


@pytest.fixture(autouse=True)
def _patch_deps(monkeypatch: pytest.MonkeyPatch) -> Iterable[None]:
    # models
    monkeypatch.setattr(
        service_module.AgentModelConfigModel,
        "find_one",
        AsyncMock(return_value=SimpleNamespace(api_key="k", base_url="http://x", model="gpt")),
    )
    monkeypatch.setattr(
        service_module.AgentPromptTemplateModel,
        "find_one",
        AsyncMock(return_value=SimpleNamespace(system_prompt="SYS")),
    )
    monkeypatch.setattr(service_module, "generate_id", lambda _s: "sess1")

    class _StubSession:
        def __init__(self, **kw: Any) -> None:
            pass

        async def insert(self) -> None:
            return None

    monkeypatch.setattr(service_module, "NanobotSessionModel", lambda **kw: _StubSession(**kw))

    class _ProviderStub(LLMProvider):
        def __init__(self, **kw: Any) -> None:
            super().__init__(api_key=kw.get("api_key"), api_base=kw.get("api_base"))
            self.default_model = str(kw.get("default_model") or "gpt")
            self._extra_body: dict[str, Any] = {}

        async def chat(self, *args: Any, **kwargs: Any) -> Any:
            raise NotImplementedError

        @property
        def extra_body(self) -> dict[str, Any]:
            return dict(self._extra_body)

        def set_extra_body(self, body: dict[str, Any] | None) -> None:
            self._extra_body = dict(body or {})

        def get_default_model(self) -> str:
            return self.default_model

    monkeypatch.setattr(service_module, "OpenAICompatProvider", lambda **kw: _ProviderStub(**kw))

    # memory/session singletons
    monkeypatch.setattr(service_module.AnalystService, "_get_memory_backend", classmethod(lambda cls: object()))
    monkeypatch.setattr(service_module.AnalystService, "_get_session_store", classmethod(lambda cls: object()))

    # hooks + tools builder
    sentinel_hooks = [object(), object(), object(), object()]
    monkeypatch.setattr(service_module, "default_analyst_hooks", lambda: sentinel_hooks)
    monkeypatch.setattr(
        service_module,
        "build_business_tools",
        lambda enabled: [SimpleNamespace(name=n) for n in enabled],
    )

    class _FakePromptRepo:
        async def resolve_builtin_render_context(
            self,
            doc_ids: list[str],
            **kwargs: Any,
        ) -> dict[str, Any]:
            return {"channel": kwargs.get("channel", "cli")}

        async def render_many_by_ids(self, doc_ids: list[str], **kwargs: Any) -> list[str]:
            return [f"builtin:{i}" for i in doc_ids]

    monkeypatch.setattr(
        service_module,
        "AgentPromptRepository",
        lambda: _FakePromptRepo(),
    )

    def _from_components(**kw: Any) -> Any:
        return FakeBot(**kw)

    monkeypatch.setattr(service_module.Nanobot, "from_components", staticmethod(_from_components))

    monkeypatch.setattr(
        service_module.SkillService,
        "load_always_content",
        AsyncMock(return_value=""),
    )
    monkeypatch.setattr(
        service_module.SkillService,
        "list_enabled_for_agent",
        AsyncMock(return_value=[]),
    )
    monkeypatch.setattr(
        service_module.SkillService,
        "build_summary",
        AsyncMock(return_value=""),
    )
    yield


@pytest.mark.asyncio
async def test_build_bot_injects_hooks_and_tools() -> None:
    agent = FakeAgent()
    ws = FakeWorkspace()
    bot, session_id = await service_module.AnalystService.build_bot(agent, ws)

    assert session_id == "sess1"
    assert len(bot.loop._extra_hooks) == 4
    assert set(bot.loop.tools._tools.keys()) == {"notify_user", "write_todos", "submit_task_result"}
    assert "SYS" in bot.loop.context.extra_system_suffix
    assert service_module.TASK_SUBMIT_GUIDANCE in bot.loop.context.extra_system_suffix


@pytest.mark.asyncio
async def test_build_bot_applies_reasoning_effort_to_provider_generation() -> None:
    agent = FakeAgent(reasoning_effort=ReasoningEffortEnum.HIGH)
    ws = FakeWorkspace()
    bot, _ = await service_module.AnalystService.build_bot(agent, ws)
    assert bot.loop.provider.generation.reasoning_effort == "high"


@pytest.mark.asyncio
async def test_build_bot_applies_llm_config_to_openai_compat_extra_body() -> None:
    agent = FakeAgent(llm_config={"seed": 42, "top_p": 0.9})
    ws = FakeWorkspace()
    bot, _ = await service_module.AnalystService.build_bot(agent, ws)
    assert getattr(bot.loop.provider, "extra_body", None) == {"seed": 42, "top_p": 0.9}


@pytest.mark.asyncio
async def test_build_bot_builtin_prompt_sections() -> None:
    agent = FakeAgent(agent_builtin_prompt_ids=["id1", "id2"])
    ws = FakeWorkspace()
    bot, _ = await service_module.AnalystService.build_bot(agent, ws)
    assert bot.loop.context.builtin_prompt_sections == ["builtin:id1", "builtin:id2"]

