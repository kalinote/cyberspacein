from __future__ import annotations

from datetime import datetime, timedelta, timezone

from app.core.config import settings
from app.core.permissions import PERMISSION_REGISTRY
from app.core.security import hash_password, verify_password
from app.models.auth.group import GroupModel
from app.models.auth.permission_code import PermissionCodeModel
from app.models.auth.user import UserModel
from app.schemas.auth.user import UserCreateRequest
from app.service.auth_session import (
    clear_login_failures,
    create_user_session,
    ensure_login_allowed,
    record_login_failure,
    terminate_user_sessions,
)
from app.utils.id_lib import generate_id


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


async def get_enabled_groups_by_ids(group_ids: list[str]) -> list[GroupModel]:
    if not group_ids:
        return []
    return await GroupModel.find(
        {"_id": {"$in": list(set(group_ids))}, "is_deleted": False, "enabled": True}
    ).to_list()


async def validate_group_ids(group_ids: list[str]) -> bool:
    if not group_ids:
        return True
    groups = await get_enabled_groups_by_ids(group_ids)
    return len(groups) == len(set(group_ids))


async def get_user_permissions(user: UserModel) -> list[str]:
    if user.is_system:
        return ["*"]
    groups = await get_enabled_groups_by_ids(user.groups)
    requested = {
        permission
        for group in groups
        for permission in group.permissions
        if permission != "*"
    }
    if not requested:
        return []
    active = await PermissionCodeModel.find(
        {
            "perm_key": {"$in": list(requested)},
            "enabled": True,
            "is_deleted": False,
        }
    ).to_list()
    return sorted(
        doc.perm_key
        for doc in active
        if doc.source == "placeholder" or doc.perm_key in PERMISSION_REGISTRY
    )


async def has_backend_permissions(user: UserModel, required: list[str]) -> bool:
    if user.is_system:
        return True
    if not required:
        return True
    if any(code not in PERMISSION_REGISTRY or not PERMISSION_REGISTRY[code].backend_enforced for code in required):
        return False
    permissions = set(await get_user_permissions(user))
    return all(code in permissions for code in required)


def validate_temporary_account(temporary: bool, expired_at: datetime | None) -> None:
    if temporary and expired_at is None:
        raise ValueError("临时账号必须设置到期时间")
    if expired_at is None:
        return
    now = utcnow()
    normalized = _as_utc(expired_at)
    if normalized <= now:
        raise ValueError("账号到期时间必须晚于当前时间")
    if temporary and normalized > now + timedelta(days=settings.TEMPORARY_ACCOUNT_MAX_DAYS):
        raise ValueError(
            f"临时账号到期时间不能超过 {settings.TEMPORARY_ACCOUNT_MAX_DAYS} 天"
        )


async def authenticate_user(
    username: str,
    password: str,
    login_ip: str | None,
    user_agent: str | None = None,
):
    normalized_username = username.strip()
    await ensure_login_allowed(normalized_username, login_ip)
    user = await UserModel.find_one(
        {"username": normalized_username, "is_deleted": False}
    )
    now = utcnow()
    invalid = (
        user is None
        or not user.enabled
        or (user.expired_at is not None and _as_utc(user.expired_at) <= now)
        or not verify_password(password, user.password_hash)
    )
    if invalid:
        await record_login_failure(normalized_username)
        return None

    await clear_login_failures(normalized_username)
    user.login_ip = login_ip
    user.login_date = now
    user.update_at = now
    user.update_by = user.username
    await user.save()
    token, session = await create_user_session(
        user,
        login_ip=login_ip,
        user_agent=user_agent,
    )
    return token, user, await get_user_permissions(user), session


async def get_user_by_id(user_id: str) -> UserModel | None:
    return await UserModel.find_one({"_id": user_id, "is_deleted": False})


