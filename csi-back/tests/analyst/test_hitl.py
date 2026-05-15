"""HITL 模块（hitl.py）单元测试。"""
from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Iterable
from unittest.mock import AsyncMock

import pytest

import app.service.analyst.hitl as hitl_module
import app.service.analyst.service as service_module
from app.schemas.agent.hitl import HitlSource, validate_source
from app.schemas.agent.nanobot_agent import AgentServiceError
from app.schemas.constants import NanobotSessionStatusEnum
from app.service.analyst.hitl import (
    HitlOutcome,
    HitlService,
    approval_resolution_label,
    parse_approval_decisions,
)
from app.utils import status_codes


@dataclass
class FakeSessionDoc:
    id: str
    agent_id: str = "a1"
    status: NanobotSessionStatusEnum = NanobotSessionStatusEnum.RUNNING
    pending_approval: dict | None = None
    updated_at: datetime = field(default_factory=datetime.now)

    async def save(self) -> None:
        FakeNanobotSessionModel._docs[self.id] = self


class FakeNanobotSessionModel:
    _docs: dict[str, FakeSessionDoc] = {}

    @classmethod
    async def find_one(cls, query: dict[str, Any]) -> FakeSessionDoc | None:
        return cls._docs.get(query.get("_id"))


@pytest.fixture(autouse=True)
def _patch_session_model(monkeypatch: pytest.MonkeyPatch) -> Iterable[None]:
    FakeNanobotSessionModel._docs = {}
    monkeypatch.setattr(hitl_module, "NanobotSessionModel", FakeNanobotSessionModel)
    yield
    HitlService._pending_resumes.clear()


def test_validate_source_ok() -> None:
    assert validate_source("tool:modify_entity") == "tool:modify_entity"


def test_validate_source_invalid() -> None:
    with pytest.raises(ValueError):
        validate_source("Tool:Modify")


def test_parse_approval_decisions_variants() -> None:
    approved, rejections = parse_approval_decisions(
        [{"action": "approve"}, {"approved": True}, {"action": "reject", "reason": "bad"}]
    )
    assert len(approved) == 2
    assert rejections == ["bad"]


def test_approval_resolution_label_mixed() -> None:
    assert approval_resolution_label([{}], ["x"]) == "mixed"
    assert approval_resolution_label([], ["x"]) == "rejected"
    assert approval_resolution_label([{}], []) == "approved"
    assert approval_resolution_label([], []) == "rejected"


@pytest.mark.asyncio
async def test_submit_decisions_puts_queue() -> None:
    FakeNanobotSessionModel._docs["s1"] = FakeSessionDoc(
        id="s1",
        agent_id="a1",
        status=NanobotSessionStatusEnum.AWAITING_APPROVAL,
    )
    decisions = [{"action": "approve"}]
    await HitlService.submit_decisions("a1", "s1", decisions)
    payload = await HitlService._await_decisions("s1")
    assert payload["decisions"] == decisions


@pytest.mark.asyncio
async def test_submit_decisions_not_found() -> None:
    with pytest.raises(AgentServiceError) as e:
        await HitlService.submit_decisions("a1", "missing", [])
    assert e.value.code == status_codes.NOT_FOUND_AGENT


@pytest.mark.asyncio
async def test_request_approval_full_handshake(monkeypatch: pytest.MonkeyPatch) -> None:
    FakeNanobotSessionModel._docs["s1"] = FakeSessionDoc(id="s1", agent_id="a1")
    calls: list[tuple[str, str, Any, bool]] = []

    async def _broadcast(
        agent_id: str, event: str, data: Any, *, persist: bool = True
    ) -> None:
        calls.append((agent_id, event, data, persist))

    async def _await(_session_id: str) -> dict:
        return {"decisions": [{"action": "approve"}]}

    monkeypatch.setattr(service_module.AnalystService, "broadcast_sse", _broadcast)
    monkeypatch.setattr(HitlService, "_await_decisions", _await)
    monkeypatch.setattr(HitlService, "patch_persisted_approval_required", AsyncMock())

    payload = {
        "entity_type": "article",
        "entity_uuid": "u1",
        "modifications": [],
        "reason": "r",
    }
    outcome = await HitlService.request_approval(
        "a1", "s1", HitlSource.TOOL_MODIFY_ENTITY, payload
    )

    assert outcome.resolution == "approved"
    assert outcome.approval_request_id
    doc = FakeNanobotSessionModel._docs["s1"]
    assert doc.status == NanobotSessionStatusEnum.RUNNING
    assert doc.pending_approval is None

    ar = [c for c in calls if c[1] == "approval_required"]
    assert len(ar) == 2
    assert ar[0][2]["source"] == HitlSource.TOOL_MODIFY_ENTITY
    assert ar[0][2]["resolution"] is None
    assert ar[0][2]["payload"] == payload
    assert ar[0][3] is True
    assert ar[1][2]["resolution"] == "approved"
    assert ar[1][3] is False

    pending = doc.pending_approval
    assert pending is None


@pytest.mark.asyncio
async def test_request_approval_pending_record_on_session(monkeypatch: pytest.MonkeyPatch) -> None:
    FakeNanobotSessionModel._docs["s1"] = FakeSessionDoc(id="s1", agent_id="a1")
    gate = asyncio.Event()

    async def _broadcast(
        _agent_id: str, event: str, data: Any, *, persist: bool = True
    ) -> None:
        if event == "approval_required" and (data or {}).get("resolution") is None:
            doc = FakeNanobotSessionModel._docs["s1"]
            assert doc.pending_approval is not None
            assert doc.pending_approval["source"] == HitlSource.TOOL_MODIFY_ENTITY
            assert doc.pending_approval["payload"]["entity_uuid"] == "u1"
            gate.set()

    async def _await(_session_id: str) -> dict:
        await gate.wait()
        return {"decisions": [{"action": "approve"}]}

    monkeypatch.setattr(service_module.AnalystService, "broadcast_sse", _broadcast)
    monkeypatch.setattr(HitlService, "_await_decisions", _await)
    monkeypatch.setattr(HitlService, "patch_persisted_approval_required", AsyncMock())

    await HitlService.request_approval(
        "a1",
        "s1",
        HitlSource.TOOL_MODIFY_ENTITY,
        {"entity_type": "article", "entity_uuid": "u1", "modifications": [], "reason": "r"},
    )
