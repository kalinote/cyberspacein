"""SkillAdminService 单元测试。"""
from __future__ import annotations

from collections.abc import Iterable
from datetime import datetime
from typing import Any
from unittest.mock import AsyncMock

import pytest

import app.utils.status_codes as status_codes
from app.schemas.agent.skill import SkillServiceError
from app.service.analyst import skill_admin as admin_module
from app.service.analyst.skill_frontmatter import build_skill_md, parse_frontmatter, split_promoted_fields


class _FakeQuery:
    def __init__(self, items: list[Any]) -> None:
        self._items = items

    async def delete(self) -> None:
        pass


class FakeSkillDoc:
    _skills: dict[str, Any] = {}
    _files: list[Any] = []

    def __init__(
        self,
        *,
        id: str,
        name: str,
        description: str = "",
        always: bool = False,
        meta: dict | None = None,
    ) -> None:
        self.id = id
        self.name = name
        self.description = description
        self.always = always
        self.meta = meta or {}
        self.created_at = datetime.now()
        self.updated_at = self.created_at

    async def insert(self) -> None:
        FakeSkillDoc._skills[self.id] = self

    async def save(self) -> None:
        FakeSkillDoc._skills[self.id] = self

    async def delete(self) -> None:
        FakeSkillDoc._skills.pop(self.id, None)


class FakeSkillFileDoc:
    def __init__(
        self,
        *,
        skill_id: str,
        path: str,
        file_type: str,
        content: str,
    ) -> None:
        self.skill_id = skill_id
        self.path = path
        self.file_type = file_type
        self.content = content
        self.created_at = datetime.now()
        self.updated_at = self.created_at

    async def insert(self) -> None:
        FakeSkillFileDoc._files.append(self)

    async def save(self) -> None:
        pass

    async def delete(self) -> None:
        FakeSkillFileDoc._files = [
            f for f in FakeSkillFileDoc._files
            if not (f.skill_id == self.skill_id and f.path == self.path)
        ]


class FakeNanobotSkillModel:
    @classmethod
    async def find_one(cls, query: dict[str, Any]) -> Any:
        if "_id" in query:
            return FakeSkillDoc._skills.get(query["_id"])
        if "name" in query:
            for s in FakeSkillDoc._skills.values():
                if s.name == query["name"]:
                    return s
        return None

    def __init__(self, **kwargs: Any) -> None:
        for key, value in kwargs.items():
            setattr(self, key, value)
        if not hasattr(self, "created_at"):
            self.created_at = datetime.now()
        if not hasattr(self, "updated_at"):
            self.updated_at = self.created_at

    async def insert(self) -> None:
        FakeSkillDoc._skills[self.id] = self

    async def save(self) -> None:
        FakeSkillDoc._skills[self.id] = self

    async def delete(self) -> None:
        FakeSkillDoc._skills.pop(self.id, None)


class FakeNanobotSkillFileModel:
    @classmethod
    async def find_one(cls, query: dict[str, Any]) -> Any:
        sid = query.get("skill_id")
        path = query.get("path")
        for f in FakeSkillFileDoc._files:
            if f.skill_id == sid and f.path == path:
                return f
        return None

    @classmethod
    def find(cls, *args: Any, **kwargs: Any) -> _FakeQuery:
        return _FakeQuery([])

    def __init__(self, **kwargs: Any) -> None:
        for key, value in kwargs.items():
            setattr(self, key, value)
        if not hasattr(self, "created_at"):
            self.created_at = datetime.now()
        if not hasattr(self, "updated_at"):
            self.updated_at = self.created_at

    async def insert(self) -> None:
        FakeSkillFileDoc._files.append(self)

    async def save(self) -> None:
        pass

    async def delete(self) -> None:
        FakeSkillFileDoc._files = [
            f for f in FakeSkillFileDoc._files
            if not (f.skill_id == self.skill_id and f.path == self.path)
        ]


class FakeNanobotAgentModel:
    @classmethod
    async def find_one(cls, query: dict[str, Any]) -> Any:
        sid = query.get("skills")
        if sid == "bound_skill":
            agent = type("A", (), {"id": "a1", "name": "Agent1"})()
            return agent
        return None


class FakeNanobotWorkspaceModel:
    @classmethod
    async def find_one(cls, query: dict[str, Any]) -> Any:
        sid = query.get("enabled_skills")
        if sid == "bound_skill":
            ws = type("W", (), {"id": "w1", "name": "WS1"})()
            return ws
        return None


