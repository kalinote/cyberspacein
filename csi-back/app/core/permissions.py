from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml


_PERMISSION_FILE = Path(__file__).with_name("permissions.yml")
_PAGE_PATTERN = re.compile(r"^page:[a-z0-9][a-z0-9-]*(?::[a-z0-9][a-z0-9-]*)*:(visible|access)$")
_OPERATION_PATTERN = re.compile(
    r"^operation:[a-z0-9][a-z0-9-]*:[a-z0-9][a-z0-9-]*:(read|create|update|delete|execute)$"
)


@dataclass(frozen=True, slots=True)
class PermissionDefinition:
    code: str
    name: str
    module: str
    resource: str
    description: str
    tags: tuple[str, ...]
    system_reserved: bool
    delegable: bool
    default_enabled: bool
    backend_enforced: bool


def _require_bool(item: dict[str, Any], field: str) -> bool:
    value = item.get(field)
    if not isinstance(value, bool):
        raise RuntimeError(f"权限 {item.get('code', '<unknown>')} 的 {field} 必须是 bool")
    return value


def _load_permission_manifest() -> tuple[str, tuple[PermissionDefinition, ...], str]:
    raw_bytes = _PERMISSION_FILE.read_bytes()
    raw = yaml.safe_load(raw_bytes)
    if not isinstance(raw, dict) or not isinstance(raw.get("permissions"), list):
        raise RuntimeError("permissions.yml 必须包含 permissions 列表")
    version = str(raw.get("version") or "").strip()
    if not version:
        raise RuntimeError("permissions.yml 缺少 version")

    definitions: list[PermissionDefinition] = []
    seen: set[str] = set()
    for item in raw["permissions"]:
        if not isinstance(item, dict):
            raise RuntimeError("permissions.yml 中每个权限必须是对象")
        code = str(item.get("code") or "").strip()
        if code != "*" and not (_PAGE_PATTERN.fullmatch(code) or _OPERATION_PATTERN.fullmatch(code)):
            raise RuntimeError(f"非法权限码: {code}")
        if code in seen:
            raise RuntimeError(f"重复权限码: {code}")
        seen.add(code)
        tags = item.get("tags")
        if not isinstance(tags, list) or not all(isinstance(tag, str) and tag for tag in tags):
            raise RuntimeError(f"权限 {code} 的 tags 必须是非空字符串列表")
        definition = PermissionDefinition(
            code=code,
            name=str(item.get("name") or "").strip(),
            module=str(item.get("module") or "").strip(),
            resource=str(item.get("resource") or "").strip(),
            description=str(item.get("description") or "").strip(),
            tags=tuple(tags),
            system_reserved=_require_bool(item, "system_reserved"),
            delegable=_require_bool(item, "delegable"),
            default_enabled=_require_bool(item, "default_enabled"),
            backend_enforced=_require_bool(item, "backend_enforced"),
        )
        if not all((definition.name, definition.module, definition.resource, definition.description)):
            raise RuntimeError(f"权限 {code} 的展示字段不完整")
        if code.startswith("page:") and definition.backend_enforced:
            raise RuntimeError(f"页面权限不能作为后端放行依据: {code}")
        if code == "*" and (not definition.system_reserved or definition.delegable):
            raise RuntimeError("* 必须是不可委派的系统保留权限")
        definitions.append(definition)

    digest = hashlib.sha256(raw_bytes).hexdigest()[:16]
    return version, tuple(definitions), digest


PERMISSION_MANIFEST_VERSION, PERMISSION_DEFINITIONS, PERMISSION_MANIFEST_DIGEST = _load_permission_manifest()
PERMISSION_REGISTRY = {item.code: item for item in PERMISSION_DEFINITIONS}
STANDARD_PERMISSION_CODES = frozenset(PERMISSION_REGISTRY)
BACKEND_PERMISSION_CODES = frozenset(
    item.code for item in PERMISSION_DEFINITIONS if item.backend_enforced
)
DELEGABLE_PERMISSION_CODES = frozenset(
    item.code for item in PERMISSION_DEFINITIONS if item.delegable
)


def is_declared_permission(code: str) -> bool:
    return code in STANDARD_PERMISSION_CODES


def is_backend_permission(code: str) -> bool:
    return code in BACKEND_PERMISSION_CODES


def validate_placeholder_permission_code(code: str) -> bool:
    """Placeholders may use the normal naming grammar but cannot shadow standards."""
    return (
        code != "*"
        and code not in STANDARD_PERMISSION_CODES
        and bool(_PAGE_PATTERN.fullmatch(code) or _OPERATION_PATTERN.fullmatch(code))
    )


async def sync_standard_permissions() -> None:
    """Reconcile YAML standard permissions into MongoDB without re-enabling manual disables."""
    from app.models.auth.permission_code import PermissionCodeModel
    from app.utils.id_lib import generate_id

    now = datetime.now(timezone.utc)
    for definition in PERMISSION_DEFINITIONS:
        doc = await PermissionCodeModel.find_one({"perm_key": definition.code})
        if doc is None:
            doc = PermissionCodeModel(
                id=generate_id(f"standard-permission:{definition.code}"),
                perm_key=definition.code,
                name=definition.name,
                category=f"{definition.module}:{definition.resource}",
                desc=definition.description,
                tags=list(definition.tags),
                module=definition.module,
                resource=definition.resource,
                source="standard",
                backend_enforced=definition.backend_enforced,
                system_reserved=definition.system_reserved,
                delegable=definition.delegable,
                default_enabled=definition.default_enabled,
                enabled=definition.default_enabled,
                yaml_version=f"{PERMISSION_MANIFEST_VERSION}:{PERMISSION_MANIFEST_DIGEST}",
                create_by="system",
            )
            await doc.insert()
            continue

        doc.name = definition.name
        doc.category = f"{definition.module}:{definition.resource}"
        doc.desc = definition.description
        doc.tags = list(definition.tags)
        doc.module = definition.module
        doc.resource = definition.resource
        doc.source = "standard"
        doc.backend_enforced = definition.backend_enforced
        doc.system_reserved = definition.system_reserved
        doc.delegable = definition.delegable
        doc.default_enabled = definition.default_enabled
        doc.yaml_version = f"{PERMISSION_MANIFEST_VERSION}:{PERMISSION_MANIFEST_DIGEST}"
        doc.is_deleted = False
        doc.update_by = "system"
        doc.update_at = now
        await doc.save()

    stale = await PermissionCodeModel.find(
        {
            "source": "standard",
            "perm_key": {"$nin": list(STANDARD_PERMISSION_CODES)},
            "is_deleted": False,
        }
    ).to_list()
    for doc in stale:
        doc.enabled = False
        doc.backend_enforced = False
        doc.is_deleted = True
        doc.update_by = "system"
        doc.update_at = now
        await doc.save()
