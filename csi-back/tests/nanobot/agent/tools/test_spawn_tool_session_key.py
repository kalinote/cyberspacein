"""SpawnTool：多会话并行时 session_key 优先使用 Nanobot 会话 id。"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from app.service.nanobot.agent.tools.spawn import SpawnTool


@pytest.mark.asyncio
async def test_spawn_uses_nanobot_session_id_when_set() -> None:
    mgr = MagicMock()
    mgr.spawn = AsyncMock(return_value="ok")
    tool = SpawnTool(manager=mgr)
    tool.set_context("cli", "direct", nanobot_session_id="mongo-sess-1")
    out = await tool.execute("task-a")
    assert out == "ok"
    mgr.spawn.assert_awaited_once()
    kw = mgr.spawn.await_args.kwargs
    assert kw["session_key"] == "mongo-sess-1"
    assert kw["origin_channel"] == "cli"
    assert kw["origin_chat_id"] == "direct"


@pytest.mark.asyncio
async def test_spawn_falls_back_to_channel_chat_id() -> None:
    mgr = MagicMock()
    mgr.spawn = AsyncMock(return_value="ok")
    tool = SpawnTool(manager=mgr)
    tool.set_context("feishu", "oc_1")
    out = await tool.execute("task-b")
    assert out == "ok"
    assert mgr.spawn.await_args.kwargs["session_key"] == "feishu:oc_1"
