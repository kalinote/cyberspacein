from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Iterable

import pytest

import app.service.analyst.system_prompt as system_prompt_module
import app.utils.status_codes as status_codes
from app.schemas.agent.configs import (
    SystemPromptCreateRequestSchema,
    SystemPromptUpdateRequestSchema,
)
from app.schemas.constants import NanobotMemoryDocTypeEnum


def _dt(n: int) -> datetime:
    return datetime(2026, 1, 1, 0, 0, 0) + timedelta(seconds=n)


@dataclass
class FakeSystemPromptDoc:
    id: str
    workspace_id: str
    type: NanobotMemoryDocTypeEnum
    name: str
    content: str
    description: str | None = None
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)

    async def insert(self) -> None:
        FakeNanobotMemoryDocsModel._docs[self.id] = self

    async def save(self) -> None:
        FakeNanobotMemoryDocsModel._docs[self.id] = self

    async def delete(self) -> None:
        FakeNanobotMemoryDocsModel._docs.pop(self.id, None)


class _FakeQuery:
    def __init__(self, items: list[Any]) -> None:
        self._items = list(items)
        self._skip = 0
        self._limit: int | None = None

    async def count(self) -> int:
        return len(self._items)

    def skip(self, n: int) -> "_FakeQuery":
        self._skip = n
        return self

    def limit(self, n: int) -> "_FakeQuery":
        self._limit = n
        return self

    async def to_list(self) -> list[Any]:
        items = self._items[self._skip :]
        if self._limit is not None:
            items = items[: self._limit]
        return items


class FakeNanobotMemoryDocsModel:
    _docs: dict[str, FakeSystemPromptDoc] = {}

    def __init__(self, **kwargs: Any) -> None:
        doc_id = f"sp{len(self._docs) + 1}"
        self._doc = FakeSystemPromptDoc(
            id=doc_id,
            workspace_id=kwargs["workspace_id"],
            type=kwargs["type"],
            name=kwargs["name"],
            content=kwargs["content"],
            description=kwargs.get("description"),
            created_at=kwargs.get("created_at", datetime.now()),
            updated_at=kwargs.get("updated_at", datetime.now()),
        )

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
    async def find_one(cls, query: dict[str, Any]) -> FakeSystemPromptDoc | None:
        if "_id" in query:
            return cls._docs.get(str(query["_id"]))
        raise AssertionError(f"不支持的查询: {query}")

    @classmethod
    def find(cls, query_filters: dict[str, Any]) -> _FakeQuery:
        items = list(cls._docs.values())
        if "workspace_id" in query_filters:
            items = [doc for doc in items if doc.workspace_id == query_filters["workspace_id"]]
        if "type" in query_filters:
            items = [doc for doc in items if doc.type == query_filters["type"]]
        if "$or" in query_filters:
            branches = query_filters["$or"]
            patterns: list[re.Pattern[str]] = []
            for branch in branches:
                for _field, spec in branch.items():
                    if isinstance(spec, dict) and "$regex" in spec:
                        p = spec["$regex"]
                        if isinstance(p, re.Pattern):
                            patterns.append(p)
            if not patterns:
                raise AssertionError("测试桩期望 $or 分支含 re.Pattern")
            pat = patterns[0]

            def _matches(doc: FakeSystemPromptDoc) -> bool:
                if pat.search(doc.content):
                    return True
                if pat.search(doc.name):
                    return True
                if doc.description and pat.search(doc.description):
                    return True
                return False

            items = [doc for doc in items if _matches(doc)]
        elif "content" in query_filters:
            pattern = query_filters["content"].get("$regex")
            if not isinstance(pattern, re.Pattern):
                raise AssertionError("测试桩期望 $regex 为 re.Pattern")
            items = [doc for doc in items if pattern.search(doc.content)]
        return _FakeQuery(items)


@pytest.fixture(autouse=True)
def _patch_model(monkeypatch: pytest.MonkeyPatch) -> Iterable[None]:
    FakeNanobotMemoryDocsModel._docs = {}
    monkeypatch.setattr(
        system_prompt_module,
        "NanobotMemoryDocsModel",
        FakeNanobotMemoryDocsModel,
    )
    yield


async def _seed(
    *,
    id: str,
    workspace_id: str,
    type: NanobotMemoryDocTypeEnum,
    name: str,
    content: str,
    description: str | None = None,
    updated_at: datetime | None = None,
) -> FakeSystemPromptDoc:
    doc = FakeSystemPromptDoc(
        id=id,
        workspace_id=workspace_id,
        type=type,
        name=name,
        content=content,
        description=description,
        created_at=_dt(0),
        updated_at=updated_at or _dt(0),
    )
    await doc.insert()
    return doc


