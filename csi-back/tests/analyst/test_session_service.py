"""SessionService 分页列表（纯 mock / 内存仓库）。"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Iterable

import pytest

import app.service.analyst.session as session_module
from app.schemas.constants import NanobotSessionStatusEnum


def _dt(n: int) -> datetime:
    return datetime(2026, 1, 1, 0, 0, 0) + timedelta(seconds=n)


@dataclass
class FakeAgentDoc:
    id: str
    name: str
    workspace_id: str = "w1"


@dataclass
class FakeSessionDoc:
    id: str
    agent_id: str
    workspace_id: str = "w1"
    metadata: dict[str, Any] = field(default_factory=dict)
    last_consolidated_seq: int = 0
    status: NanobotSessionStatusEnum = NanobotSessionStatusEnum.IDLE
    steps: list[dict] = field(default_factory=list)
    todos: list[dict] = field(default_factory=list)
    pending_approval: dict | None = None
    result: dict | None = None
    user_prompt: str | None = None
    error_message: str | None = None
    started_at: datetime | None = None
    finished_at: datetime | None = None
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)


class _FakeQuery:
    def __init__(self, items: list[Any]) -> None:
        self._items = list(items)
        self._skip = 0
        self._limit: int | None = None
        self._sort_key: str | None = None
        self._sort_desc = False

    def project(self, _projection: dict[str, int]) -> "_FakeQuery":
        return self

    async def count(self) -> int:
        return len(self._items)

    def skip(self, n: int) -> "_FakeQuery":
        self._skip = n
        return self

    def limit(self, n: int) -> "_FakeQuery":
        self._limit = n
        return self

    def sort(self, key: str) -> "_FakeQuery":
        if key.startswith("-"):
            self._sort_key = key[1:]
            self._sort_desc = True
        else:
            self._sort_key = key
            self._sort_desc = False
        return self

    async def to_list(self) -> list[Any]:
        items = list(self._items)
        if self._sort_key:
            items.sort(key=lambda x: getattr(x, self._sort_key), reverse=self._sort_desc)
        if self._skip:
            items = items[self._skip :]
        if self._limit is not None:
            items = items[: self._limit]
        return items


class FakeNanobotSessionModel:
    _docs: dict[str, FakeSessionDoc] = {}

    @classmethod
    async def find_one(cls, query: dict[str, Any]) -> FakeSessionDoc | None:
        return cls._docs.get(query.get("_id"))

    @classmethod
    def find(cls, query_filters: dict[str, Any]) -> _FakeQuery:
        items = list(cls._docs.values())
        if "agent_id" in query_filters:
            items = [d for d in items if d.agent_id == query_filters["agent_id"]]
        if "workspace_id" in query_filters:
            items = [d for d in items if d.workspace_id == query_filters["workspace_id"]]
        if "status" in query_filters:
            items = [
                d for d in items if d.status.value == query_filters["status"]
            ]
        return _FakeQuery(items)


class FakeNanobotAgentModel:
    _docs: dict[str, FakeAgentDoc] = {}

    @classmethod
    async def find_one(cls, query: dict[str, Any]) -> FakeAgentDoc | None:
        return cls._docs.get(query.get("_id"))

    @classmethod
    def find(cls, query_filters: dict[str, Any]) -> _FakeQuery:
        ids = query_filters.get("_id", {}).get("$in", [])
        items = [cls._docs[i] for i in ids if i in cls._docs]
        return _FakeQuery(items)


@pytest.fixture(autouse=True)
def _patch_models(monkeypatch: pytest.MonkeyPatch) -> Iterable[None]:
    FakeNanobotSessionModel._docs = {}
    FakeNanobotAgentModel._docs = {}
    monkeypatch.setattr(session_module, "NanobotSessionModel", FakeNanobotSessionModel)
    monkeypatch.setattr(session_module, "NanobotAgentModel", FakeNanobotAgentModel)
    yield


@pytest.mark.asyncio
async def test_list_page_filter_by_workspace() -> None:
    FakeNanobotSessionModel._docs["s1"] = FakeSessionDoc(
        id="s1", agent_id="a1", workspace_id="w1", created_at=_dt(1)
    )
    FakeNanobotSessionModel._docs["s2"] = FakeSessionDoc(
        id="s2", agent_id="a1", workspace_id="w2", created_at=_dt(2)
    )
    FakeNanobotAgentModel._docs["a1"] = FakeAgentDoc(id="a1", name="Agent1")
    items, total = await session_module.SessionService.list_page(
        page=1, page_size=10, workspace_id="w1"
    )
    assert total == 1
    assert items[0].id == "s1"
    assert items[0].agent_name == "Agent1"


@pytest.mark.asyncio
async def test_list_page_filter_by_agent_and_status() -> None:
    FakeNanobotSessionModel._docs["s1"] = FakeSessionDoc(
        id="s1",
        agent_id="a1",
        status=NanobotSessionStatusEnum.RUNNING,
        created_at=_dt(1),
    )
    FakeNanobotSessionModel._docs["s2"] = FakeSessionDoc(
        id="s2",
        agent_id="a1",
        status=NanobotSessionStatusEnum.COMPLETED,
        created_at=_dt(2),
    )
    FakeNanobotSessionModel._docs["s3"] = FakeSessionDoc(
        id="s3",
        agent_id="a2",
        status=NanobotSessionStatusEnum.RUNNING,
        created_at=_dt(3),
    )
    items, total = await session_module.SessionService.list_page(
        page=1,
        page_size=10,
        agent_id="a1",
        status=NanobotSessionStatusEnum.RUNNING,
    )
    assert total == 1
    assert items[0].id == "s1"


@pytest.mark.asyncio
async def test_list_page_pagination_and_sort() -> None:
    for i in range(3):
        FakeNanobotSessionModel._docs[f"s{i}"] = FakeSessionDoc(
            id=f"s{i}",
            agent_id="a1",
            created_at=_dt(i),
        )
    items, total = await session_module.SessionService.list_page(
        page=2, page_size=1
    )
    assert total == 3
    assert len(items) == 1
    assert items[0].id == "s1"


@pytest.mark.asyncio
async def test_list_page_agent_name_missing_when_agent_deleted() -> None:
    FakeNanobotSessionModel._docs["s1"] = FakeSessionDoc(
        id="s1", agent_id="gone", created_at=_dt(1)
    )
    items, total = await session_module.SessionService.list_page(page=1, page_size=10)
    assert total == 1
    assert items[0].agent_name is None


@pytest.mark.asyncio
async def test_list_page_schema_excludes_heavy_fields() -> None:
    FakeNanobotSessionModel._docs["s1"] = FakeSessionDoc(
        id="s1",
        agent_id="a1",
        steps=[{"n": 1}],
        todos=[{"id": "t1"}],
        user_prompt="secret",
        created_at=_dt(1),
    )
    FakeNanobotAgentModel._docs["a1"] = FakeAgentDoc(id="a1", name="A")
    items, _ = await session_module.SessionService.list_page(page=1, page_size=10)
    dumped = items[0].model_dump()
    assert "steps" not in dumped
    assert "todos" not in dumped
    assert "user_prompt" not in dumped
    assert dumped["agent_name"] == "A"


@pytest.mark.asyncio
async def test_get_detail_returns_same_fields_as_list() -> None:
    FakeNanobotSessionModel._docs["s1"] = FakeSessionDoc(
        id="s1",
        agent_id="a1",
        workspace_id="w1",
        status=NanobotSessionStatusEnum.COMPLETED,
        result={"success": True},
        error_message=None,
        started_at=_dt(10),
        finished_at=_dt(20),
        created_at=_dt(1),
        updated_at=_dt(21),
    )
    FakeNanobotAgentModel._docs["a1"] = FakeAgentDoc(id="a1", name="Agent1")
    detail = await session_module.SessionService.get_detail("s1")
    assert detail is not None
    items, _ = await session_module.SessionService.list_page(page=1, page_size=10)
    assert detail.model_dump() == items[0].model_dump()


@pytest.mark.asyncio
async def test_get_detail_not_found() -> None:
    assert await session_module.SessionService.get_detail("missing") is None
    assert await session_module.SessionService.get_detail("  ") is None
