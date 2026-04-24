"""MIGRATION_PLAN §12.11：WorkspaceService（纯 mock / 内存仓库）。"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Iterable

import pytest

import app.utils.status_codes as status_codes
import app.service.analyst.workspace as workspace_module
from app.schemas.agent.workspace import (
    MCPServerConfigSchema,
    NanobotWorkspaceCreateRequestSchema,
    NanobotWorkspaceUpdateRequestSchema,
    WorkspaceServiceError,
)


def _dt(n: int) -> datetime:
    return datetime(2026, 1, 1, 0, 0, 0) + timedelta(seconds=n)


@dataclass
class FakeWorkspaceDoc:
    id: str
    name: str
    description: str | None = None
    prompt_template_ids: list[str] = field(default_factory=list)
    model_config_ids: list[str] = field(default_factory=list)
    enabled_tools: list[str] = field(default_factory=list)
    enabled_skills: list[str] = field(default_factory=list)
    enabled_mcp_servers: dict[str, dict] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)

    async def insert(self) -> None:
        FakeNanobotWorkspaceModel._docs[self.id] = self

    async def save(self) -> None:
        FakeNanobotWorkspaceModel._docs[self.id] = self

    async def delete(self) -> None:
        FakeNanobotWorkspaceModel._docs.pop(self.id, None)


@dataclass
class FakeAgentDoc:
    id: str
    workspace_id: str
    name: str
    prompt_template_id: str | None = None
    model_config_id: str | None = None
    tools: list[str] = field(default_factory=list)
    skills: list[str] = field(default_factory=list)
    mcp_servers: list[str] = field(default_factory=list)


@dataclass
class FakeIdDoc:
    id: str


class _FakeQuery:
    def __init__(self, items: list[Any]) -> None:
        self._items = list(items)
        self._skip = 0
        self._limit: int | None = None
        self._sort_key: str | None = None
        self._sort_desc: bool = False

    async def count(self) -> int:
        return len(self._items)

    def skip(self, n: int) -> "_FakeQuery":
        self._skip = n
        return self

    def limit(self, n: int) -> "_FakeQuery":
        self._limit = n
        return self

    def sort(self, key: str) -> "_FakeQuery":
        # beanie: "-created_at" 表示倒序
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

    def __init__(self, **kwargs: Any) -> None:
        self._doc = FakeWorkspaceDoc(**kwargs)

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
    async def find_one(cls, query: dict[str, Any]) -> FakeWorkspaceDoc | None:
        if "_id" in query:
            return cls._docs.get(query["_id"])
        if "name" in query:
            for d in cls._docs.values():
                if d.name == query["name"]:
                    return d
            return None
        raise AssertionError(f"不支持的查询: {query}")

    @classmethod
    def find(cls, query_filters: dict[str, Any]) -> _FakeQuery:
        items = list(cls._docs.values())
        if not query_filters:
            return _FakeQuery(items)
        if "$or" in query_filters:
            clauses = query_filters["$or"]

            def _match_clause(doc: FakeWorkspaceDoc, clause: dict[str, Any]) -> bool:
                # {"name": {"$regex": pattern}} / {"description": {"$regex": pattern}}
                (field_name, payload), = clause.items()
                pattern = payload.get("$regex")
                if not isinstance(pattern, re.Pattern):
                    raise AssertionError("测试桩期望 $regex 为 re.Pattern")
                value = getattr(doc, field_name) or ""
                return bool(pattern.search(value))

            filtered = [d for d in items if any(_match_clause(d, c) for c in clauses)]
            return _FakeQuery(filtered)
        raise AssertionError(f"不支持的查询过滤器: {query_filters}")

    @classmethod
    def find_all(cls) -> _FakeQuery:
        return _FakeQuery(list(cls._docs.values()))


class FakeNanobotAgentModel:
    _docs: list[FakeAgentDoc] = []

    @classmethod
    def find(cls, query: dict[str, Any]) -> _FakeQuery:
        if "workspace_id" in query:
            ws = query["workspace_id"]
            return _FakeQuery([a for a in cls._docs if a.workspace_id == ws])
        raise AssertionError(f"不支持的查询: {query}")


class FakePromptTemplateModel:
    _docs: dict[str, FakeIdDoc] = {}

    @classmethod
    def find(cls, query: dict[str, Any]) -> _FakeQuery:
        ids = query.get("_id", {}).get("$in", [])
        return _FakeQuery([d for i, d in cls._docs.items() if i in ids])


class FakeModelConfigModel:
    _docs: dict[str, FakeIdDoc] = {}

    @classmethod
    def find(cls, query: dict[str, Any]) -> _FakeQuery:
        ids = query.get("_id", {}).get("$in", [])
        return _FakeQuery([d for i, d in cls._docs.items() if i in ids])


@pytest.fixture(autouse=True)
def _patch_models(monkeypatch: pytest.MonkeyPatch) -> Iterable[None]:
    FakeNanobotWorkspaceModel._docs = {}
    FakeNanobotAgentModel._docs = []
    FakePromptTemplateModel._docs = {}
    FakeModelConfigModel._docs = {}

    monkeypatch.setattr(workspace_module, "NanobotWorkspaceModel", FakeNanobotWorkspaceModel)
    monkeypatch.setattr(workspace_module, "NanobotAgentModel", FakeNanobotAgentModel)
    monkeypatch.setattr(workspace_module, "AgentPromptTemplateModel", FakePromptTemplateModel)
    monkeypatch.setattr(workspace_module, "AgentModelConfigModel", FakeModelConfigModel)
    monkeypatch.setattr(workspace_module, "generate_id", lambda _: "ws_fixed")
    yield


def _seed_resources(*, prompts: list[str] | None = None, models: list[str] | None = None) -> None:
    for pid in prompts or []:
        FakePromptTemplateModel._docs[pid] = FakeIdDoc(id=pid)
    for mid in models or []:
        FakeModelConfigModel._docs[mid] = FakeIdDoc(id=mid)


def _mcp_ok() -> dict[str, MCPServerConfigSchema]:
    return {"srv": MCPServerConfigSchema(command="npx", args=["-v"])}


@pytest.mark.asyncio
async def test_create_success() -> None:
    _seed_resources(prompts=["p1"], models=["m1"])
    data = NanobotWorkspaceCreateRequestSchema(
        name="A",
        description="d",
        prompt_template_ids=["p1"],
        model_config_ids=["m1"],
        enabled_tools=["t1"],
        enabled_skills=["s1"],
        enabled_mcp_servers=_mcp_ok(),
    )
    doc = await workspace_module.WorkspaceService.create(data)
    assert doc.id == "ws_fixed"
    assert doc.name == "A"
    assert doc.enabled_mcp_servers["srv"]["command"] == "npx"
    assert await FakeNanobotWorkspaceModel.find_one({"_id": "ws_fixed"}) is not None


@pytest.mark.asyncio
async def test_create_name_conflict() -> None:
    _seed_resources()
    await FakeWorkspaceDoc(id="x", name="A").insert()
    data = NanobotWorkspaceCreateRequestSchema(name="A")
    with pytest.raises(WorkspaceServiceError) as e:
        await workspace_module.WorkspaceService.create(data)
    assert e.value.code == status_codes.CONFLICT_NAME


@pytest.mark.asyncio
async def test_create_missing_prompt_template() -> None:
    _seed_resources(models=["m1"])
    data = NanobotWorkspaceCreateRequestSchema(
        name="A", prompt_template_ids=["p_missing"], model_config_ids=["m1"]
    )
    with pytest.raises(WorkspaceServiceError) as e:
        await workspace_module.WorkspaceService.create(data)
    assert e.value.code == status_codes.NOT_FOUND_TEMPLATE


@pytest.mark.asyncio
async def test_create_missing_model_config() -> None:
    _seed_resources(prompts=["p1"])
    data = NanobotWorkspaceCreateRequestSchema(
        name="A", prompt_template_ids=["p1"], model_config_ids=["m_missing"]
    )
    with pytest.raises(WorkspaceServiceError) as e:
        await workspace_module.WorkspaceService.create(data)
    assert e.value.code == status_codes.NOT_FOUND_MODEL_CONFIG


@pytest.mark.asyncio
async def test_create_duplicate_prompt_ids() -> None:
    _seed_resources(prompts=["p1"], models=["m1"])
    data = NanobotWorkspaceCreateRequestSchema(
        name="A",
        prompt_template_ids=["p1", "p1"],
        model_config_ids=["m1", "m1"],
    )
    with pytest.raises(WorkspaceServiceError) as e:
        await workspace_module.WorkspaceService.create(data)
    assert e.value.code == status_codes.INVALID_ARGUMENT


@pytest.mark.asyncio
async def test_create_invalid_mcp_config(monkeypatch: pytest.MonkeyPatch) -> None:
    _seed_resources()
    # MCPServerConfigSchema 本身已做了较严格的参数校验（例如 tool_timeout>=1），
    # 因此这里通过让 MCPServerConfig.model_validate 主动抛异常来模拟“解析失败”的业务分支。
    monkeypatch.setattr(
        workspace_module.MCPServerConfig,
        "model_validate",
        lambda *_args, **_kw: (_ for _ in ()).throw(ValueError("bad mcp config")),
    )
    data = NanobotWorkspaceCreateRequestSchema(
        name="A",
        enabled_mcp_servers={"srv": MCPServerConfigSchema(command="npx", args=["-v"])},
    )
    with pytest.raises(WorkspaceServiceError) as e:
        await workspace_module.WorkspaceService.create(data)
    assert e.value.code == status_codes.INVALID_ARGUMENT
    assert "srv" in e.value.message


@pytest.mark.asyncio
async def test_create_empty_mcp_server_name() -> None:
    _seed_resources()
    data = NanobotWorkspaceCreateRequestSchema(
        name="A",
        enabled_mcp_servers={"": MCPServerConfigSchema(command="npx")},
    )
    with pytest.raises(WorkspaceServiceError) as e:
        await workspace_module.WorkspaceService.create(data)
    assert e.value.code == status_codes.INVALID_ARGUMENT


@pytest.mark.asyncio
async def test_get_not_found() -> None:
    with pytest.raises(WorkspaceServiceError) as e:
        await workspace_module.WorkspaceService.get("missing")
    assert e.value.code == status_codes.NOT_FOUND_WORKSPACE


@pytest.mark.asyncio
async def test_list_page_pagination() -> None:
    await FakeWorkspaceDoc(id="w1", name="n1", created_at=_dt(1)).insert()
    await FakeWorkspaceDoc(id="w2", name="n2", created_at=_dt(2)).insert()
    await FakeWorkspaceDoc(id="w3", name="n3", created_at=_dt(3)).insert()

    items, total = await workspace_module.WorkspaceService.list_page(page=1, page_size=2)
    assert total == 3
    assert [i.id for i in items] == ["w1", "w2"]


@pytest.mark.asyncio
async def test_list_page_search() -> None:
    await FakeWorkspaceDoc(id="w1", name="foo", description="x").insert()
    await FakeWorkspaceDoc(id="w2", name="bar", description="foo in desc").insert()
    await FakeWorkspaceDoc(id="w3", name="baz", description="no").insert()

    items, total = await workspace_module.WorkspaceService.list_page(page=1, page_size=10, search="foo")
    assert total == 2
    assert {i.id for i in items} == {"w1", "w2"}


@pytest.mark.asyncio
async def test_list_all_brief() -> None:
    await FakeWorkspaceDoc(id="w1", name="n1", created_at=_dt(1)).insert()
    await FakeWorkspaceDoc(id="w2", name="n2", created_at=_dt(3)).insert()
    await FakeWorkspaceDoc(id="w3", name="n3", created_at=_dt(2)).insert()

    items = await workspace_module.WorkspaceService.list_all_brief()
    assert [i.id for i in items] == ["w2", "w3", "w1"]


@pytest.mark.asyncio
async def test_update_success() -> None:
    _seed_resources(prompts=["p1"], models=["m1"])
    await FakeWorkspaceDoc(
        id="w1",
        name="old",
        prompt_template_ids=["p1"],
        model_config_ids=["m1"],
        enabled_tools=["t1"],
        enabled_skills=["s1"],
        enabled_mcp_servers={"srv": {"command": "npx", "args": [], "env": {}, "url": "", "headers": {}, "tool_timeout": 30, "enabled_tools": ["*"], "type": None}},
        updated_at=_dt(1),
    ).insert()

    data = NanobotWorkspaceUpdateRequestSchema(
        name="new",
        description="d2",
        prompt_template_ids=["p1"],
        model_config_ids=["m1"],
        enabled_tools=["t1", "t2"],
        enabled_skills=["s1"],
        enabled_mcp_servers=_mcp_ok(),
    )
    doc = await workspace_module.WorkspaceService.update("w1", data)
    assert doc.name == "new"
    assert doc.description == "d2"
    assert doc.updated_at > _dt(1)


@pytest.mark.asyncio
async def test_update_name_conflict() -> None:
    _seed_resources()
    await FakeWorkspaceDoc(id="w1", name="A").insert()
    await FakeWorkspaceDoc(id="w2", name="B").insert()
    data = NanobotWorkspaceUpdateRequestSchema(name="B")
    with pytest.raises(WorkspaceServiceError) as e:
        await workspace_module.WorkspaceService.update("w1", data)
    assert e.value.code == status_codes.CONFLICT_NAME


@pytest.mark.asyncio
async def test_update_narrow_tools_with_reference() -> None:
    _seed_resources(prompts=["p1"], models=["m1"])
    await FakeWorkspaceDoc(
        id="w1",
        name="A",
        prompt_template_ids=["p1"],
        model_config_ids=["m1"],
        enabled_tools=["t1", "t2"],
    ).insert()
    FakeNanobotAgentModel._docs.append(
        FakeAgentDoc(
            id="a1",
            workspace_id="w1",
            name="agent",
            prompt_template_id="p1",
            model_config_id="m1",
            tools=["t1"],
        )
    )
    data = NanobotWorkspaceUpdateRequestSchema(
        name="A",
        prompt_template_ids=["p1"],
        model_config_ids=["m1"],
        enabled_tools=["t2"],  # 移除 t1
    )
    with pytest.raises(WorkspaceServiceError) as e:
        await workspace_module.WorkspaceService.update("w1", data)
    assert e.value.code == status_codes.CONFLICT_STATE
    assert e.value.data and "conflicts" in e.value.data


@pytest.mark.asyncio
async def test_update_narrow_prompt_template() -> None:
    _seed_resources(prompts=["p1", "p2"], models=["m1"])
    await FakeWorkspaceDoc(
        id="w1",
        name="A",
        prompt_template_ids=["p1", "p2"],
        model_config_ids=["m1"],
        enabled_tools=[],
    ).insert()
    FakeNanobotAgentModel._docs.append(
        FakeAgentDoc(
            id="a1",
            workspace_id="w1",
            name="agent",
            prompt_template_id="p2",
            model_config_id="m1",
        )
    )
    data = NanobotWorkspaceUpdateRequestSchema(
        name="A",
        prompt_template_ids=["p1"],  # 移除 p2
        model_config_ids=["m1"],
    )
    with pytest.raises(WorkspaceServiceError) as e:
        await workspace_module.WorkspaceService.update("w1", data)
    assert e.value.code == status_codes.CONFLICT_STATE


@pytest.mark.asyncio
async def test_update_widen_allowed() -> None:
    _seed_resources(prompts=["p1"], models=["m1"])
    await FakeWorkspaceDoc(
        id="w1",
        name="A",
        prompt_template_ids=["p1"],
        model_config_ids=["m1"],
        enabled_tools=["t1"],
        enabled_skills=["s1"],
        enabled_mcp_servers={"srv": {"command": "npx", "args": [], "env": {}, "url": "", "headers": {}, "tool_timeout": 30, "enabled_tools": ["*"], "type": None}},
    ).insert()
    FakeNanobotAgentModel._docs.append(
        FakeAgentDoc(
            id="a1",
            workspace_id="w1",
            name="agent",
            prompt_template_id="p1",
            model_config_id="m1",
            tools=["t1"],
            skills=["s1"],
            mcp_servers=["srv"],
        )
    )
    data = NanobotWorkspaceUpdateRequestSchema(
        name="A",
        prompt_template_ids=["p1"],
        model_config_ids=["m1"],
        enabled_tools=["t1", "t2"],  # 放宽
        enabled_skills=["s1", "s2"],  # 放宽
        enabled_mcp_servers={**_mcp_ok(), "srv2": MCPServerConfigSchema(command="node")},
    )
    doc = await workspace_module.WorkspaceService.update("w1", data)
    assert "t2" in doc.enabled_tools
    assert "s2" in doc.enabled_skills
    assert "srv2" in doc.enabled_mcp_servers


@pytest.mark.asyncio
async def test_update_resource_missing() -> None:
    _seed_resources(prompts=["p1"], models=["m1"])
    await FakeWorkspaceDoc(id="w1", name="A", prompt_template_ids=["p1"], model_config_ids=["m1"]).insert()
    # 若资源不存在，应先失败在资源校验阶段，不触发 narrowing cascade（即不需要 agents）
    data = NanobotWorkspaceUpdateRequestSchema(
        name="A",
        prompt_template_ids=["p_missing"],
        model_config_ids=["m1"],
    )
    with pytest.raises(WorkspaceServiceError) as e:
        await workspace_module.WorkspaceService.update("w1", data)
    assert e.value.code == status_codes.NOT_FOUND_TEMPLATE


@pytest.mark.asyncio
async def test_delete_success() -> None:
    _seed_resources()
    await FakeWorkspaceDoc(id="w1", name="A").insert()
    await workspace_module.WorkspaceService.delete("w1")
    assert await FakeNanobotWorkspaceModel.find_one({"_id": "w1"}) is None


@pytest.mark.asyncio
async def test_delete_blocked_by_agents() -> None:
    _seed_resources()
    await FakeWorkspaceDoc(id="w1", name="A").insert()
    FakeNanobotAgentModel._docs.append(FakeAgentDoc(id="a1", workspace_id="w1", name="agent"))
    with pytest.raises(WorkspaceServiceError) as e:
        await workspace_module.WorkspaceService.delete("w1")
    assert e.value.code == status_codes.CONFLICT_STATE

