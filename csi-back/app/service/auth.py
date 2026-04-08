from datetime import datetime

from app.core.config import settings
from app.core.security import create_access_token, hash_password, verify_password
from app.models.auth.group import GroupModel
from app.models.auth.user import UserModel
from app.schemas.auth.user import UserCreateRequest
from app.utils.id_lib import generate_id


async def get_enabled_groups_by_ids(group_ids: list[str]) -> list[GroupModel]:
    if not group_ids:
        return []
    groups = await GroupModel.find(
        {"_id": {"$in": group_ids}, "is_deleted": False, "enabled": True}
    ).to_list()
    return groups


async def validate_group_ids(group_ids: list[str]) -> bool:
    if not group_ids:
        return True
    groups = await get_enabled_groups_by_ids(group_ids)
    return len(groups) == len(set(group_ids))


async def get_user_permissions(user: UserModel) -> list[str]:
    groups = await get_enabled_groups_by_ids(user.groups)
    permissions: set[str] = set()
    for group in groups:
        for permission in group.permissions:
            permissions.add(permission)
    return sorted(list(permissions))


async def authenticate_user(username: str, password: str, login_ip: str | None) -> tuple[str, UserModel, list[str]] | None:
    user = await UserModel.find_one({"username": username, "is_deleted": False})
    if not user:
        return None
    if not user.enabled:
        return None
    if user.expired_at is not None and user.expired_at <= datetime.now():
        return None
    if not verify_password(password, user.password_hash):
        return None

    user.login_ip = login_ip
    user.login_date = datetime.now()
    user.update_at = datetime.now()
    user.update_by = user.username
    await user.save()

    token = create_access_token(user.id)
    permissions = await get_user_permissions(user)
    return token, user, permissions


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

    user_id = generate_id(data.username + datetime.now().isoformat())
    user = UserModel(
        id=user_id,
        username=data.username,
        display_name=data.display_name,
        email=data.email,
        password_hash=hash_password(data.password),
        remark=data.remark,
        enabled=data.enabled,
        temporary_account=data.temporary_account,
        expired_at=data.expired_at,
        groups=data.groups,
        create_by=operator,
    )
    await user.insert()
    return user


async def ensure_default_admin() -> None:
    admin_group = await GroupModel.find_one(
        {"group_name": settings.INIT_SYSTEM_GROUP_NAME, "is_deleted": False}
    )
    if not admin_group:
        group_id = generate_id(settings.INIT_SYSTEM_GROUP_NAME)
        admin_group = GroupModel(
            id=group_id,
            group_name=settings.INIT_SYSTEM_GROUP_NAME,
            display_name="系统组",
            remark="系统初始化组",
            permissions=["*"],
            create_by="system",
        )
        await admin_group.insert()

    admin_user = await UserModel.find_one(
        {"username": settings.INIT_SYSTEM_USERNAME, "is_deleted": False}
    )
    if not admin_user:
        admin_user = UserModel(
            id=generate_id(settings.INIT_SYSTEM_USERNAME),
            username=settings.INIT_SYSTEM_USERNAME,
            display_name=settings.INIT_SYSTEM_DISPLAY_NAME,
            email=settings.INIT_SYSTEM_EMAIL,
            password_hash=hash_password(settings.INIT_SYSTEM_PASSWORD),
            remark="系统内置用户",
            groups=[admin_group.id],
            create_by="system",
        )
        await admin_user.insert()
