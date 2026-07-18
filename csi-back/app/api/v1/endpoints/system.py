from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends, Query

import app.utils.status_codes as status_codes
from app.core.exceptions import BadRequestException, ForbiddenException
from app.core.permissions import validate_placeholder_permission_code
from app.dependencies.auth import get_current_user
from app.models.auth.group import GroupModel
from app.models.auth.permission_code import PermissionCodeModel
from app.models.auth.session import LoginSessionModel
from app.models.auth.user import UserModel
from app.schemas.auth.group import GroupCreateRequest, GroupResponse, GroupUpdateRequest
from app.schemas.auth.permission_code import (
    PermissionCodeBatchCreateRequest,
    PermissionCodeCreateRequest,
    PermissionCodeListQuery,
    PermissionCodeMigrationRequest,
    PermissionCodeResponse,
    PermissionCodeUpdateRequest,
    PermissionImpactResponse,
)
from app.schemas.auth.session import LoginSessionResponse
from app.schemas.auth.user import (
    AssignmentScopeUpdateRequest,
    UserCreateRequest,
    UserExpiryUpdateRequest,
    UserGroupUpdateRequest,
    UserListItemResponse,
    UserPasswordUpdateRequest,
    UserProfileUpdateRequest,
    UserResponse,
    UserStatusUpdateRequest,
)
from app.schemas.general import PageParamsSchema, PageResponseSchema
from app.schemas.response import ApiResponseSchema
from app.service.auth import (
    bump_group_member_authorization_versions,
    bump_user_authorization_versions,
    change_user_credentials,
    create_user,
    validate_temporary_account,
)
from app.service.auth_session import (
    as_utc,
    terminate_session_by_id,
    terminate_user_sessions,
)
from app.service.permission_admin import (
    ensure_mutable_group,
    ensure_mutable_user,
    get_permission_impact,
    validate_group_assignment,
    validate_permission_assignment,
)
from app.utils.id_lib import generate_id


router = APIRouter(prefix="/system", tags=["系统用户与权限"])


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


async def _get_user(user_id: str) -> UserModel:
    user = await UserModel.find_one({"_id": user_id, "is_deleted": False})
    if user is None:
        raise BadRequestException(f"用户不存在，ID: {user_id}")
    return user


async def _get_group(group_id: str) -> GroupModel:
    group = await GroupModel.find_one({"_id": group_id, "is_deleted": False})
    if group is None:
        raise BadRequestException(f"权限组不存在，ID: {group_id}")
    return group


async def _get_permission(permission_id: str) -> PermissionCodeModel:
    doc = await PermissionCodeModel.find_one({"_id": permission_id, "is_deleted": False})
    if doc is None:
        raise BadRequestException(f"权限码不存在，ID: {permission_id}")
    return doc


@router.get("/users", response_model=PageResponseSchema[UserListItemResponse], summary="分页获取用户列表")
async def get_user_list(params: PageParamsSchema = Depends()):
    query = UserModel.find({"is_deleted": False})
    total = await query.count()
    users = await query.skip((params.page - 1) * params.page_size).limit(params.page_size).to_list()
    return PageResponseSchema.create(
        [UserListItemResponse.from_doc(user) for user in users],
        total,
        params.page,
        params.page_size,
    )


@router.get("/users/{user_id}", response_model=ApiResponseSchema[UserResponse], summary="获取用户详情")
async def get_user_detail(user_id: str):
    return ApiResponseSchema.success(data=UserResponse.from_doc(await _get_user(user_id)))


@router.post("/users", response_model=ApiResponseSchema[UserResponse], summary="创建用户")
async def create_system_user(
    data: UserCreateRequest,
    current_user: UserModel = Depends(get_current_user),
):
    groups = await validate_group_assignment(current_user, data.groups)
    try:
        validate_temporary_account(data.temporary_account, data.expired_at)
    except ValueError as exc:
        raise BadRequestException(str(exc)) from exc
    normalized = data.model_copy(update={"groups": groups})
    user = await create_user(normalized, operator=current_user.username)
    if user is None:
        return ApiResponseSchema.error(
            code=status_codes.CONFLICT_EXISTS,
            message="用户名或邮箱已存在",
        )
    return ApiResponseSchema.success(data=UserResponse.from_doc(user))


