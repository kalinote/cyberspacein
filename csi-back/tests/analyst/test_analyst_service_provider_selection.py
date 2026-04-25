"""AnalystService.build_bot 的 provider 选择策略测试。"""

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
    enabled_mcp_servers: dict[str, dict] = field(default_factory=dict)


@pytest.mark.asyncio
async def test_build_bot_uses_deepseek_provider_when_base_url_matches(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        service_module.AgentModelConfigModel,
        "find_one",
        AsyncMock(return_value=SimpleNamespace(api_key="k", base_url="https://api.deepseek.com/", model="deepseek-chat")),
    )
    monkeypatch.setattr(
        service_module.AgentPromptTemplateModel,
        "find_one",
        AsyncMock(return_value=SimpleNamespace(system_prompt="SYS")),
    )
    monkeypatch.setattr(service_module, "generate_id", lambda _s: "sess1")
    monkeypatch.setattr(service_module, "default_analyst_hooks", lambda: [])
    monkeypatch.setattr(service_module, "build_business_tools", lambda _enabled: [])
    monkeypatch.setattr(service_module.AnalystService, "_get_memory_backend", classmethod(lambda cls: object()))
    monkeypatch.setattr(service_module.AnalystService, "_get_session_store", classmethod(lambda cls: object()))

    called: dict[str, dict] = {}

    def _deepseek_provider(**kw: Any) -> Any:
        called["deepseek"] = kw
        return SimpleNamespace(**kw)

    def _openai_provider(**kw: Any) -> Any:
        called["openai"] = kw
        return SimpleNamespace(**kw)

    monkeypatch.setattr(service_module, "DeepSeekProvider", _deepseek_provider)
    monkeypatch.setattr(service_module, "OpenAICompatProvider", _openai_provider)
    monkeypatch.setattr(service_module.Nanobot, "from_components", staticmethod(lambda **kw: SimpleNamespace(loop=SimpleNamespace(tools=SimpleNamespace(register=lambda _t: None), context=SimpleNamespace(extra_system_suffix=""), _extra_hooks=[]))))

    agent = FakeAgent()
    ws = FakeWorkspace()
    await service_module.AnalystService.build_bot(agent, ws)

    assert "deepseek" in called
    assert "openai" not in called