async def create_user(data: UserCreateRequest, operator: str = "system") -> UserModel | None:
    existing = await UserModel.find_one({"username": data.username, "is_deleted": False})
    if existing:
        return None
    if data.email:
        existing_email = await UserModel.find_one({"email": data.email, "is_deleted": False})
        if existing_email:
            return None
    validate_temporary_account(data.temporary_account, data.expired_at)
    user = UserModel(
        id=generate_id(data.username + utcnow().isoformat()),
        username=data.username.strip(),
        display_name=data.display_name,
        email=data.email,
        password_hash=hash_password(data.password),
        remark=data.remark,
        enabled=data.enabled,
        temporary_account=data.temporary_account,
        expired_at=data.expired_at,
        groups=list(dict.fromkeys(data.groups)),
        create_by=operator,
    )
    await user.insert()
    return user


async def bump_user_authorization_versions(user_ids: list[str]) -> None:
    if not user_ids:
        return
    users = await UserModel.find(
        {"_id": {"$in": list(set(user_ids))}, "is_deleted": False}
    ).to_list()
    now = utcnow()
    for user in users:
        user.authorization_version += 1
        user.update_at = now
        await user.save()


async def bump_group_member_authorization_versions(group_ids: list[str]) -> None:
    if not group_ids:
        return
    users = await UserModel.find(
        {"groups": {"$in": list(set(group_ids))}, "is_deleted": False}
    ).to_list()
    await bump_user_authorization_versions([user.id for user in users])


async def change_user_credentials(user: UserModel, new_password: str, operator: str) -> None:
    user.password_hash = hash_password(new_password)
    user.credential_version += 1
    user.update_by = operator
    user.update_at = utcnow()
    await user.save()
    await terminate_user_sessions(user.id, reason="password_changed")


async def ensure_default_admin() -> None:
    admin_group = await GroupModel.find_one(
        {"group_name": settings.INIT_SYSTEM_GROUP_NAME, "is_deleted": False}
    )
    if admin_group is None:
        admin_group = GroupModel(
            id=generate_id(settings.INIT_SYSTEM_GROUP_NAME),
            group_name=settings.INIT_SYSTEM_GROUP_NAME,
            display_name="系统内置全权限组",
            remark="系统启动协调，业务 API 不可修改",
            permissions=["*"],
            enabled=True,
            is_system=True,
            create_by="system",
        )
        await admin_group.insert()
    else:
        admin_group.display_name = "系统内置全权限组"
        admin_group.permissions = ["*"]
        admin_group.enabled = True
        admin_group.is_system = True
        admin_group.is_deleted = False
        admin_group.update_by = "system"
        admin_group.update_at = utcnow()
        await admin_group.save()

    admin_user = await UserModel.find_one(
        {"username": settings.INIT_SYSTEM_USERNAME, "is_deleted": False}
    )
    if admin_user is None:
        admin_user = UserModel(
            id=generate_id(settings.INIT_SYSTEM_USERNAME),
            username=settings.INIT_SYSTEM_USERNAME,
            display_name=settings.INIT_SYSTEM_DISPLAY_NAME,
            email=settings.INIT_SYSTEM_EMAIL,
            password_hash=hash_password(settings.INIT_SYSTEM_PASSWORD),
            remark="系统内置用户",
            groups=[admin_group.id],
            is_system=True,
            restrict_permission_assignment=False,
            create_by="system",
        )
        await admin_user.insert()
        return

    password_changed = not verify_password(
        settings.INIT_SYSTEM_PASSWORD, admin_user.password_hash
    )
    admin_user.display_name = settings.INIT_SYSTEM_DISPLAY_NAME
    admin_user.email = settings.INIT_SYSTEM_EMAIL
    admin_user.enabled = True
    admin_user.temporary_account = False
    admin_user.expired_at = None
    admin_user.groups = [admin_group.id]
    admin_user.is_system = True
    admin_user.restrict_permission_assignment = False
    admin_user.is_deleted = False
    if password_changed:
        admin_user.password_hash = hash_password(settings.INIT_SYSTEM_PASSWORD)
        admin_user.credential_version += 1
    admin_user.update_by = "system"
    admin_user.update_at = utcnow()
    await admin_user.save()
    if password_changed:
        await terminate_user_sessions(admin_user.id, reason="system_password_reconciled")
