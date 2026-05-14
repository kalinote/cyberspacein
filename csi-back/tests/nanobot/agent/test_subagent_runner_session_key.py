"""SubagentManager：子代理 runner 使用独立 session_key 与 workspace。"""

from __future__ import annotations

import asyncio
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.service.nanobot.agent.runner import AgentRunResult
from app.service.nanobot.agent.subagent import SubagentManager


@pytest.mark.asyncio
async def test_subagent_runner_gets_workspace_and_session_key_with_parent() -> None:
    specs: list = []

    async def fake_run(spec) -> AgentRunResult:
        specs.append(spec)
        return AgentRunResult(final_content="ok", messages=[])

    provider = MagicMock()
    provider.get_default_model = MagicMock(return_value="gpt-test")
    bus = MagicMock()
    bus.publish_inbound = AsyncMock()

    mgr = SubagentManager(
        provider=provider,
        workspace=Path("/tmp/sub_ws"),
        bus=bus,
        max_tool_result_chars=8000,
    )
    mgr.runner.run = fake_run

    await mgr.spawn("do work", session_key="mongo-session-99")

    for _ in range(100):
        await asyncio.sleep(0.005)
        if specs:
            break
    assert len(specs) == 1
    sp = specs[0]
    assert sp.workspace == Path("/tmp/sub_ws")
    assert sp.session_key and sp.session_key.startswith("sub:mongo-session-99:")
    assert len(sp.session_key.split(":")) >= 3

    for t in list(mgr._running_tasks.values()):
        t.cancel()
        try:
            await t
        except asyncio.CancelledError:
            pass


@pytest.mark.asyncio
async def test_subagent_runner_session_key_when_no_parent_session() -> None:
    specs: list = []

    async def fake_run(spec) -> AgentRunResult:
        specs.append(spec)
        return AgentRunResult(final_content="ok", messages=[])

    provider = MagicMock()
    provider.get_default_model = MagicMock(return_value="gpt-test")
    bus = MagicMock()
    bus.publish_inbound = AsyncMock()

    mgr = SubagentManager(
        provider=provider,
        workspace=Path("/x"),
        bus=bus,
        max_tool_result_chars=4000,
    )
    mgr.runner.run = fake_run

    await mgr.spawn("task", session_key=None)

    for _ in range(100):
        await asyncio.sleep(0.005)
        if specs:
            break
    assert len(specs) == 1
    assert specs[0].session_key.startswith("sub:none:")

    for t in list(mgr._running_tasks.values()):
        t.cancel()
        try:
            await t
        except asyncio.CancelledError:
            pass
