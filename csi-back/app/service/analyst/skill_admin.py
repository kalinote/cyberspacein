"""Skill 管理端写操作（创建、元数据更新、删除、文件 CRUD）。"""
from __future__ import annotations

from datetime import datetime
from typing import Any

from loguru import logger

import app.utils.status_codes as status_codes
from app.models.agent.nanobot import NanobotAgentModel, NanobotWorkspaceModel
from app.models.agent.skill import NanobotSkillFileModel, NanobotSkillModel
from app.schemas.agent.skill import SkillServiceError
from app.service.analyst.skill_frontmatter import (
    build_skill_md,
    infer_file_type,
    is_allowed_text_path,
    parse_frontmatter,
    split_promoted_fields,
    strip_frontmatter,
    validate_skill_name,
)
from app.utils.id_lib import generate_id

logger = logger.bind(name=__name__)

MAX_FILE_BYTES = 512 * 1024


class SkillAdminService:
    @staticmethod
    def normalize_path(path: str) -> str:
        norm = (path or "").replace("\\", "/").lstrip("/")
        if not norm or ".." in norm.split("/"):
            raise SkillServiceError(status_codes.INVALID_ARGUMENT, "非法文件路径")
        return norm

    @staticmethod
    def _check_content_size(content: str) -> None:
        if len(content.encode("utf-8")) > MAX_FILE_BYTES:
            raise SkillServiceError(
                status_codes.INVALID_ARGUMENT,
                f"单文件内容不能超过 {MAX_FILE_BYTES // 1024}KB",
            )

    @classmethod
    async def _get_skill_or_raise(cls, skill_id: str) -> NanobotSkillModel:
        doc = await NanobotSkillModel.find_one({"_id": skill_id})
        if doc is None:
            raise SkillServiceError(status_codes.NOT_FOUND, f"Skill 不存在: {skill_id}")
        return doc

    @classmethod
    async def _ensure_name_unique(cls, name: str, *, exclude_skill_id: str | None = None) -> None:
        existing = await NanobotSkillModel.find_one({"name": name})
        if existing and existing.id != exclude_skill_id:
            raise SkillServiceError(
                status_codes.CONFLICT_NAME,
                f"Skill 名称已存在: {name}",
            )

    @classmethod
    async def create(
        cls,
        *,
        name: str,
        description: str = "",
        always: bool = False,
        meta: dict[str, Any] | None = None,
        skill_md_body: str = "",
    ) -> NanobotSkillModel:
        name_err = validate_skill_name(name)
        if name_err:
            raise SkillServiceError(status_codes.INVALID_ARGUMENT, name_err)
        await cls._ensure_name_unique(name)

        skill_id = generate_id(f"skill:{name}")
        meta_dict = dict(meta or {})
        skill_md = build_skill_md(name, description, always, meta_dict, skill_md_body)
        cls._check_content_size(skill_md)
        now = datetime.now()

        doc = NanobotSkillModel(
            id=skill_id,
            name=name,
            description=description,
            always=always,
            meta=meta_dict,
            created_at=now,
            updated_at=now,
        )
        await doc.insert()
        await NanobotSkillFileModel(
            skill_id=skill_id,
            path="SKILL.md",
            file_type="skill",
            content=skill_md,
            created_at=now,
            updated_at=now,
        ).insert()
        logger.info("创建 Skill: {} ({})", skill_id, name)
        return doc

    @classmethod
    async def update_meta(
        cls,
        skill_id: str,
        *,
        name: str,
        description: str = "",
        always: bool = False,
        meta: dict[str, Any] | None = None,
    ) -> NanobotSkillModel:
        doc = await cls._get_skill_or_raise(skill_id)
        name_err = validate_skill_name(name)
        if name_err:
            raise SkillServiceError(status_codes.INVALID_ARGUMENT, name_err)
        if name != doc.name:
            await cls._ensure_name_unique(name, exclude_skill_id=skill_id)

        meta_dict = dict(meta or {})
        now = datetime.now()
        doc.name = name
        doc.description = description
        doc.always = always
        doc.meta = meta_dict
        doc.updated_at = now
        await doc.save()

        skill_file = await NanobotSkillFileModel.find_one(
            {"skill_id": skill_id, "path": "SKILL.md"},
        )
        if skill_file is not None:
            body = strip_frontmatter(skill_file.content)
            new_md = build_skill_md(name, description, always, meta_dict, body)
            cls._check_content_size(new_md)
            skill_file.content = new_md
            skill_file.updated_at = now
            await skill_file.save()

        logger.info("更新 Skill 元数据: {}", skill_id)
        return doc

    @classmethod
    async def delete(cls, skill_id: str) -> None:
        doc = await cls._get_skill_or_raise(skill_id)

        bound_agent = await NanobotAgentModel.find_one({"skills": skill_id})
        if bound_agent:
            raise SkillServiceError(
                status_codes.CONFLICT_STATE,
                f"仍有 Agent[{bound_agent.id}:{bound_agent.name}] 引用该 Skill，无法删除",
            )
        workspace_ref = await NanobotWorkspaceModel.find_one({"enabled_skills": skill_id})
        if workspace_ref:
            raise SkillServiceError(
                status_codes.CONFLICT_STATE,
                f"仍有工作区[{workspace_ref.id}:{workspace_ref.name}] 启用该 Skill，无法删除",
            )

        await NanobotSkillFileModel.find({"skill_id": skill_id}).delete()
        await doc.delete()
        logger.info("删除 Skill: {}", skill_id)

    @classmethod
    async def get_file_content(cls, skill_id: str, path: str) -> NanobotSkillFileModel:
        await cls._get_skill_or_raise(skill_id)
        norm = cls.normalize_path(path)
        file_doc = await NanobotSkillFileModel.find_one(
            {"skill_id": skill_id, "path": norm},
        )
        if file_doc is None:
            raise SkillServiceError(status_codes.NOT_FOUND, f"文件不存在: {norm}")
        return file_doc

    @classmethod
    async def _sync_skill_from_skill_md(
        cls,
        doc: NanobotSkillModel,
        content: str,
    ) -> None:
        frontmatter = parse_frontmatter(content)
        if not frontmatter:
            raise SkillServiceError(status_codes.INVALID_ARGUMENT, "SKILL.md 缺少有效 YAML frontmatter")
        name, description, always, meta = split_promoted_fields(frontmatter)
        name_err = validate_skill_name(name)
        if name_err:
            raise SkillServiceError(status_codes.INVALID_ARGUMENT, name_err)
        if name != doc.name:
            await cls._ensure_name_unique(name, exclude_skill_id=doc.id)
        doc.name = name
        doc.description = description
        doc.always = always
        doc.meta = meta
        doc.updated_at = datetime.now()
        await doc.save()

    @classmethod
    async def upsert_file_content(
        cls,
        skill_id: str,
        path: str,
        content: str,
    ) -> NanobotSkillFileModel:
        doc = await cls._get_skill_or_raise(skill_id)
        norm = cls.normalize_path(path)
        if not is_allowed_text_path(norm):
            raise SkillServiceError(status_codes.INVALID_ARGUMENT, f"不支持的文件类型或路径: {norm}")
        cls._check_content_size(content)

        now = datetime.now()
        file_doc = await NanobotSkillFileModel.find_one(
            {"skill_id": skill_id, "path": norm},
        )
        if file_doc is None:
            raise SkillServiceError(status_codes.NOT_FOUND, f"文件不存在: {norm}，请使用 POST 创建")

        file_doc.content = content
        file_doc.file_type = infer_file_type(norm)
        file_doc.updated_at = now
        await file_doc.save()

        if norm.lower() == "skill.md":
            await cls._sync_skill_from_skill_md(doc, content)
            doc = await cls._get_skill_or_raise(skill_id)

        return file_doc

    @classmethod
    async def create_file(
        cls,
        skill_id: str,
        path: str,
        content: str,
    ) -> NanobotSkillFileModel:
        doc = await cls._get_skill_or_raise(skill_id)
        norm = cls.normalize_path(path)
        if not is_allowed_text_path(norm):
            raise SkillServiceError(status_codes.INVALID_ARGUMENT, f"不支持的文件类型或路径: {norm}")
        cls._check_content_size(content)

        existing = await NanobotSkillFileModel.find_one(
            {"skill_id": skill_id, "path": norm},
        )
        if existing is not None:
            raise SkillServiceError(status_codes.CONFLICT_EXISTS, f"文件已存在: {norm}")

        now = datetime.now()
        file_doc = NanobotSkillFileModel(
            skill_id=skill_id,
            path=norm,
            file_type=infer_file_type(norm),
            content=content,
            created_at=now,
            updated_at=now,
        )
        await file_doc.insert()

        if norm.lower() == "skill.md":
            await cls._sync_skill_from_skill_md(doc, content)

        return file_doc

    @classmethod
    async def delete_file(cls, skill_id: str, path: str) -> None:
        await cls._get_skill_or_raise(skill_id)
        norm = cls.normalize_path(path)
        if norm.lower() == "skill.md":
            raise SkillServiceError(status_codes.INVALID_ARGUMENT, "不能删除 SKILL.md")

        file_doc = await NanobotSkillFileModel.find_one(
            {"skill_id": skill_id, "path": norm},
        )
        if file_doc is None:
            raise SkillServiceError(status_codes.NOT_FOUND, f"文件不存在: {norm}")
        await file_doc.delete()
