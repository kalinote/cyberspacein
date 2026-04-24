"""MIGRATION_PLAN §12.15：AnalystService.build_bot 装配（hooks + tools + suffix）。"""

from __future__ import annotations

from dataclasses import dataclass, field
from types import SimpleNamespace
from typing import Any, Iterable
from unittest.mock import AsyncMock

import pytest

import app.service.analyst.service as service_module


@dataclass
class FakeAgent:
    id: str = "a1"
    workspace_id: str = "w1"
    model_config_id: str = "m1"
    prompt_template_id: str = "p1"
    tools: list[str] = field(default_factory=lambda: ["notify_user", "write_todos"])
    mcp_servers: list[str] = field(default_factory=lambda: ["srv1"])
    current_session_id: str | None = None
    steps: list[dict] = field(default_factory=list)
    todos: list[dict] = field(default_factory=list)
    pending_approval: dict | None = None
    result: dict | None = None
    updated_at: Any = None

    async def save(self) -> None:
        return None


@dataclass
class FakeWorkspace:
    id: str = "w1"
    enabled_mcp_servers: dict[str, dict] = field(default_factory=lambda: {"srv1": {"command": "npx"}, "srv2": {"command": "node"}})


class FakeRegistry:
    def __init__(self) -> None:
        self._tools: dict[str, Any] = {}

    def register(self, tool: Any) -> None:
        self._tools[tool.name] = tool


class FakeBot:
    def __init__(self, provider: Any, hooks: list[Any]) -> None:
        self.loop = SimpleNamespace(
            tools=FakeRegistry(),
            context=SimpleNamespace(extra_system_suffix=""),
            provider=provider,
            _extra_hooks=list(hooks),
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

    # provider/format
    monkeypatch.setattr(service_module, "build_response_format_schema", lambda: {"x": 1})
    monkeypatch.setattr(service_module, "OpenAICompatProvider", lambda **kw: SimpleNamespace(**kw))

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

    # Nanobot.from_components
    def _from_components(**kw: Any) -> Any:
        return FakeBot(provider=kw["provider"], hooks=kw.get("hooks") or [])

    monkeypatch.setattr(service_module.Nanobot, "from_components", staticmethod(_from_components))
    yield


@pytest.mark.asyncio
async def test_build_bot_injects_hooks_and_tools() -> None:
    agent = FakeAgent()
    ws = FakeWorkspace()
    bot, session_id = await service_module.AnalystService.build_bot(agent, ws)

    assert session_id == "sess1"
    assert len(bot.loop._extra_hooks) == 4
    assert set(bot.loop.tools._tools.keys()) == {"notify_user", "write_todos"}
    assert "SYS" in bot.loop.context.extra_system_suffix
    assert service_module.RESULT_FORMAT_INSTRUCTION in bot.loop.context.extra_system_suffix