@router.patch("/users/{user_id}/profile", response_model=ApiResponseSchema[UserResponse], summary="更新用户资料")
async def update_user_profile(
    user_id: str,
    data: UserProfileUpdateRequest,
    current_user: UserModel = Depends(get_current_user),
):
    user = await _get_user(user_id)
    ensure_mutable_user(user)
    update_data = data.model_dump(exclude_unset=True)
    if "email" in update_data and update_data["email"]:
        duplicate = await UserModel.find_one(
            {"email": update_data["email"], "_id": {"$ne": user.id}, "is_deleted": False}
        )
        if duplicate:
            return ApiResponseSchema.error(code=status_codes.CONFLICT_EXISTS, message="邮箱已存在")
    for key, value in update_data.items():
        setattr(user, key, value)
    user.update_by = current_user.username
    user.update_at = utcnow()
    await user.save()
    return ApiResponseSchema.success(data=UserResponse.from_doc(user))


@router.patch("/users/{user_id}/groups", response_model=ApiResponseSchema[UserResponse], summary="调整用户权限组")
async def update_user_groups(
    user_id: str,
    data: UserGroupUpdateRequest,
    current_user: UserModel = Depends(get_current_user),
):
    user = await _get_user(user_id)
    ensure_mutable_user(user)
    user.groups = await validate_group_assignment(current_user, data.groups)
    user.update_by = current_user.username
    user.update_at = utcnow()
    await user.save()
    await bump_user_authorization_versions([user.id])
    return ApiResponseSchema.success(data=UserResponse.from_doc(await _get_user(user.id)))


@router.post("/users/{user_id}/password", response_model=ApiResponseSchema[None], summary="重置用户密码")
async def reset_user_password(
    user_id: str,
    data: UserPasswordUpdateRequest,
    current_user: UserModel = Depends(get_current_user),
):
    user = await _get_user(user_id)
    ensure_mutable_user(user)
    await change_user_credentials(user, data.password, current_user.username)
    return ApiResponseSchema.success()


@router.patch("/users/{user_id}/status", response_model=ApiResponseSchema[UserResponse], summary="修改用户状态")
async def update_user_status(
    user_id: str,
    data: UserStatusUpdateRequest,
    current_user: UserModel = Depends(get_current_user),
):
    user = await _get_user(user_id)
    ensure_mutable_user(user)
    user.enabled = data.enabled
    user.update_by = current_user.username
    user.update_at = utcnow()
    await user.save()
    if not data.enabled:
        await terminate_user_sessions(user.id, reason="user_disabled")
    return ApiResponseSchema.success(data=UserResponse.from_doc(user))


@router.patch("/users/{user_id}/expiry", response_model=ApiResponseSchema[UserResponse], summary="修改用户到期约束")
async def update_user_expiry(
    user_id: str,
    data: UserExpiryUpdateRequest,
    current_user: UserModel = Depends(get_current_user),
):
    user = await _get_user(user_id)
    ensure_mutable_user(user)
    try:
        validate_temporary_account(data.temporary_account, data.expired_at)
    except ValueError as exc:
        raise BadRequestException(str(exc)) from exc
    user.temporary_account = data.temporary_account
    user.expired_at = data.expired_at
    user.update_by = current_user.username
    user.update_at = utcnow()
    await user.save()
    if user.expired_at is not None and as_utc(user.expired_at) <= utcnow():
        await terminate_user_sessions(user.id, reason="account_expired")
    return ApiResponseSchema.success(data=UserResponse.from_doc(user))


@router.patch("/users/{user_id}/assignment-scope", response_model=ApiResponseSchema[UserResponse], summary="修改管理员权限分配范围")
async def update_assignment_scope(
    user_id: str,
    data: AssignmentScopeUpdateRequest,
    current_user: UserModel = Depends(get_current_user),
):
    if not current_user.is_system:
        raise ForbiddenException("只有系统内置账号可以修改权限分配范围")
    user = await _get_user(user_id)
    ensure_mutable_user(user)
    user.restrict_permission_assignment = data.restrict_permission_assignment
    user.authorization_version += 1
    user.update_by = current_user.username
    user.update_at = utcnow()
    await user.save()
    return ApiResponseSchema.success(data=UserResponse.from_doc(user))


@router.delete("/users/{user_id}", response_model=ApiResponseSchema[None], summary="删除用户")
async def delete_user(user_id: str, current_user: UserModel = Depends(get_current_user)):
    user = await _get_user(user_id)
    ensure_mutable_user(user)
    user.is_deleted = True
    user.enabled = False
    user.update_by = current_user.username
    user.update_at = utcnow()
    await user.save()
    await terminate_user_sessions(user.id, reason="user_deleted")
    return ApiResponseSchema.success()


