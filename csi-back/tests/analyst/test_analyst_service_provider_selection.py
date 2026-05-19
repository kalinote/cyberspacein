"""AnalystService.build_bot 的 provider 装配。"""

from __future__ import annotations

from dataclasses import dataclass, field
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock

import pytest

import app.service.analyst.service as service_module


@dataclass
class FakeAgent:
    id: str = "a1"
    workspace_id: str = "w1"
    model_config_id: str = "m1"
    prompt_template_id: str = "p1"
    tools: list[str] = field(default_factory=list)
    mcp_servers: list[str] = field(default_factory=list)
    agent_builtin_prompt_ids: list[str] = field(default_factory=list)
    updated_at: Any = None

    async def save(self) -> None:
        return None


@dataclass
class FakeWorkspace:
    id: str = "w1"
    enabled_mcp_servers: dict[str, dict] = field(default_factory=dict)


@pytest.mark.asyncio
async def test_build_bot_always_uses_openai_compat_provider(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        service_module.AgentModelConfigModel,
        "find_one",
        AsyncMock(
            return_value=SimpleNamespace(
                api_key="k",
                base_url="https://api.deepseek.com/",
                model="deepseek-chat",
            )
        ),
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

    monkeypatch.setattr(service_module, "default_analyst_hooks", lambda: [])
    monkeypatch.setattr(service_module, "build_business_tools", lambda _enabled: [])
    monkeypatch.setattr(service_module.AnalystService, "_get_memory_backend", classmethod(lambda cls: object()))
    monkeypatch.setattr(service_module.AnalystService, "_get_session_store", classmethod(lambda cls: object()))

    called: dict[str, dict] = {}

    def _openai_provider(**kw: Any) -> Any:
        called["openai"] = kw
        return SimpleNamespace(**kw)

    monkeypatch.setattr(service_module, "OpenAICompatProvider", _openai_provider)
    class _FakePromptRepo:
        async def resolve_builtin_render_context(
            self,
            doc_ids: list[str],
            **kwargs: Any,
        ) -> dict[str, Any]:
            return {}

        async def render_many_by_ids(self, doc_ids: list[str], **kwargs: Any) -> list[str]:
            return []

    monkeypatch.setattr(service_module, "AgentPromptRepository", lambda: _FakePromptRepo())
    monkeypatch.setattr(
        service_module.Nanobot,
        "from_components",
        staticmethod(
            lambda **kw: SimpleNamespace(
                loop=SimpleNamespace(
                    tools=SimpleNamespace(register=lambda _t: None, has=lambda _n: False),
                    context=SimpleNamespace(
                        extra_system_suffix="",
                        builtin_prompt_sections=[],
                    ),
                    _extra_hooks=[],
                )
            )
        ),
    )

    agent = FakeAgent()
    ws = FakeWorkspace()
    await service_module.AnalystService.build_bot(agent, ws)

    assert "openai" in called
    assert called["openai"].get("response_format") in (None, {})
    assert called["openai"].get("api_key") == "k"
