from __future__ import annotations

from datetime import datetime, timezone

from app.core.exceptions import ForbiddenException
from app.core.permissions import PERMISSION_REGISTRY
from app.models.auth.group import GroupModel
from app.models.auth.permission_code import PermissionCodeModel
from app.models.auth.user import UserModel
from app.service.auth import get_user_permissions


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def ensure_mutable_user(user: UserModel) -> None:
    if user.is_system:
        raise ForbiddenException("系统内置账号不可通过业务 API 修改或删除")


def ensure_mutable_group(group: GroupModel) -> None:
    if group.is_system:
        raise ForbiddenException("系统内置权限组不可通过业务 API 修改或删除")


async def validate_permission_assignment(
    operator: UserModel,
    permission_codes: list[str],
) -> list[str]:
    normalized = list(dict.fromkeys(permission_codes))
    if "*" in normalized:
        raise ForbiddenException("普通权限组不能拥有超级权限 *")
    if not normalized:
        return []
    docs = await PermissionCodeModel.find(
        {
            "perm_key": {"$in": normalized},
            "enabled": True,
            "is_deleted": False,
        }
    ).to_list()
    by_code = {doc.perm_key: doc for doc in docs}
    missing = [code for code in normalized if code not in by_code]
    if missing:
        raise ForbiddenException(f"权限不存在或未启用: {', '.join(missing)}")
    reserved = [code for code, doc in by_code.items() if doc.system_reserved]
    if reserved:
        raise ForbiddenException(f"系统保留权限不可分配: {', '.join(reserved)}")
    if not operator.restrict_permission_assignment:
        return normalized
    operator_permissions = set(await get_user_permissions(operator))
    denied: list[str] = []
    for code in normalized:
        doc = by_code[code]
        definition = PERMISSION_REGISTRY.get(code)
        delegable = definition.delegable if definition is not None else doc.delegable
        if code not in operator_permissions or not delegable:
            denied.append(code)
    if denied:
        raise ForbiddenException(f"超出当前账号可分配权限范围: {', '.join(denied)}")
    return normalized


async def validate_group_assignment(
    operator: UserModel,
    group_ids: list[str],
) -> list[str]:
    normalized = list(dict.fromkeys(group_ids))
    if not normalized:
        return []
    groups = await GroupModel.find(
        {"_id": {"$in": normalized}, "enabled": True, "is_deleted": False}
    ).to_list()
    by_id = {group.id: group for group in groups}
    missing = [group_id for group_id in normalized if group_id not in by_id]
    if missing:
        raise ForbiddenException(f"权限组不存在或未启用: {', '.join(missing)}")
    if any(group.is_system for group in groups):
        raise ForbiddenException("系统内置全权限组不能分配给普通账号")
    await validate_permission_assignment(
        operator,
        [permission for group in groups for permission in group.permissions],
    )
    return normalized


async def get_permission_impact(permission_code: str) -> tuple[list[str], list[str]]:
    groups = await GroupModel.find(
        {
            "permissions": permission_code,
            "is_deleted": False,
        }
    ).to_list()
    group_ids = sorted(group.id for group in groups)
    if not group_ids:
        return [], []
    users = await UserModel.find(
        {"groups": {"$in": group_ids}, "is_deleted": False}
    ).to_list()
    return group_ids, sorted(user.id for user in users)
