"""AnalystService.send_message：已结束会话续聊。"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from datetime import datetime
from types import SimpleNamespace
from typing import Any, Iterable
from unittest.mock import AsyncMock, MagicMock

import pytest

import app.core.config as cfg
import app.service.analyst.hitl as hitl_module
import app.service.analyst.service as service_module
import app.utils.status_codes as status_codes
from app.schemas.agent.nanobot_agent import AgentServiceError
from app.schemas.constants import NanobotSessionStatusEnum


@dataclass
class FakeSessionDoc:
    id: str
    agent_id: str = "a1"
    workspace_id: str = "w1"
    status: NanobotSessionStatusEnum = NanobotSessionStatusEnum.COMPLETED
    user_prompt: str | None = None
    steps: list[dict] = field(default_factory=list)
    todos: list[dict] = field(default_factory=list)
    pending_approval: dict | None = None
    result: dict | None = None
    error_message: str | None = None
    finished_at: datetime | None = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)

    async def save(self) -> None:
        FakeNanobotSessionModel._docs[self.id] = self


class FakeNanobotSessionModel:
    _docs: dict[str, FakeSessionDoc] = {}

    @classmethod
    async def find_one(cls, query: dict[str, Any]) -> FakeSessionDoc | None:
        return cls._docs.get(query.get("_id"))

    @classmethod
    def find(cls, *_a: Any, **_k: Any) -> Any:
        class _Q:
            async def count(self) -> int:
                return sum(
                    1
                    for d in FakeNanobotSessionModel._docs.values()
                    if d.agent_id == "a1"
                    and d.status == NanobotSessionStatusEnum.RUNNING
                )

        return _Q()


@pytest.fixture(autouse=True)
def _reset(monkeypatch: pytest.MonkeyPatch) -> Iterable[None]:
    monkeypatch.setattr(cfg.settings, "NANOBOT_AGENT_MAX_PARALLEL_SESSIONS", 0, raising=False)
    service_module.AnalystService._bots = {}
    service_module.AnalystService._running_tasks = {}
    service_module.AnalystService._cancel_reasons = {}
    service_module.AnalystService._bots_lock = asyncio.Lock()
    service_module.AnalystService._task_lock = asyncio.Lock()
    hitl_module.HitlService._pending_resumes = {}
    hitl_module.HitlService._resume_lock = asyncio.Lock()
    FakeNanobotSessionModel._docs = {}

    monkeypatch.setattr(hitl_module, "NanobotSessionModel", FakeNanobotSessionModel)
    monkeypatch.setattr(service_module, "NanobotSessionModel", FakeNanobotSessionModel)
    monkeypatch.setattr(service_module.AnalystService, "broadcast_sse", AsyncMock())

    store = MagicMock()
    store.invalidate = AsyncMock()
    monkeypatch.setattr(
        service_module.AnalystService,
        "_get_session_store",
        classmethod(lambda cls: store),
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

    assemble_mock = AsyncMock(return_value=object())
    monkeypatch.setattr(service_module.AnalystService, "_assemble_bot", assemble_mock)

    launch_calls: list[dict[str, Any]] = []

    async def _launch(**kwargs: Any) -> None:
        launch_calls.append(kwargs)

    monkeypatch.setattr(service_module.AnalystService, "_launch_background_run", _launch)

    yield {"assemble_mock": assemble_mock, "launch_calls": launch_calls, "store": store}


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "status",
    [
        NanobotSessionStatusEnum.COMPLETED,
        NanobotSessionStatusEnum.FAILED,
        NanobotSessionStatusEnum.CANCELLED,
    ],
)
async def test_send_message_allowed_statuses(
    status: NanobotSessionStatusEnum, _reset: dict[str, Any]
) -> None:
    FakeNanobotSessionModel._docs["s1"] = FakeSessionDoc(id="s1", status=status)
    sid = await service_module.AnalystService.send_message("a1", "s1", "继续分析")
    assert sid == "s1"
    doc = FakeNanobotSessionModel._docs["s1"]
    assert doc.status == NanobotSessionStatusEnum.RUNNING
    assert doc.user_prompt == "继续分析"
    assert doc.finished_at is None
    assert doc.error_message is None
    _reset["store"].invalidate.assert_awaited_once_with("s1")
    _reset["assemble_mock"].assert_awaited_once()
    assert _reset["launch_calls"][0]["session_id"] == "s1"
    assert _reset["launch_calls"][0]["user_prompt"] == "继续分析"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "status,msg_substr",
    [
        (NanobotSessionStatusEnum.RUNNING, "运行中"),
        (NanobotSessionStatusEnum.AWAITING_APPROVAL, "运行中"),
        (NanobotSessionStatusEnum.PAUSED, "暂停"),
        (NanobotSessionStatusEnum.IDLE, "首轮"),
    ],
)
async def test_send_message_rejects_disallowed_status(
    status: NanobotSessionStatusEnum, msg_substr: str
) -> None:
    FakeNanobotSessionModel._docs["s1"] = FakeSessionDoc(id="s1", status=status)
    with pytest.raises(AgentServiceError) as ei:
        await service_module.AnalystService.send_message("a1", "s1", "hi")
    assert ei.value.code == status_codes.CONFLICT_STATE
    assert msg_substr in ei.value.message


@pytest.mark.asyncio
async def test_send_message_rejects_active_task() -> None:
    FakeNanobotSessionModel._docs["s1"] = FakeSessionDoc(
        id="s1", status=NanobotSessionStatusEnum.COMPLETED
    )
    loop = asyncio.get_running_loop()
    fut: asyncio.Future[None] = loop.create_future()
    service_module.AnalystService._running_tasks["s1"] = fut
    try:
        with pytest.raises(AgentServiceError) as ei:
            await service_module.AnalystService.send_message("a1", "s1", "hi")
        assert ei.value.code == status_codes.CONFLICT_STATE
        assert "运行中" in ei.value.message
    finally:
        service_module.AnalystService._running_tasks.pop("s1", None)


@pytest.mark.asyncio
async def test_send_message_not_found_session() -> None:
    with pytest.raises(AgentServiceError) as ei:
        await service_module.AnalystService.send_message("a1", "missing", "hi")
    assert ei.value.code == status_codes.NOT_FOUND_AGENT


@pytest.mark.asyncio
async def test_send_message_wrong_agent() -> None:
    FakeNanobotSessionModel._docs["s1"] = FakeSessionDoc(
        id="s1", agent_id="other", status=NanobotSessionStatusEnum.COMPLETED
    )
    with pytest.raises(AgentServiceError) as ei:
        await service_module.AnalystService.send_message("a1", "s1", "hi")
    assert ei.value.code == status_codes.NOT_FOUND_AGENT


@pytest.mark.asyncio
async def test_send_message_parallel_cap(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(cfg.settings, "NANOBOT_AGENT_MAX_PARALLEL_SESSIONS", 1, raising=False)
    FakeNanobotSessionModel._docs["s1"] = FakeSessionDoc(
        id="s1", status=NanobotSessionStatusEnum.COMPLETED
    )
    FakeNanobotSessionModel._docs["s2"] = FakeSessionDoc(
        id="s2", status=NanobotSessionStatusEnum.RUNNING
    )

    with pytest.raises(AgentServiceError) as ei:
        await service_module.AnalystService.send_message("a1", "s1", "hi")
    assert ei.value.code == status_codes.CONFLICT_STATE
    assert "并行上限" in ei.value.message
