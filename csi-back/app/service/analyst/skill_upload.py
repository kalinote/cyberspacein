"""Skill zip 上传与落库。

支持的 zip 布局（可混用多种之一，由内容自动识别）：

1. 扁平单 skill：根目录直接含 SKILL.md、references/ 等
   my.zip → SKILL.md, references/...

2. 单层目录包裹单 skill：zip 内仅一个顶层目录，且该目录含 SKILL.md
   my.zip → my/SKILL.md, my/references/...

3. 多 skill 包：多个顶层目录，各自含 SKILL.md
   skills.zip → my/SKILL.md, clawhub/SKILL.md, ...
"""
from __future__ import annotations

import io
import zipfile
from datetime import datetime

from loguru import logger

import app.utils.status_codes as status_codes
from app.models.agent.skill import NanobotSkillFileModel, NanobotSkillModel
from app.schemas.agent.skill import SkillServiceError, SkillUploadItemSchema
from app.service.analyst.skill_frontmatter import (
    infer_file_type,
    is_allowed_text_path,
    parse_frontmatter,
    split_promoted_fields,
    validate_skill_name,
)
from app.utils.id_lib import generate_id

logger = logger.bind(name=__name__)

MAX_ZIP_BYTES = 5 * 1024 * 1024


class SkillUploadService:
    @classmethod
    async def upload_zip(cls, raw: bytes, filename: str = "") -> list[SkillUploadItemSchema]:
        if len(raw) > MAX_ZIP_BYTES:
            raise SkillServiceError(
                status_codes.INVALID_ARGUMENT,
                f"zip 体积超过限制（{MAX_ZIP_BYTES // 1024 // 1024}MB）",
            )
        try:
            with zipfile.ZipFile(io.BytesIO(raw)) as zf:
                entries = cls._collect_zip_entries(zf)
        except zipfile.BadZipFile as exc:
            raise SkillServiceError(status_codes.INVALID_ARGUMENT, "无效的 zip 文件") from exc

        if not entries:
            raise SkillServiceError(status_codes.INVALID_ARGUMENT, "zip 为空")

        packages = cls._split_into_skill_packages(entries)
        results: list[SkillUploadItemSchema] = []
        for files in packages:
            results.append(await cls._persist_skill_package(files))
        logger.info(
            "Skill zip 上传完成: file={} count={} names={}",
            filename,
            len(results),
            [r.name for r in results],
        )
        return results

    @classmethod
    async def _persist_skill_package(cls, files: dict[str, str]) -> SkillUploadItemSchema:
        skill_md = files.get("SKILL.md")
        if not skill_md:
            raise SkillServiceError(status_codes.INVALID_ARGUMENT, "缺少 SKILL.md")

        frontmatter = parse_frontmatter(skill_md)
        if not frontmatter:
            raise SkillServiceError(status_codes.INVALID_ARGUMENT, "SKILL.md 缺少有效 YAML frontmatter")

        name, description, always, meta = split_promoted_fields(frontmatter)
        name_err = validate_skill_name(name)
        if name_err:
            raise SkillServiceError(status_codes.INVALID_ARGUMENT, name_err)
        if not description:
            raise SkillServiceError(status_codes.INVALID_ARGUMENT, "description 不能为空")

        existing = await NanobotSkillModel.find_one(NanobotSkillModel.name == name)
        now = datetime.now()
        if existing:
            skill_id = existing.id
            existing.description = description
            existing.always = always
            existing.meta = meta
            existing.updated_at = now
            await existing.save()
            await NanobotSkillFileModel.find(
                NanobotSkillFileModel.skill_id == skill_id,
            ).delete()
        else:
            skill_id = generate_id(f"skill:{name}")
            await NanobotSkillModel(
                id=skill_id,
                name=name,
                description=description,
                always=always,
                meta=meta,
                created_at=now,
                updated_at=now,
            ).insert()

        file_count = 0
        for rel_path, content in sorted(files.items()):
            await NanobotSkillFileModel(
                skill_id=skill_id,
                path=rel_path,
                file_type=infer_file_type(rel_path),
                content=content,
                created_at=now,
                updated_at=now,
            ).insert()
            file_count += 1

        return SkillUploadItemSchema(
            skill_id=skill_id,
            name=name,
            file_count=file_count,
            always=always,
        )

    @staticmethod
    def _collect_zip_entries(zf: zipfile.ZipFile) -> dict[str, str]:
        out: dict[str, str] = {}
        for info in zf.infolist():
            if info.is_dir():
                continue
            name = info.filename.replace("\\", "/").lstrip("/")
            if "/__pycache__/" in f"/{name}/" or name.endswith(".pyc"):
                continue
            if not name or ".." in name.split("/"):
                raise SkillServiceError(status_codes.INVALID_ARGUMENT, f"非法路径: {name}")
            if not is_allowed_text_path(name):
                raise SkillServiceError(
                    status_codes.INVALID_ARGUMENT,
                    f"不支持的文件类型或路径: {name}",
                )
            try:
                data = zf.read(info)
                text = data.decode("utf-8")
            except UnicodeDecodeError as exc:
                raise SkillServiceError(
                    status_codes.INVALID_ARGUMENT,
                    f"文件须为 UTF-8 文本: {name}",
                ) from exc
            out[name] = text
        return out

    @staticmethod
    def _skill_root_prefixes(entries: dict[str, str]) -> list[str]:
        """返回每个 skill 包在 zip 内的路径前缀（'' 表示根目录扁平包）。"""
        roots: list[str] = []
        for path in entries:
            norm = path.replace("\\", "/")
            lower = norm.lower()
            if lower == "skill.md":
                roots.append("")
            elif lower.endswith("/skill.md"):
                prefix = norm[: -len("SKILL.md")]
                roots.append(prefix if prefix.endswith("/") else f"{prefix}/")
        return sorted(set(roots), key=len, reverse=True)

    @classmethod
    def _split_into_skill_packages(cls, entries: dict[str, str]) -> list[dict[str, str]]:
        roots = cls._skill_root_prefixes(entries)
        if not roots:
            raise SkillServiceError(status_codes.INVALID_ARGUMENT, "zip 中未找到 SKILL.md")

        if "" in roots and len(roots) > 1:
            raise SkillServiceError(
                status_codes.INVALID_ARGUMENT,
                "不能同时使用根目录 SKILL.md 与多个子目录 skill",
            )

        packages: dict[str, dict[str, str]] = {root: {} for root in roots}
        orphans: list[str] = []

        nested_roots = [r for r in roots if r]

        for path, content in entries.items():
            matched_root: str | None = None
            for root in roots:
                if root == "":
                    if not nested_roots:
                        matched_root = ""
                        break
                    if not any(path.startswith(r) for r in nested_roots):
                        matched_root = ""
                        break
                    continue
                if path.startswith(root):
                    matched_root = root
                    break
            if matched_root is None:
                orphans.append(path)
                continue
            rel = path[len(matched_root):] if matched_root else path
            if rel:
                packages[matched_root][rel] = content

        if orphans:
            raise SkillServiceError(
                status_codes.INVALID_ARGUMENT,
                f"以下文件无法归属到任一 skill 目录: {sorted(orphans)}",
            )

        result: list[dict[str, str]] = []
        for root in sorted(roots, key=len):
            files = packages[root]
            if "SKILL.md" not in files:
                label = "根目录" if root == "" else root.rstrip("/")
                raise SkillServiceError(
                    status_codes.INVALID_ARGUMENT,
                    f"{label} 缺少 SKILL.md",
                )
            if root:
                folder_name = root.rstrip("/").split("/")[-1]
                fm = parse_frontmatter(files["SKILL.md"])
                if fm:
                    skill_name, _, _, _ = split_promoted_fields(fm)
                    if skill_name != folder_name:
                        raise SkillServiceError(
                            status_codes.INVALID_ARGUMENT,
                            f"目录 {folder_name} 与 frontmatter name={skill_name} 不一致",
                        )
            result.append(files)

        if not result:
            raise SkillServiceError(status_codes.INVALID_ARGUMENT, "未解析到有效 skill 包")
        return result

    @staticmethod
    def _resolve_skill_root(entries: dict[str, str]) -> tuple[str, dict[str, str]]:
        """兼容旧单测：解析为单个 skill 包。"""
        packages = SkillUploadService._split_into_skill_packages(entries)
        if len(packages) != 1:
            raise SkillServiceError(
                status_codes.INVALID_ARGUMENT,
                "zip 须只包含一个 skill",
            )
        files = packages[0]
        if "SKILL.md" in entries and "" in SkillUploadService._skill_root_prefixes(entries):
            return "", files
        roots = SkillUploadService._skill_root_prefixes(entries)
        prefix = roots[0] if roots else ""
        return prefix, files