@pytest.fixture(autouse=True)
def _patch(monkeypatch: pytest.MonkeyPatch) -> Iterable[None]:
    FakeSkillDoc._skills = {}
    FakeSkillFileDoc._files = []
    monkeypatch.setattr(admin_module, "NanobotSkillModel", FakeNanobotSkillModel)
    monkeypatch.setattr(admin_module, "NanobotSkillFileModel", FakeNanobotSkillFileModel)
    monkeypatch.setattr(admin_module, "NanobotAgentModel", FakeNanobotAgentModel)
    monkeypatch.setattr(admin_module, "NanobotWorkspaceModel", FakeNanobotWorkspaceModel)
    monkeypatch.setattr(admin_module, "generate_id", lambda _: "skill_fixed")
    yield


@pytest.mark.asyncio
async def test_create_skill() -> None:
    doc = await admin_module.SkillAdminService.create(
        name="demo-skill",
        description="desc",
        always=True,
        skill_md_body="# Hello",
    )
    assert doc.id == "skill_fixed"
    assert doc.name == "demo-skill"
    assert len(FakeSkillFileDoc._files) == 1
    assert FakeSkillFileDoc._files[0].path == "SKILL.md"
    fm = parse_frontmatter(FakeSkillFileDoc._files[0].content)
    assert fm is not None
    name, desc, always, _ = split_promoted_fields(fm)
    assert name == "demo-skill"
    assert desc == "desc"
    assert always is True


@pytest.mark.asyncio
async def test_create_duplicate_name() -> None:
    await FakeSkillDoc(id="x", name="demo-skill").insert()
    with pytest.raises(SkillServiceError) as exc:
        await admin_module.SkillAdminService.create(name="demo-skill")
    assert exc.value.code == status_codes.CONFLICT_NAME


@pytest.mark.asyncio
async def test_update_meta_syncs_skill_md() -> None:
    body = "# Title"
    md = build_skill_md("old-name", "old", False, {}, body)
    await FakeSkillDoc(id="skill_fixed", name="old-name", description="old").insert()
    await FakeSkillFileDoc(
        skill_id="skill_fixed",
        path="SKILL.md",
        file_type="skill",
        content=md,
    ).insert()

    doc = await admin_module.SkillAdminService.update_meta(
        "skill_fixed",
        name="new-name",
        description="new desc",
        always=True,
    )
    assert doc.name == "new-name"
    file_doc = FakeSkillFileDoc._files[0]
    fm = parse_frontmatter(file_doc.content)
    assert fm is not None
    name, desc, always, _ = split_promoted_fields(fm)
    assert name == "new-name"
    assert desc == "new desc"
    assert always is True
    assert "# Title" in file_doc.content


@pytest.mark.asyncio
async def test_upsert_skill_md_syncs_aggregate() -> None:
    await FakeSkillDoc(id="skill_fixed", name="old-name", description="").insert()
    await FakeSkillFileDoc(
        skill_id="skill_fixed",
        path="SKILL.md",
        file_type="skill",
        content=build_skill_md("old-name", "", False, {}),
    ).insert()

    new_md = build_skill_md("renamed", "d2", True, {"tag": "x"}, "# body")
    await admin_module.SkillAdminService.upsert_file_content("skill_fixed", "SKILL.md", new_md)
    doc = FakeSkillDoc._skills["skill_fixed"]
    assert doc.name == "renamed"
    assert doc.description == "d2"
    assert doc.always is True
    assert doc.meta.get("tag") == "x"


@pytest.mark.asyncio
async def test_delete_file_forbids_skill_md() -> None:
    await FakeSkillDoc(id="skill_fixed", name="demo-skill").insert()
    with pytest.raises(SkillServiceError) as exc:
        await admin_module.SkillAdminService.delete_file("skill_fixed", "SKILL.md")
    assert exc.value.code == status_codes.INVALID_ARGUMENT


@pytest.mark.asyncio
async def test_delete_blocked_by_agent() -> None:
    await FakeSkillDoc(id="bound_skill", name="bound").insert()
    with pytest.raises(SkillServiceError) as exc:
        await admin_module.SkillAdminService.delete("bound_skill")
    assert exc.value.code == status_codes.CONFLICT_STATE


@pytest.mark.asyncio
async def test_delete_blocked_by_workspace() -> None:
    admin_module.NanobotAgentModel.find_one = AsyncMock(return_value=None)
    await FakeSkillDoc(id="bound_skill", name="bound").insert()
    with pytest.raises(SkillServiceError) as exc:
        await admin_module.SkillAdminService.delete("bound_skill")
    assert exc.value.code == status_codes.CONFLICT_STATE


def test_build_skill_md_roundtrip() -> None:
    md = build_skill_md("my-skill", "说明", True, {"k": 1}, "# 正文")
    fm = parse_frontmatter(md)
    assert fm is not None
    name, desc, always, meta = split_promoted_fields(fm)
    assert name == "my-skill"
    assert desc == "说明"
    assert always is True
    assert meta.get("k") == 1
    assert "# 正文" in md
