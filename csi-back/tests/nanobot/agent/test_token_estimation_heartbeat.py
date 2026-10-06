"""验证 token 估算缓慢时，分析 Worker 仍能按时续租。"""

import asyncio
import threading
from datetime import datetime, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest

from app.service.analyst import runtime_worker
from app.service.analyst.runtime_store import AnalystRuntimeStore
from app.service.nanobot.agent import memory, runner
from app.service.nanobot.agent.tools.registry import ToolRegistry
from app.service.nanobot.providers.base import LLMResponse
from app.service.nanobot.session.manager import Session


@pytest.mark.parametrize("stage", ["runner", "consolidator", "boundary"])
async def test_slow_token_estimation_keeps_runtime_lease(monkeypatch, stage):
    """用真实心跳监视器验证三处同步估算不会阻塞续租。"""
    worker = runtime_worker.AnalystRuntimeWorker()
    run = SimpleNamespace(id="test-run", session_id="test-session")
    current = SimpleNamespace(
        active=True,
        worker_id=worker.worker_id,
        lease_token="test-lease",
        lease_expires_at=datetime.now() + timedelta(seconds=3),
        desired_state=runtime_worker.NanobotRunDesiredStateEnum.RUNNING,
    )
    released = threading.Event()
    finished_after_heartbeat = []

    def slow_estimate(*_args, **_kwargs):
        """模拟阻塞的词表加载或 token 编码，等待心跳释放。"""
        finished_after_heartbeat.append(released.wait(timeout=4))
        return None if stage == "boundary" else (100, "test")

    async def renew_lease(*_args):
        """模拟数据库续租成功，并放行正在等待的估算。"""
        current.lease_expires_at = datetime.now() + timedelta(seconds=3)
        released.set()
        return True

    renew = AsyncMock(side_effect=renew_lease)
    monkeypatch.setattr(
        runtime_worker, "settings",
        SimpleNamespace(
            NANOBOT_RUNTIME_HEARTBEAT_SECONDS=1,
            NANOBOT_RUNTIME_POLL_SECONDS=0.2,
        ),
    )
    monkeypatch.setattr(AnalystRuntimeStore, "get", AsyncMock(return_value=current))
    monkeypatch.setattr(AnalystRuntimeStore, "renew_lease", renew)
    monkeypatch.setattr(runtime_worker.AnalystService, "_owned_run_leases", {})
    monkeypatch.setattr(runtime_worker.AnalystService, "_cancel_reasons", {})
    provider = SimpleNamespace(
        generation=SimpleNamespace(max_tokens=1000),
        chat_with_retry=AsyncMock(return_value=LLMResponse(content="测试完成")),
    )
    if stage == "runner":
        monkeypatch.setattr(runner, "estimate_prompt_tokens_chain", slow_estimate)
        operation = runner.AgentRunner(provider).run(runner.AgentRunSpec(
            initial_messages=[{"role": "user", "content": "只读测试"}],
            tools=ToolRegistry(),
            model="test",
            max_iterations=1,
            max_tool_result_chars=1000,
            context_window_tokens=10000,
        ))
    else:
        consolidator = memory.Consolidator(
            store=Mock(), provider=provider, model="test", sessions=Mock(),
            context_window_tokens=10000, max_completion_tokens=1000,
            build_messages=Mock(return_value=[{"role": "user", "content": "测试"}]),
            get_tool_definitions=Mock(return_value=[]), prompt_repo=Mock(),
        )
        if stage == "consolidator":
            monkeypatch.setattr(memory, "estimate_prompt_tokens_chain", slow_estimate)
        else:
            monkeypatch.setattr(
                consolidator, "estimate_session_prompt_tokens",
                Mock(return_value=(9500, "test")),
            )
            monkeypatch.setattr(consolidator, "pick_consolidation_boundary", slow_estimate)
        operation = consolidator.maybe_consolidate_by_tokens(Session(
            id="test-session", agent_id="test-agent", workspace_id="test-workspace",
            messages=[{"role": "user", "content": "测试"}],
        ))

    task = asyncio.create_task(operation)
    monitor = asyncio.create_task(
        worker._monitor_lease(run, "test-lease", task, SimpleNamespace()),
    )
    try:
        results = await asyncio.gather(task, monitor, return_exceptions=True)
    finally:
        released.set()
    assert finished_after_heartbeat == [True]
    assert renew.await_count >= 1
    assert results[1] is False
    assert not isinstance(results[0], BaseException)
