"""MIGRATION_PLAN §12.12：AgentService（纯 mock / 内存仓库）。"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Iterable

import pytest

import app.service.analyst.agent as agent_module
import app.utils.status_codes as status_codes
from app.schemas.agent.nanobot_agent import (
    AgentServiceError,
    NanobotAgentCreateRequestSchema,
    NanobotAgentUpdateRequestSchema,
)
from app.schemas.constants import NanobotAgentStatusEnum


def _dt(n: int) -> datetime:
    return datetime(2026, 1, 1, 0, 0, 0) + timedelta(seconds=n)


@dataclass
class FakeWorkspaceDoc:
    id: str
    name: str = "ws"
    prompt_template_ids: list[str] = field(default_factory=list)
    model_config_ids: list[str] = field(default_factory=list)
    enabled_tools: list[str] = field(default_factory=list)
    enabled_skills: list[str] = field(default_factory=list)
    enabled_mcp_servers: dict[str, dict] = field(default_factory=dict)


@dataclass
class FakeAgentDoc:
    id: str
    workspace_id: str
    name: str
    description: str | None = None
    prompt_template_id: str = ""
    model_config_id: str = ""
    tools: list[str] = field(default_factory=list)
    skills: list[str] = field(default_factory=list)
    mcp_servers: list[str] = field(default_factory=list)
    llm_config: dict[str, Any] = field(default_factory=dict)

    # 运行时字段（update 不应污染）
    status: NanobotAgentStatusEnum = NanobotAgentStatusEnum.IDLE
    current_session_id: str | None = None
    steps: list[dict] = field(default_factory=list)
    todos: list[dict] = field(default_factory=list)
    pending_approval: dict | None = None
    result: dict | None = None
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)

    async def insert(self) -> None:
        FakeNanobotAgentModel._docs[self.id] = self

    async def save(self) -> None:
        FakeNanobotAgentModel._docs[self.id] = self

    async def delete(self) -> None:
        FakeNanobotAgentModel._docs.pop(self.id, None)


class _FakeQuery:
    def __init__(self, items: list[Any]) -> None:
        self._items = list(items)
        self._skip = 0
        self._limit: int | None = None
        self._sort_key: str | None = None
        self._sort_desc = False

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


class FakeNanobotWorkspaceModel:
    _docs: dict[str, FakeWorkspaceDoc] = {}

    @classmethod
    async def find_one(cls, query: dict[str, Any]) -> FakeWorkspaceDoc | None:
        return cls._docs.get(query.get("_id"))


class FakeNanobotAgentModel:
    _docs: dict[str, FakeAgentDoc] = {}

    def __init__(self, **kwargs: Any) -> None:
        self._doc = FakeAgentDoc(**kwargs)

    def __getattr__(self, item: str) -> Any:
        return getattr(self._doc, item)

    def __setattr__(self, key: str, value: Any) -> None:
        if key == "_doc":
            super().__setattr__(key, value)
        else:
            setattr(self._doc, key, value)

    async def insert(self) -> None:
        await self._doc.insert()

    async def save(self) -> None:
        await self._doc.save()

    async def delete(self) -> None:
        await self._doc.delete()

    @classmethod
    async def find_one(cls, query: dict[str, Any]) -> FakeAgentDoc | None:
        if "_id" in query:
            return cls._docs.get(query["_id"])
        if "workspace_id" in query and "name" in query:
            for d in cls._docs.values():
                if d.workspace_id == query["workspace_id"] and d.name == query["name"]:
                    return d
            return None
        raise AssertionError(f"不支持的 find_one 查询: {query}")

    @classmethod
    def find(cls, query_filters: dict[str, Any]) -> _FakeQuery:
        items = list(cls._docs.values())
        if not query_filters:
            return _FakeQuery(items)

        if "workspace_id" in query_filters:
            items = [d for d in items if d.workspace_id == query_filters["workspace_id"]]

        if "$or" in query_filters:
            clauses = query_filters["$or"]

            def _match_clause(doc: FakeAgentDoc, clause: dict[str, Any]) -> bool:
                (field_name, payload), = clause.items()
                pattern = payload.get("$regex")
                if not isinstance(pattern, re.Pattern):
                    raise AssertionError("测试桩期望 $regex 为 re.Pattern")
                value = getattr(doc, field_name) or ""
                return bool(pattern.search(value))

            items = [d for d in items if any(_match_clause(d, c) for c in clauses)]

        return _FakeQuery(items)


@pytest.fixture(autouse=True)
def _patch_models(monkeypatch: pytest.MonkeyPatch) -> Iterable[None]:
    FakeNanobotAgentModel._docs = {}
    FakeNanobotWorkspaceModel._docs = {}
    monkeypatch.setattr(agent_module, "NanobotAgentModel", FakeNanobotAgentModel)
    monkeypatch.setattr(agent_module, "NanobotWorkspaceModel", FakeNanobotWorkspaceModel)
    monkeypatch.setattr(agent_module, "generate_id", lambda _: "agent_fixed")
    yield


def _seed_workspace(ws_id: str, **kw: Any) -> None:
    FakeNanobotWorkspaceModel._docs[ws_id] = FakeWorkspaceDoc(id=ws_id, **kw)


@pytest.mark.asyncio
async def test_create_success() -> None:
    _seed_workspace(
        "w1",
        prompt_template_ids=["p1"],
        model_config_ids=["m1"],
        enabled_tools=["t1"],
        enabled_skills=["s1"],
        enabled_mcp_servers={"srv": {}},
    )
    data = NanobotAgentCreateRequestSchema(
        workspace_id="w1",
        name="A",
        description="d",
        prompt_template_id="p1",
        model_config_id="m1",
        tools=["t1"],
        skills=["s1"],
        mcp_servers=["srv"],
        llm_config={"temperature": 0.1},
    )
    doc = await agent_module.AgentService.create(data)
    assert doc.id == "agent_fixed"
    assert doc.status == NanobotAgentStatusEnum.IDLE
    assert await FakeNanobotAgentModel.find_one({"_id": "agent_fixed"}) is not None


@pytest.mark.asyncio
async def test_create_workspace_missing() -> None:
    data = NanobotAgentCreateRequestSchema(
        workspace_id="missing",
        name="A",
        prompt_template_id="p1",
        model_config_id="m1",
    )
    with pytest.raises(AgentServiceError) as e:
        await agent_module.AgentService.create(data)
    assert e.value.code == status_codes.NOT_FOUND_WORKSPACE


@pytest.mark.asyncio
async def test_create_prompt_not_in_whitelist() -> None:
    _seed_workspace("w1", prompt_template_ids=["p1"], model_config_ids=["m1"])
    data = NanobotAgentCreateRequestSchema(
        workspace_id="w1",
        name="A",
        prompt_template_id="pX",
        model_config_id="m1",
    )
    with pytest.raises(AgentServiceError) as e:
        await agent_module.AgentService.create(data)
    assert e.value.code == status_codes.INVALID_ARGUMENT
    assert "violations" in (e.value.data or {})


@pytest.mark.asyncio
async def test_create_model_not_in_whitelist() -> None:
    _seed_workspace("w1", prompt_template_ids=["p1"], model_config_ids=["m1"])
    data = NanobotAgentCreateRequestSchema(
        workspace_id="w1",
        name="A",
        prompt_template_id="p1",
        model_config_id="mX",
    )
    with pytest.raises(AgentServiceError) as e:
        await agent_module.AgentService.create(data)
    assert e.value.code == status_codes.INVALID_ARGUMENT


@pytest.mark.asyncio
async def test_create_tools_outside() -> None:
    _seed_workspace("w1", prompt_template_ids=["p1"], model_config_ids=["m1"], enabled_tools=["t1"])
    data = NanobotAgentCreateRequestSchema(
        workspace_id="w1",
        name="A",
        prompt_template_id="p1",
        model_config_id="m1",
        tools=["t2"],
    )
    with pytest.raises(AgentServiceError) as e:
        await agent_module.AgentService.create(data)
    assert e.value.code == status_codes.INVALID_ARGUMENT
    assert "tools" in "\n".join(e.value.data["violations"])


@pytest.mark.asyncio
async def test_create_skills_outside() -> None:
    _seed_workspace("w1", prompt_template_ids=["p1"], model_config_ids=["m1"], enabled_skills=["s1"])
    data = NanobotAgentCreateRequestSchema(
        workspace_id="w1",
        name="A",
        prompt_template_id="p1",
        model_config_id="m1",
        skills=["s2"],
    )
    with pytest.raises(AgentServiceError) as e:
        await agent_module.AgentService.create(data)
    assert e.value.code == status_codes.INVALID_ARGUMENT


@pytest.mark.asyncio
async def test_create_mcp_outside() -> None:
    _seed_workspace("w1", prompt_template_ids=["p1"], model_config_ids=["m1"], enabled_mcp_servers={"srv": {}})
    data = NanobotAgentCreateRequestSchema(
        workspace_id="w1",
        name="A",
        prompt_template_id="p1",
        model_config_id="m1",
        mcp_servers=["srv2"],
    )
    with pytest.raises(AgentServiceError) as e:
        await agent_module.AgentService.create(data)
    assert e.value.code == status_codes.INVALID_ARGUMENT


@pytest.mark.asyncio
async def test_create_duplicate_fields() -> None:
    _seed_workspace(
        "w1",
        prompt_template_ids=["p1"],
        model_config_ids=["m1"],
        enabled_tools=["t1"],
        enabled_skills=["s1"],
        enabled_mcp_servers={"srv": {}},
    )
    data = NanobotAgentCreateRequestSchema(
        workspace_id="w1",
        name="A",
        prompt_template_id="p1",
        model_config_id="m1",
        tools=["t1", "t1"],
        skills=["s1", "s1"],
        mcp_servers=["srv", "srv"],
    )
    with pytest.raises(AgentServiceError) as e:
        await agent_module.AgentService.create(data)
    assert e.value.code == status_codes.INVALID_ARGUMENT
    assert "重复" in "\n".join(e.value.data["violations"])


@pytest.mark.asyncio
async def test_create_name_unique_per_workspace() -> None:
    _seed_workspace("w1", prompt_template_ids=["p1"], model_config_ids=["m1"])
    _seed_workspace("w2", prompt_template_ids=["p1"], model_config_ids=["m1"])
    await FakeAgentDoc(id="a1", workspace_id="w1", name="A", prompt_template_id="p1", model_config_id="m1").insert()

    data1 = NanobotAgentCreateRequestSchema(
        workspace_id="w1", name="A", prompt_template_id="p1", model_config_id="m1"
    )
    with pytest.raises(AgentServiceError) as e:
        await agent_module.AgentService.create(data1)
    assert e.value.code == status_codes.CONFLICT_NAME

    data2 = NanobotAgentCreateRequestSchema(
        workspace_id="w2", name="A", prompt_template_id="p1", model_config_id="m1"
    )
    doc = await agent_module.AgentService.create(data2)
    assert doc.workspace_id == "w2"


@pytest.mark.asyncio
async def test_get_not_found() -> None:
    with pytest.raises(AgentServiceError) as e:
        await agent_module.AgentService.get("missing")
    assert e.value.code == status_codes.NOT_FOUND_AGENT


@pytest.mark.asyncio
async def test_list_page_filter_by_workspace() -> None:
    await FakeAgentDoc(id="a1", workspace_id="w1", name="n1", created_at=_dt(1)).insert()
    await FakeAgentDoc(id="a2", workspace_id="w2", name="n2", created_at=_dt(2)).insert()
    items, total = await agent_module.AgentService.list_page(page=1, page_size=10, workspace_id="w1")
    assert total == 1
    assert items[0].id == "a1"


@pytest.mark.asyncio
async def test_list_page_search() -> None:
    await FakeAgentDoc(id="a1", workspace_id="w1", name="foo", description="x").insert()
    await FakeAgentDoc(id="a2", workspace_id="w1", name="bar", description="foo in desc").insert()
    await FakeAgentDoc(id="a3", workspace_id="w1", name="baz", description="no").insert()
    items, total = await agent_module.AgentService.list_page(page=1, page_size=10, workspace_id="w1", search="foo")
    assert total == 2
    assert {i.id for i in items} == {"a1", "a2"}


@pytest.mark.asyncio
async def test_list_brief() -> None:
    await FakeAgentDoc(id="a1", workspace_id="w1", name="n1", status=NanobotAgentStatusEnum.IDLE, created_at=_dt(1)).insert()
    await FakeAgentDoc(id="a2", workspace_id="w1", name="n2", status=NanobotAgentStatusEnum.RUNNING, created_at=_dt(2)).insert()
    items = await agent_module.AgentService.list_brief(workspace_id="w1")
    assert [i.id for i in items] == ["a2", "a1"]


@pytest.mark.asyncio
async def test_update_success() -> None:
    _seed_workspace(
        "w1",
        prompt_template_ids=["p1"],
        model_config_ids=["m1"],
        enabled_tools=["t1", "t2"],
        enabled_skills=["s1"],
        enabled_mcp_servers={"srv": {}},
    )
    await FakeAgentDoc(
        id="a1",
        workspace_id="w1",
        name="old",
        prompt_template_id="p1",
        model_config_id="m1",
        tools=["t1"],
        status=NanobotAgentStatusEnum.COMPLETED,
        steps=[{"x": 1}],
        todos=[{"y": 2}],
        current_session_id="sess",
        updated_at=_dt(1),
    ).insert()
    data = NanobotAgentUpdateRequestSchema(
        name="new",
        description="d2",
        prompt_template_id="p1",
        model_config_id="m1",
        tools=["t2"],
        skills=["s1"],
        mcp_servers=["srv"],
        llm_config={"temperature": 0.2},
    )
    doc = await agent_module.AgentService.update("a1", data)
    assert doc.name == "new"
    assert doc.tools == ["t2"]
    assert doc.updated_at > _dt(1)
    # 运行时字段不被污染
    assert doc.steps == [{"x": 1}]
    assert doc.todos == [{"y": 2}]
    assert doc.current_session_id == "sess"


@pytest.mark.asyncio
async def test_update_blocked_running() -> None:
    _seed_workspace("w1", prompt_template_ids=["p1"], model_config_ids=["m1"])
    await FakeAgentDoc(
        id="a1",
        workspace_id="w1",
        name="A",
        prompt_template_id="p1",
        model_config_id="m1",
        status=NanobotAgentStatusEnum.RUNNING,
    ).insert()
    data = NanobotAgentUpdateRequestSchema(
        name="A",
        prompt_template_id="p1",
        model_config_id="m1",
    )
    with pytest.raises(AgentServiceError) as e:
        await agent_module.AgentService.update("a1", data)
    assert e.value.code == status_codes.CONFLICT_STATE


@pytest.mark.asyncio
async def test_update_blocked_awaiting_approval() -> None:
    _seed_workspace("w1", prompt_template_ids=["p1"], model_config_ids=["m1"])
    await FakeAgentDoc(
        id="a1",
        workspace_id="w1",
        name="A",
        prompt_template_id="p1",
        model_config_id="m1",
        status=NanobotAgentStatusEnum.AWAITING_APPROVAL,
    ).insert()
    data = NanobotAgentUpdateRequestSchema(name="A", prompt_template_id="p1", model_config_id="m1")
    with pytest.raises(AgentServiceError) as e:
        await agent_module.AgentService.update("a1", data)
    assert e.value.code == status_codes.CONFLICT_STATE


@pytest.mark.asyncio
async def test_update_allowed_after_completed() -> None:
    _seed_workspace("w1", prompt_template_ids=["p1"], model_config_ids=["m1"])
    for st in [NanobotAgentStatusEnum.COMPLETED, NanobotAgentStatusEnum.FAILED, NanobotAgentStatusEnum.PAUSED]:
        FakeNanobotAgentModel._docs = {}
        await FakeAgentDoc(
            id="a1",
            workspace_id="w1",
            name="A",
            prompt_template_id="p1",
            model_config_id="m1",
            status=st,
        ).insert()
        data = NanobotAgentUpdateRequestSchema(name="A2", prompt_template_id="p1", model_config_id="m1")
        doc = await agent_module.AgentService.update("a1", data)
        assert doc.name == "A2"


@pytest.mark.asyncio
async def test_update_rename_conflict() -> None:
    _seed_workspace("w1", prompt_template_ids=["p1"], model_config_ids=["m1"])
    await FakeAgentDoc(id="a1", workspace_id="w1", name="A", prompt_template_id="p1", model_config_id="m1").insert()
    await FakeAgentDoc(id="a2", workspace_id="w1", name="B", prompt_template_id="p1", model_config_id="m1").insert()
    data = NanobotAgentUpdateRequestSchema(name="B", prompt_template_id="p1", model_config_id="m1")
    with pytest.raises(AgentServiceError) as e:
        await agent_module.AgentService.update("a1", data)
    assert e.value.code == status_codes.CONFLICT_NAME


@pytest.mark.asyncio
async def test_update_rename_no_conflict_self() -> None:
    _seed_workspace("w1", prompt_template_ids=["p1"], model_config_ids=["m1"])
    await FakeAgentDoc(id="a1", workspace_id="w1", name="A", prompt_template_id="p1", model_config_id="m1").insert()
    data = NanobotAgentUpdateRequestSchema(name="A", prompt_template_id="p1", model_config_id="m1")
    doc = await agent_module.AgentService.update("a1", data)
    assert doc.name == "A"


@pytest.mark.asyncio
async def test_update_resubset_check() -> None:
    _seed_workspace("w1", prompt_template_ids=["p1"], model_config_ids=["m1"], enabled_tools=["t1"])
    await FakeAgentDoc(
        id="a1",
        workspace_id="w1",
        name="A",
        prompt_template_id="p1",
        model_config_id="m1",
        tools=["t1"],
    ).insert()
    # workspace 白名单变更（移除 t1）后，update 仍应基于最新 workspace 校验
    _seed_workspace("w1", prompt_template_ids=["p1"], model_config_ids=["m1"], enabled_tools=["t2"])
    data = NanobotAgentUpdateRequestSchema(
        name="A",
        prompt_template_id="p1",
        model_config_id="m1",
        tools=["t1"],
    )
    with pytest.raises(AgentServiceError) as e:
        await agent_module.AgentService.update("a1", data)
    assert e.value.code == status_codes.INVALID_ARGUMENT


@pytest.mark.asyncio
async def test_delete_success() -> None:
    _seed_workspace("w1", prompt_template_ids=["p1"], model_config_ids=["m1"])
    await FakeAgentDoc(id="a1", workspace_id="w1", name="A", prompt_template_id="p1", model_config_id="m1").insert()
    await agent_module.AgentService.delete("a1")
    assert await FakeNanobotAgentModel.find_one({"_id": "a1"}) is None


@pytest.mark.asyncio
async def test_delete_blocked_running() -> None:
    _seed_workspace("w1", prompt_template_ids=["p1"], model_config_ids=["m1"])
    for st in [NanobotAgentStatusEnum.RUNNING, NanobotAgentStatusEnum.AWAITING_APPROVAL]:
        FakeNanobotAgentModel._docs = {}
        await FakeAgentDoc(
            id="a1",
            workspace_id="w1",
            name="A",
            prompt_template_id="p1",
            model_config_id="m1",
            status=st,
        ).insert()
        with pytest.raises(AgentServiceError) as e:
            await agent_module.AgentService.delete("a1")
        assert e.value.code == status_codes.CONFLICT_STATE

