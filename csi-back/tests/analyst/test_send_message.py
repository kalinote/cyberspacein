"""AnalystService.send_message 的会话状态前置校验。"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable

import pytest

import app.service.analyst.service as service_module
import app.utils.status_codes as status_codes
from app.schemas.agent.nanobot_agent import AgentServiceError
from app.schemas.constants import NanobotSessionStatusEnum


@dataclass
class FakeSessionDoc:
    id: str
    agent_id: str = "a1"
    status: NanobotSessionStatusEnum = NanobotSessionStatusEnum.COMPLETED


class FakeNanobotSessionModel:
    _docs: dict[str, FakeSessionDoc] = {}

    @classmethod
    async def find_one(cls, query: dict[str, Any]) -> FakeSessionDoc | None:
        return cls._docs.get(query.get("_id"))


@pytest.fixture(autouse=True)
def _reset(monkeypatch: pytest.MonkeyPatch) -> Iterable[None]:
    FakeNanobotSessionModel._docs = {}
    monkeypatch.setattr(
        service_module, "NanobotSessionModel", FakeNanobotSessionModel
    )
    yield


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
    with pytest.raises(AgentServiceError) as exc_info:
        await service_module.AnalystService.send_message("a1", "s1", "hi")
    assert exc_info.value.code == status_codes.CONFLICT_STATE
    assert msg_substr in exc_info.value.message


@pytest.mark.asyncio
async def test_send_message_not_found_session() -> None:
    with pytest.raises(AgentServiceError) as exc_info:
        await service_module.AnalystService.send_message("a1", "missing", "hi")
    assert exc_info.value.code == status_codes.NOT_FOUND_AGENT


@pytest.mark.asyncio
async def test_send_message_wrong_agent() -> None:
    FakeNanobotSessionModel._docs["s1"] = FakeSessionDoc(
        id="s1", agent_id="other"
    )
    with pytest.raises(AgentServiceError) as exc_info:
        await service_module.AnalystService.send_message("a1", "s1", "hi")
    assert exc_info.value.code == status_codes.NOT_FOUND_AGENT