@pytest.mark.asyncio
async def test_create_agent_type_forces_builtin_workspace() -> None:
    data = SystemPromptCreateRequestSchema(
        workspace_id="w1",
        type=NanobotMemoryDocTypeEnum.AGENT,
        name="identity",
        content="hello",
    )
    doc = await system_prompt_module.SystemPromptService.create(data)
    assert doc.workspace_id == system_prompt_module.NANOBOT_BUILTIN_WORKSPACE_ID


@pytest.mark.asyncio
async def test_create_success() -> None:
    data = SystemPromptCreateRequestSchema(
        workspace_id="w1",
        type=NanobotMemoryDocTypeEnum.MEMORY,
        name="默认记忆",
        content="规则",
    )
    doc = await system_prompt_module.SystemPromptService.create(data)
    assert doc.id == "sp1"
    assert doc.workspace_id == "w1"
    assert await FakeNanobotMemoryDocsModel.find_one({"_id": "sp1"}) is not None


@pytest.mark.asyncio
async def test_create_multiple_same_workspace_type_allowed() -> None:
    await _seed(
        id="sp0",
        workspace_id="w1",
        type=NanobotMemoryDocTypeEnum.MEMORY,
        name="已有",
        content="旧规则",
    )
    data = SystemPromptCreateRequestSchema(
        workspace_id="w1",
        type=NanobotMemoryDocTypeEnum.MEMORY,
        name="另一条",
        content="新规则",
    )
    doc = await system_prompt_module.SystemPromptService.create(data)
    assert doc.id == "sp2"
    assert len(FakeNanobotMemoryDocsModel._docs) == 2


@pytest.mark.asyncio
async def test_list_page_filters() -> None:
    await _seed(
        id="sp1",
        workspace_id="w1",
        type=NanobotMemoryDocTypeEnum.MEMORY,
        name="m1",
        content="alpha",
    )
    await _seed(
        id="sp2",
        workspace_id="w1",
        type=NanobotMemoryDocTypeEnum.SOUL,
        name="s1",
        content="alpha",
    )
    await _seed(
        id="sp3",
        workspace_id="w2",
        type=NanobotMemoryDocTypeEnum.MEMORY,
        name="m2",
        content="alpha",
    )
    items, total = await system_prompt_module.SystemPromptService.list_page(
        page=1,
        page_size=10,
        workspace_id="w1",
        type=NanobotMemoryDocTypeEnum.MEMORY,
        search="ALP",
    )
    assert total == 1
    assert items[0].id == "sp1"


@pytest.mark.asyncio
async def test_update_success() -> None:
    await _seed(
        id="sp1",
        workspace_id="w1",
        type=NanobotMemoryDocTypeEnum.MEMORY,
        name="旧名",
        content="旧规则",
        updated_at=_dt(1),
    )
    data = SystemPromptUpdateRequestSchema(
        workspace_id="w1",
        type=NanobotMemoryDocTypeEnum.SOUL,
        name="新名",
        content="新规则",
    )
    doc = await system_prompt_module.SystemPromptService.update("sp1", data)
    assert doc.type is NanobotMemoryDocTypeEnum.SOUL
    assert doc.name == "新名"
    assert doc.content == "新规则"
    assert doc.updated_at > _dt(1)


@pytest.mark.asyncio
async def test_update_no_conflict_when_another_doc_shares_type() -> None:
    await _seed(
        id="sp1",
        workspace_id="w1",
        type=NanobotMemoryDocTypeEnum.MEMORY,
        name="a",
        content="a",
    )
    await _seed(
        id="sp2",
        workspace_id="w1",
        type=NanobotMemoryDocTypeEnum.SOUL,
        name="b",
        content="b",
    )
    data = SystemPromptUpdateRequestSchema(
        workspace_id="w1",
        type=NanobotMemoryDocTypeEnum.SOUL,
        name="a",
        content="c",
    )
    doc = await system_prompt_module.SystemPromptService.update("sp1", data)
    assert doc.type is NanobotMemoryDocTypeEnum.SOUL
    assert doc.content == "c"
    assert FakeNanobotMemoryDocsModel._docs["sp2"].content == "b"


@pytest.mark.asyncio
async def test_delete_not_found() -> None:
    with pytest.raises(system_prompt_module.SystemPromptServiceError) as e:
        await system_prompt_module.SystemPromptService.delete("missing")
    assert e.value.code == status_codes.NOT_FOUND