@router.get("/users/{user_id}/sessions", response_model=ApiResponseSchema[list[LoginSessionResponse]], summary="查看用户登录会话")
async def list_user_sessions(user_id: str, active_only: bool = True):
    await _get_user(user_id)
    query: dict[str, Any] = {"user_id": user_id}
    if active_only:
        query["status"] = "active"
    sessions = await LoginSessionModel.find(query).sort("-created_at").to_list()
    return ApiResponseSchema.success(data=[LoginSessionResponse.from_doc(item) for item in sessions])


@router.post("/users/{user_id}/sessions/terminate", response_model=ApiResponseSchema[dict[str, int]], summary="终止用户全部会话")
async def terminate_all_user_sessions(user_id: str):
    await _get_user(user_id)
    count = await terminate_user_sessions(user_id, reason="terminated_by_admin")
    return ApiResponseSchema.success(data={"terminated": count})


@router.post("/sessions/{session_id}/terminate", response_model=ApiResponseSchema[None], summary="终止具体登录会话")
async def terminate_specific_session(session_id: str):
    if not await terminate_session_by_id(session_id, reason="terminated_by_admin"):
        return ApiResponseSchema.error(code=status_codes.NOT_FOUND, message="登录会话不存在")
    return ApiResponseSchema.success()


@router.get("/groups", response_model=PageResponseSchema[GroupResponse], summary="分页获取权限组列表")
async def get_group_list(params: PageParamsSchema = Depends()):
    query = GroupModel.find({"is_deleted": False})
    total = await query.count()
    groups = await query.skip((params.page - 1) * params.page_size).limit(params.page_size).to_list()
    return PageResponseSchema.create(
        [GroupResponse.from_doc(group) for group in groups], total, params.page, params.page_size
    )


@router.get("/groups/{group_id}", response_model=ApiResponseSchema[GroupResponse], summary="获取权限组详情")
async def get_group_detail(group_id: str):
    return ApiResponseSchema.success(data=GroupResponse.from_doc(await _get_group(group_id)))


@router.post("/groups", response_model=ApiResponseSchema[GroupResponse], summary="创建权限组")
async def create_group(data: GroupCreateRequest, current_user: UserModel = Depends(get_current_user)):
    if await GroupModel.find_one({"group_name": data.group_name, "is_deleted": False}):
        return ApiResponseSchema.error(code=status_codes.CONFLICT_NAME, message="权限组标识已存在")
    permissions = await validate_permission_assignment(current_user, data.permissions)
    group = GroupModel(
        id=generate_id(data.group_name + utcnow().isoformat()),
        group_name=data.group_name,
        display_name=data.display_name,
        remark=data.remark,
        enabled=data.enabled,
        permissions=permissions,
        is_system=False,
        create_by=current_user.username,
    )
    await group.insert()
    return ApiResponseSchema.success(data=GroupResponse.from_doc(group))


@router.patch("/groups/{group_id}", response_model=ApiResponseSchema[GroupResponse], summary="更新权限组")
async def update_group(
    group_id: str,
    data: GroupUpdateRequest,
    current_user: UserModel = Depends(get_current_user),
):
    group = await _get_group(group_id)
    ensure_mutable_group(group)
    update_data = data.model_dump(exclude_unset=True)
    if "permissions" in update_data:
        update_data["permissions"] = await validate_permission_assignment(
            current_user, update_data["permissions"] or []
        )
    changed_authorization = "permissions" in update_data or "enabled" in update_data
    for key, value in update_data.items():
        setattr(group, key, value)
    group.update_by = current_user.username
    group.update_at = utcnow()
    await group.save()
    if changed_authorization:
        await bump_group_member_authorization_versions([group.id])
    return ApiResponseSchema.success(data=GroupResponse.from_doc(group))


@router.delete("/groups/{group_id}", response_model=ApiResponseSchema[None], summary="删除权限组")
async def delete_group(group_id: str, current_user: UserModel = Depends(get_current_user)):
    group = await _get_group(group_id)
    ensure_mutable_group(group)
    if await UserModel.find_one({"groups": group.id, "is_deleted": False}):
        return ApiResponseSchema.error(code=status_codes.CONFLICT_STATE, message="权限组仍被用户引用")
    group.is_deleted = True
    group.enabled = False
    group.update_by = current_user.username
    group.update_at = utcnow()
    await group.save()
    return ApiResponseSchema.success()


def _permission_query(
    category: str | None = None,
    enabled: bool | None = None,
    tags: list[str] = Query(default_factory=list),
    keyword: str | None = None,
    source: str | None = None,
) -> PermissionCodeListQuery:
    return PermissionCodeListQuery(
        category=category, enabled=enabled, tags=tags, keyword=keyword, source=source
    )


