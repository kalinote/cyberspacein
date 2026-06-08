"""Mongo Skill 查询与运行时拼装。"""
from __future__ import annotations

import os
import re
import shutil
from dataclasses import dataclass
from typing import Any

from loguru import logger

from app.models.agent.skill import NanobotSkillFileModel, NanobotSkillModel
from app.service.analyst.skill_frontmatter import (
    parse_nanobot_metadata,
    strip_frontmatter,
)

logger = logger.bind(name=__name__)


@dataclass(frozen=True, slots=True)
class SkillMeta:
    skill_id: str
    name: str
    description: str
    always: bool
    meta: dict[str, Any]


class SkillService:
    @staticmethod
    def resolve_enabled_skill_ids(
        agent_skills: list[str],
        workspace_enabled_skills: list[str],
    ) -> list[str]:
        allowed = set(workspace_enabled_skills or [])
        return [sid for sid in (agent_skills or []) if sid in allowed]

    @classmethod
    async def fetch_metas_by_ids(cls, skill_ids: list[str]) -> list[SkillMeta]:
        if not skill_ids:
            return []
        docs = await NanobotSkillModel.find({"_id": {"$in": list(skill_ids)}}).to_list()
        by_id = {doc.id: doc for doc in docs}
        result: list[SkillMeta] = []
        for sid in skill_ids:
            doc = by_id.get(sid)
            if doc is None:
                continue
            result.append(
                SkillMeta(
                    skill_id=doc.id,
                    name=doc.name,
                    description=doc.description,
                    always=doc.always,
                    meta=dict(doc.meta or {}),
                )
            )
        return result

    @classmethod
    async def list_enabled_for_agent(
        cls,
        agent_skills: list[str],
        workspace_enabled_skills: list[str],
    ) -> list[SkillMeta]:
        ids = cls.resolve_enabled_skill_ids(agent_skills, workspace_enabled_skills)
        return await cls.fetch_metas_by_ids(ids)

    @classmethod
    async def get_by_id(cls, skill_id: str) -> NanobotSkillModel | None:
        return await NanobotSkillModel.find_one({"_id": skill_id})

    @classmethod
    async def get_by_name(cls, name: str) -> NanobotSkillModel | None:
        return await NanobotSkillModel.find_one(NanobotSkillModel.name == name)

    @classmethod
    async def ensure_skill_ids_exist(cls, skill_ids: list[str]) -> set[str]:
        unique = set(skill_ids or [])
        if not unique:
            return set()
        docs = await NanobotSkillModel.find({"_id": {"$in": list(unique)}}).to_list()
        return {doc.id for doc in docs}

    @classmethod
    def check_requirements(cls, meta: dict[str, Any]) -> bool:
        nanobot_meta = parse_nanobot_metadata(meta)
        requires = nanobot_meta.get("requires", {})
        if not isinstance(requires, dict):
            return True
        required_bins = requires.get("bins", [])
        required_env = requires.get("env", [])
        if not isinstance(required_bins, list):
            required_bins = []
        if not isinstance(required_env, list):
            required_env = []
        return all(shutil.which(str(cmd)) for cmd in required_bins) and all(
            os.environ.get(str(var)) for var in required_env
        )

    @classmethod
    def missing_requirements(cls, meta: dict[str, Any]) -> str:
        nanobot_meta = parse_nanobot_metadata(meta)
        requires = nanobot_meta.get("requires", {})
        if not isinstance(requires, dict):
            return ""
        required_bins = requires.get("bins", [])
        required_env = requires.get("env", [])
        if not isinstance(required_bins, list):
            required_bins = []
        if not isinstance(required_env, list):
            required_env = []
        parts = [
            f"CLI: {command_name}"
            for command_name in required_bins
            if not shutil.which(str(command_name))
        ] + [
            f"ENV: {env_name}"
            for env_name in required_env
            if not os.environ.get(str(env_name))
        ]
        return ", ".join(parts)

    @classmethod
    async def load_file_content(cls, skill_id: str, path: str) -> str | None:
        norm = path.replace("\\", "/").lstrip("/") or "SKILL.md"
        doc = await NanobotSkillFileModel.find_one(
            NanobotSkillFileModel.skill_id == skill_id,
            NanobotSkillFileModel.path == norm,
        )
        if doc is None:
            return None
        return doc.content

    @classmethod
    async def load_always_content(
        cls,
        agent_skills: list[str],
        workspace_enabled_skills: list[str],
    ) -> str:
        metas = await cls.list_enabled_for_agent(agent_skills, workspace_enabled_skills)
        always_ids = [m.skill_id for m in metas if m.always and cls.check_requirements(m.meta)]
        if not always_ids:
            return ""
        parts: list[str] = []
        for skill_id in always_ids:
            meta = next(m for m in metas if m.skill_id == skill_id)
            raw = await cls.load_file_content(skill_id, "SKILL.md")
            if not raw:
                continue
            body = strip_frontmatter(raw)
            parts.append(f"### Skill: {meta.name}\n\n{body}")
        return "\n\n---\n\n".join(parts)

    @classmethod
    async def build_summary(
        cls,
        agent_skills: list[str],
        workspace_enabled_skills: list[str],
        *,
        exclude_skill_ids: set[str] | None = None,
    ) -> str:
        metas = await cls.list_enabled_for_agent(agent_skills, workspace_enabled_skills)
        if not metas:
            return ""
        lines: list[str] = []
        for meta in metas:
            if exclude_skill_ids and meta.skill_id in exclude_skill_ids:
                continue
            available = cls.check_requirements(meta.meta)
            desc = meta.description or meta.name
            if available:
                lines.append(f"- **{meta.name}** (`{meta.skill_id}`) — {desc}")
            else:
                missing = cls.missing_requirements(meta.meta)
                suffix = f" (unavailable: {missing})" if missing else " (unavailable)"
                lines.append(f"- **{meta.name}** (`{meta.skill_id}`) — {desc}{suffix}")
        if lines:
            lines.append("")
            lines.append("非 always 技能请使用 `use_skill` 工具加载正文或子文件（参数 path）。")
        return "\n".join(lines)

    @classmethod
    async def load_for_tool(
        cls,
        skill_id: str,
        path: str,
    ) -> tuple[str | None, str | None]:
        """返回 (正文, 错误信息)。"""
        skill = await cls.get_by_id(skill_id)
        if skill is None:
            return None, f"Skill 不存在: {skill_id}"
        if not cls.check_requirements(skill.meta or {}):
            missing = cls.missing_requirements(skill.meta or {})
            return None, f"Skill 环境要求未满足: {missing or 'unknown'}"
        norm = (path or "SKILL.md").replace("\\", "/").lstrip("/")
        raw = await cls.load_file_content(skill_id, norm)
        if raw is None:
            return None, f"文件不存在: {norm}"
        if norm.lower() == "skill.md":
            return strip_frontmatter(raw), None
        return raw, None

    @classmethod
    async def count_files(cls, skill_id: str) -> int:
        return await NanobotSkillFileModel.find(
            NanobotSkillFileModel.skill_id == skill_id,
        ).count()

    @classmethod
    async def list_page(
        cls,
        *,
        page: int,
        page_size: int,
        search: str | None = None,
    ) -> tuple[list[tuple[NanobotSkillModel, int]], int]:
        filters: dict[str, Any] = {}
        if search and search.strip():
            pattern = re_escape_regex(search.strip())
            filters["$or"] = [
                {"name": {"$regex": pattern, "$options": "i"}},
                {"description": {"$regex": pattern, "$options": "i"}},
            ]
        query = NanobotSkillModel.find(filters) if filters else NanobotSkillModel.find()
        total = await query.count()
        docs = (
            await query.sort(-NanobotSkillModel.updated_at)
            .skip((page - 1) * page_size)
            .limit(page_size)
            .to_list()
        )
        rows: list[tuple[NanobotSkillModel, int]] = []
        for doc in docs:
            fc = await cls.count_files(doc.id)
            rows.append((doc, fc))
        return rows, total

    @classmethod
    async def list_all_brief(cls) -> list[NanobotSkillModel]:
        return await NanobotSkillModel.find().sort(NanobotSkillModel.name).to_list()

    @classmethod
    async def list_brief_by_ids(cls, skill_ids: list[str]) -> list[NanobotSkillModel]:
        ordered_ids = list(dict.fromkeys(skill_ids or []))
        if not ordered_ids:
            return []
        docs = await NanobotSkillModel.find({"_id": {"$in": ordered_ids}}).to_list()
        by_id = {doc.id: doc for doc in docs}
        return [by_id[sid] for sid in ordered_ids if sid in by_id]

    @classmethod
    async def list_files(cls, skill_id: str) -> list[NanobotSkillFileModel]:
        return await NanobotSkillFileModel.find(
            NanobotSkillFileModel.skill_id == skill_id,
        ).sort(NanobotSkillFileModel.path).to_list()


def re_escape_regex(text: str) -> str:
    return re.escape(text)
