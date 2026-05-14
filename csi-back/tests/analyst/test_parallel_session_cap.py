"""AnalystService.start_agent：每 Agent 并行 RUNNING 会话上限（NANOBOT_AGENT_MAX_PARALLEL_SESSIONS）。"""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any, Iterable
from unittest.mock import AsyncMock, MagicMock

import pytest

import app.core.config as cfg
import app.service.analyst.service as service_module
import app.utils.status_codes as status_codes
from app.schemas.agent.nanobot_agent import AgentServiceError


@pytest.fixture(autouse=True)
def _reset(monkeypatch: pytest.MonkeyPatch) -> Iterable[None]:
    monkeypatch.setattr(cfg.settings, "NANOBOT_AGENT_MAX_PARALLEL_SESSIONS", 0, raising=False)
    service_module.AnalystService._bots = {}
    service_module.AnalystService._running_tasks = {}
    service_module.AnalystService._bots_lock = __import__("asyncio").Lock()
    service_module.AnalystService._task_lock = __import__("asyncio").Lock()
    service_module.AnalystService._resume_lock = __import__("asyncio").Lock()
    yield


@pytest.mark.asyncio
async def test_start_agent_rejects_when_at_parallel_cap(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(cfg.settings, "NANOBOT_AGENT_MAX_PARALLEL_SESSIONS", 1, raising=False)

    agent = SimpleNamespace(id="a1", workspace_id="w1")
    monkeypatch.setattr(
        service_module.NanobotAgentModel,
        "find_one",
        AsyncMock(return_value=agent),
    )
    monkeypatch.setattr(
        service_module.NanobotWorkspaceModel,
        "find_one",
        AsyncMock(return_value=SimpleNamespace(id="w1")),
    )

    class _RunningQuery:
        async def count(self) -> int:
            return 1

    monkeypatch.setattr(
        service_module.NanobotSessionModel,
        "find",
        lambda *_a, **_k: _RunningQuery(),
    )

    build_mock = AsyncMock()
    monkeypatch.setattr(service_module.AnalystService, "build_bot", build_mock)

    with pytest.raises(AgentServiceError) as ei:
        await service_module.AnalystService.start_agent("a1", "hi")
    assert ei.value.code == status_codes.CONFLICT_STATE
    build_mock.assert_not_called()


@pytest.mark.asyncio
async def test_start_agent_skips_count_when_max_is_zero(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(cfg.settings, "NANOBOT_AGENT_MAX_PARALLEL_SESSIONS", 0, raising=False)

    find_called: list[Any] = []

    def _find(*_a: Any, **_k: Any) -> Any:
        find_called.append(True)

        class _Q:
            async def count(self) -> int:
                return 99

        return _Q()

    monkeypatch.setattr(service_module.NanobotSessionModel, "find", _find)

    agent = SimpleNamespace(id="a1", workspace_id="w1")
    monkeypatch.setattr(
        service_module.NanobotAgentModel,
        "find_one",
        AsyncMock(return_value=agent),
    )
    monkeypatch.setattr(
        service_module.NanobotWorkspaceModel,
        "find_one",
        AsyncMock(return_value=SimpleNamespace(id="w1")),
    )

    bot = MagicMock()
    monkeypatch.setattr(
        service_module.AnalystService,
        "build_bot",
        AsyncMock(return_value=(bot, "sid0")),
    )

    sess = MagicMock(save=AsyncMock())
    monkeypatch.setattr(
        service_module.NanobotSessionModel,
        "find_one",
        AsyncMock(return_value=sess),
    )

    mock_task = MagicMock()
    mock_task.done = lambda: False

    def _fake_create_task(coro: Any, **kw: Any) -> MagicMock:
        coro.close()
        return mock_task

    monkeypatch.setattr(service_module.asyncio, "create_task", _fake_create_task)
    monkeypatch.setattr(service_module.AnalystService, "broadcast_sse", AsyncMock())

    sid = await service_module.AnalystService.start_agent("a1", "hi")
    assert sid == "sid0"
    assert find_called == []


@pytest.mark.asyncio
async def test_start_agent_allows_when_below_cap(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(cfg.settings, "NANOBOT_AGENT_MAX_PARALLEL_SESSIONS", 3, raising=False)

    class _RunningQuery:
        async def count(self) -> int:
            return 1

    monkeypatch.setattr(
        service_module.NanobotSessionModel,
        "find",
        lambda *_a, **_k: _RunningQuery(),
    )

    agent = SimpleNamespace(id="a1", workspace_id="w1")
    monkeypatch.setattr(
        service_module.NanobotAgentModel,
        "find_one",
        AsyncMock(return_value=agent),
    )
    monkeypatch.setattr(
        service_module.NanobotWorkspaceModel,
        "find_one",
        AsyncMock(return_value=SimpleNamespace(id="w1")),
    )

    bot = MagicMock()
    build_bot = AsyncMock(return_value=(bot, "sid2"))
    monkeypatch.setattr(service_module.AnalystService, "build_bot", build_bot)

    sess = MagicMock(save=AsyncMock())
    monkeypatch.setattr(
        service_module.NanobotSessionModel,
        "find_one",
        AsyncMock(return_value=sess),
    )

    mock_task = MagicMock()
    mock_task.done = lambda: False

    def _fake_create_task(coro: Any, **kw: Any) -> MagicMock:
        coro.close()
        return mock_task

    monkeypatch.setattr(service_module.asyncio, "create_task", _fake_create_task)
    monkeypatch.setattr(service_module.AnalystService, "broadcast_sse", AsyncMock())

    sid = await service_module.AnalystService.start_agent("a1", "hi")
    assert sid == "sid2"
    build_bot.assert_awaited_once()
