"""AgentLoop.close_mcp 在关闭时取消后台任务。"""

from __future__ import annotations

import asyncio

import pytest

from app.service.nanobot.agent.loop import AgentLoop


class _MinimalLoop:
    def __init__(self) -> None:
        self._background_tasks: list[asyncio.Task] = []
        self._mcp_stacks: dict = {}


_MinimalLoop._schedule_background = AgentLoop._schedule_background
_MinimalLoop.close_mcp = AgentLoop.close_mcp


@pytest.mark.asyncio
async def test_close_mcp_cancels_background_tasks() -> None:
    loop = _MinimalLoop()
    loop._schedule_background(asyncio.sleep(3600))
    assert len(loop._background_tasks) == 1
    bg_task = loop._background_tasks[0]

    await asyncio.wait_for(loop.close_mcp(), timeout=1.0)

    assert bg_task.cancelled() or bg_task.done()
    assert loop._background_tasks == []
