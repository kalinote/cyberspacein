"""Skill SKILL.md frontmatter 解析与校验。"""
from __future__ import annotations

import json
import re
from typing import Any

import yaml

_STRIP_SKILL_FRONTMATTER = re.compile(
    r"^---\s*\r?\n(.*?)\r?\n---\s*\r?\n?",
    re.DOTALL,
)

MAX_SKILL_NAME_LENGTH = 64
_SKILL_NAME_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")

TEXT_EXTENSIONS = frozenset({
    ".md", ".py", ".sh", ".json", ".yaml", ".yml", ".txt", ".toml",
    ".js", ".ts", ".css", ".html", ".xml", ".ini", ".cfg",
})


def strip_frontmatter(content: str) -> str:
    if not content.startswith("---"):
        return content
    match = _STRIP_SKILL_FRONTMATTER.match(content)
    if match:
        return content[match.end():].strip()
    return content


def parse_frontmatter(content: str) -> dict[str, Any] | None:
    if not content.startswith("---"):
        return None
    match = _STRIP_SKILL_FRONTMATTER.match(content)
    if not match:
        return None
    try:
        parsed = yaml.safe_load(match.group(1))
    except yaml.YAMLError:
        return None
    if not isinstance(parsed, dict):
        return None
    return {str(k): v for k, v in parsed.items()}


def split_promoted_fields(frontmatter: dict[str, Any]) -> tuple[str, str, bool, dict[str, Any]]:
    name = str(frontmatter.get("name") or "").strip()
    description = str(frontmatter.get("description") or "").strip()
    always_raw = frontmatter.get("always", False)
    always = bool(always_raw) if isinstance(always_raw, bool) else str(always_raw).lower() in ("true", "1", "yes")
    meta: dict[str, Any] = {}
    for key, value in frontmatter.items():
        if key in ("name", "description", "always"):
            continue
        meta[key] = value
    return name, description, always, meta


def validate_skill_name(name: str) -> str | None:
    if not name:
        return "name 不能为空"
    if len(name) > MAX_SKILL_NAME_LENGTH:
        return f"name 长度不能超过 {MAX_SKILL_NAME_LENGTH}"
    if not _SKILL_NAME_RE.match(name):
        return "name 须为小写连字符格式（如 my-skill）"
    return None


def parse_nanobot_metadata(meta: dict[str, Any]) -> dict[str, Any]:
    raw = meta.get("metadata")
    if isinstance(raw, dict):
        data = raw
    elif isinstance(raw, str):
        try:
            data = json.loads(raw)
        except (json.JSONDecodeError, TypeError):
            return {}
    else:
        return {}
    if not isinstance(data, dict):
        return {}
    payload = data.get("nanobot", data.get("openclaw", {}))
    return payload if isinstance(payload, dict) else {}


def infer_file_type(relative_path: str) -> str:
    norm = relative_path.replace("\\", "/").lstrip("/")
    lower = norm.lower()
    if lower == "skill.md":
        return "skill"
    if lower.startswith("references/"):
        return "reference"
    if lower.startswith("scripts/"):
        return "script"
    if lower.startswith("assets/"):
        return "asset"
    return "other"


def is_allowed_text_path(relative_path: str) -> bool:
    norm = relative_path.replace("\\", "/").lstrip("/")
    if ".." in norm.split("/"):
        return False
    suffix = "." + norm.rsplit(".", 1)[-1].lower() if "." in norm else ""
    if suffix and suffix not in TEXT_EXTENSIONS:
        return False
    return True


def build_skill_md(
    name: str,
    description: str,
    always: bool,
    meta: dict[str, Any] | None = None,
    body: str = "",
) -> str:
    """根据元数据生成 SKILL.md 全文（含 YAML frontmatter）。"""
    fm: dict[str, Any] = {
        "name": name,
        "description": description,
        "always": always,
    }
    for key, value in (meta or {}).items():
        if key in ("name", "description", "always"):
            continue
        fm[key] = value
    yaml_block = yaml.dump(
        fm,
        allow_unicode=True,
        default_flow_style=False,
        sort_keys=False,
    ).strip()
    body_part = (body or "").strip()
    if body_part:
        return f"---\n{yaml_block}\n---\n\n{body_part}\n"
    return f"---\n{yaml_block}\n---\n"