@router.get("/perm-codes", response_model=ApiResponseSchema[list[PermissionCodeResponse]], summary="获取权限字典")
async def get_permission_codes(query: PermissionCodeListQuery = Depends(_permission_query)):
    filters: dict[str, Any] = {"is_deleted": False}
    if query.category:
        filters["category"] = query.category
    if query.enabled is not None:
        filters["enabled"] = query.enabled
    if query.source:
        filters["source"] = query.source
    if query.tags:
        filters["tags"] = {"$in": query.tags}
    if query.keyword and query.keyword.strip():
        keyword = query.keyword.strip()
        filters["$or"] = [
            {"perm_key": {"$regex": keyword, "$options": "i"}},
            {"name": {"$regex": keyword, "$options": "i"}},
            {"desc": {"$regex": keyword, "$options": "i"}},
        ]
    docs = await PermissionCodeModel.find(filters).sort("category", "perm_key").to_list()
    return ApiResponseSchema.success(data=[PermissionCodeResponse.from_doc(doc) for doc in docs])


async def _create_placeholder(data: PermissionCodeCreateRequest, operator: UserModel) -> PermissionCodeModel:
    code = data.perm_key.strip()
    if not validate_placeholder_permission_code(code):
        raise BadRequestException("占位权限码格式非法、与标准权限重复或属于系统保留权限")
    if await PermissionCodeModel.find_one({"perm_key": code, "is_deleted": False}):
        raise BadRequestException(f"权限码已存在: {code}")
    parts = code.split(":")
    doc = PermissionCodeModel(
        id=generate_id(code + utcnow().isoformat()),
        perm_key=code,
        name=data.name,
        category=data.category,
        desc=data.desc,
        tags=data.tags,
        module=parts[1],
        resource=parts[2] if code.startswith("operation:") else ":".join(parts[2:-1]) or "page",
        source="placeholder",
        backend_enforced=False,
        system_reserved=False,
        delegable=True,
        default_enabled=data.enabled,
        enabled=data.enabled,
        create_by=operator.username,
    )
    await doc.insert()
    return doc


@router.post("/perm-codes", response_model=ApiResponseSchema[PermissionCodeResponse], summary="创建占位权限")
async def create_permission_code(
    data: PermissionCodeCreateRequest,
    current_user: UserModel = Depends(get_current_user),
):
    return ApiResponseSchema.success(data=PermissionCodeResponse.from_doc(await _create_placeholder(data, current_user)))


@router.post("/perm-codes/batch", response_model=ApiResponseSchema[list[PermissionCodeResponse]], summary="批量创建占位权限")
async def batch_create_permission_codes(
    data: PermissionCodeBatchCreateRequest,
    current_user: UserModel = Depends(get_current_user),
):
    if not data.items:
        raise BadRequestException("items 不能为空")
    keys = [item.perm_key.strip() for item in data.items]
    if len(keys) != len(set(keys)):
        raise BadRequestException("请求中存在重复权限码")
    invalid = [code for code in keys if not validate_placeholder_permission_code(code)]
    if invalid:
        raise BadRequestException(f"占位权限码格式非法、与标准权限重复或属于系统保留权限: {invalid[0]}")
    existing = await PermissionCodeModel.find_one(
        {"perm_key": {"$in": keys}, "is_deleted": False}
    )
    if existing is not None:
        raise BadRequestException(f"权限码已存在: {existing.perm_key}")
    docs = [await _create_placeholder(item, current_user) for item in data.items]
    return ApiResponseSchema.success(data=[PermissionCodeResponse.from_doc(doc) for doc in docs])


@router.get("/perm-codes/{perm_code_id}/impact", response_model=ApiResponseSchema[PermissionImpactResponse], summary="查看权限影响范围")
async def permission_impact(perm_code_id: str):
    doc = await _get_permission(perm_code_id)
    groups, users = await get_permission_impact(doc.perm_key)
    return ApiResponseSchema.success(
        data=PermissionImpactResponse(
            group_ids=groups,
            user_ids=users,
            group_count=len(groups),
            user_count=len(users),
        )
    )


@router.patch("/perm-codes/{perm_code_id}", response_model=ApiResponseSchema[PermissionCodeResponse], summary="更新权限元数据或状态")
async def update_permission_code(
    perm_code_id: str,
    data: PermissionCodeUpdateRequest,
    current_user: UserModel = Depends(get_current_user),
):
    doc = await _get_permission(perm_code_id)
    if doc.system_reserved:
        raise ForbiddenException("系统保留权限不可修改")
    update_data = data.model_dump(exclude_unset=True, exclude={"impact_acknowledged"})
    if doc.source == "standard":
        update_data = {key: value for key, value in update_data.items() if key == "enabled"}
    disabling = update_data.get("enabled") is False and doc.enabled
    groups, users = await get_permission_impact(doc.perm_key) if disabling else ([], [])
    if disabling and groups and not data.impact_acknowledged:
        return ApiResponseSchema.error(
            code=status_codes.CONFLICT_STATE,
            message="权限仍被引用，禁用前必须确认影响范围",
            data={"group_ids": groups, "user_ids": users},
        )
    for key, value in update_data.items():
        setattr(doc, key, value)
    doc.update_by = current_user.username
    doc.update_at = utcnow()
    await doc.save()
    if disabling:
        await bump_user_authorization_versions(users)
    return ApiResponseSchema.success(data=PermissionCodeResponse.from_doc(doc))


@router.delete("/perm-codes/{perm_code_id}", response_model=ApiResponseSchema[None], summary="删除未引用占位权限")
async def delete_permission_code(
    perm_code_id: str,
    current_user: UserModel = Depends(get_current_user),
):
    doc = await _get_permission(perm_code_id)
    if doc.source != "placeholder" or doc.system_reserved:
        raise ForbiddenException("标准权限和系统保留权限不可删除")
    groups, _ = await get_permission_impact(doc.perm_key)
    if groups:
        return ApiResponseSchema.error(code=status_codes.CONFLICT_STATE, message="权限仍被权限组引用")
    doc.is_deleted = True
    doc.enabled = False
    doc.update_by = current_user.username
    doc.update_at = utcnow()
    await doc.save()
    return ApiResponseSchema.success()


@router.post("/perm-codes/{perm_code_id}/migrate", response_model=ApiResponseSchema[PermissionImpactResponse], summary="迁移权限引用")
async def migrate_permission_code(
    perm_code_id: str,
    data: PermissionCodeMigrationRequest,
    current_user: UserModel = Depends(get_current_user),
):
    source = await _get_permission(perm_code_id)
    if source.system_reserved:
        raise ForbiddenException("系统保留权限不可迁移")
    if data.remove_source and source.source != "placeholder":
        raise BadRequestException("标准权限迁移后不能从字典删除")
    target = await PermissionCodeModel.find_one(
        {"perm_key": data.target_perm_key, "enabled": True, "is_deleted": False}
    )
    if target is None or target.system_reserved:
        raise BadRequestException("目标权限不存在、未启用或属于系统保留权限")
    await validate_permission_assignment(current_user, [target.perm_key])
    groups = await GroupModel.find({"permissions": source.perm_key, "is_deleted": False}).to_list()
    for group in groups:
        ensure_mutable_group(group)
        group.permissions = list(
            dict.fromkeys(target.perm_key if code == source.perm_key else code for code in group.permissions)
        )
        group.update_by = current_user.username
        group.update_at = utcnow()
        await group.save()
    _, users = await get_permission_impact(target.perm_key)
    await bump_user_authorization_versions(users)
    if data.remove_source:
        source.is_deleted = True
        source.enabled = False
        source.update_by = current_user.username
        source.update_at = utcnow()
        await source.save()
    return ApiResponseSchema.success(
        data=PermissionImpactResponse(
            group_ids=[group.id for group in groups],
            user_ids=users,
            group_count=len(groups),
            user_count=len(users),
        )
    )


@router.post("/perm-codes/{perm_code_id}/cleanup", response_model=ApiResponseSchema[PermissionImpactResponse], summary="清理权限引用")
async def cleanup_permission_code(
    perm_code_id: str,
    current_user: UserModel = Depends(get_current_user),
):
    doc = await _get_permission(perm_code_id)
    if doc.system_reserved:
        raise ForbiddenException("系统保留权限不可清理")
    groups = await GroupModel.find({"permissions": doc.perm_key, "is_deleted": False}).to_list()
    _, users = await get_permission_impact(doc.perm_key)
    for group in groups:
        ensure_mutable_group(group)
        group.permissions = [code for code in group.permissions if code != doc.perm_key]
        group.update_by = current_user.username
        group.update_at = utcnow()
        await group.save()
    await bump_user_authorization_versions(users)
    doc.enabled = False
    if doc.source == "placeholder":
        doc.is_deleted = True
    doc.update_by = current_user.username
    doc.update_at = utcnow()
    await doc.save()
    return ApiResponseSchema.success(
        data=PermissionImpactResponse(
            group_ids=[group.id for group in groups],
            user_ids=users,
            group_count=len(groups),
            user_count=len(users),
        )
    )
