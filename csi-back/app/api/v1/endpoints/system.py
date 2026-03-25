from datetime import datetime

from fastapi import APIRouter, Depends

import app.utils.status_codes as status_codes
from app.core.permissions import SystemPerms
from app.core.security import hash_password
from app.dependencies.auth import get_current_user, require_permissions
from app.models.auth.group import GroupModel
from app.models.auth.user import UserModel
from app.schemas.auth.group import GroupCreateRequest, GroupResponse, GroupUpdateRequest
from app.schemas.auth.user import (
    UserCreateRequest,
    UserResponse,
    UserStatusUpdateRequest,
    UserUpdateRequest,
)
from app.schemas.general import PageParamsSchema, PageResponseSchema
from app.schemas.response import ApiResponseSchema
from app.service.auth import create_user, validate_group_ids
from app.utils.id_lib import generate_id

router = APIRouter(prefix="/system", tags=["系统用户与权限"])


@router.get("/users", response_model=PageResponseSchema[UserResponse], summary="分页获取用户列表")
async def get_user_list(
    params: PageParamsSchema = Depends(),
    _: UserModel = Depends(get_current_user),
    __: None = Depends(require_permissions([SystemPerms.USER_VIEW])),
):
    query = UserModel.find({"is_deleted": False})
    total = await query.count()
    users = await query.skip((params.page - 1) * params.page_size).limit(params.page_size).to_list()
    items = [UserResponse.from_doc(user) for user in users]
    return PageResponseSchema.create(items, total, params.page, params.page_size)


@router.post("/users", response_model=ApiResponseSchema[UserResponse], summary="创建用户")
async def create_system_user(
    data: UserCreateRequest,
    current_user: UserModel = Depends(get_current_user),
    _: None = Depends(require_permissions([SystemPerms.USER_CREATE])),
):
    if not await validate_group_ids(data.groups):
        return ApiResponseSchema.error(code=status_codes.INVALID_ARGUMENT, message="用户组不存在或未启用")
    user = await create_user(data, operator=current_user.username)
    if user is None:
        return ApiResponseSchema.error(code=status_codes.CONFLICT_EXISTS, message="用户名或邮箱已存在")
    return ApiResponseSchema.success(data=UserResponse.from_doc(user))


@router.put("/users/{user_id}", response_model=ApiResponseSchema[UserResponse], summary="更新用户")
async def update_system_user(
    user_id: str,
    data: UserUpdateRequest,
    current_user: UserModel = Depends(get_current_user),
    _: None = Depends(require_permissions([SystemPerms.USER_EDIT])),
):
    user = await UserModel.find_one({"_id": user_id, "is_deleted": False})
    if not user:
        return ApiResponseSchema.error(code=status_codes.NOT_FOUND, message=f"用户不存在，ID: {user_id}")

    update_data = data.model_dump(exclude_unset=True)
    if "groups" in update_data and update_data["groups"] is not None:
        if not await validate_group_ids(update_data["groups"]):
            return ApiResponseSchema.error(code=status_codes.INVALID_ARGUMENT, message="用户组不存在或未启用")
    if "password" in update_data:
        raw_password = update_data.pop("password")
        if raw_password:
            update_data["password_hash"] = hash_password(raw_password)

    for key, value in update_data.items():
        setattr(user, key, value)
    user.update_by = current_user.username
    user.update_at = datetime.now()
    await user.save()
    return ApiResponseSchema.success(data=UserResponse.from_doc(user))


@router.patch("/users/{user_id}/status", response_model=ApiResponseSchema[UserResponse], summary="修改用户状态")
async def update_system_user_status(
    user_id: str,
    data: UserStatusUpdateRequest,
    current_user: UserModel = Depends(get_current_user),
    _: None = Depends(require_permissions([SystemPerms.USER_DISABLE])),
):
    user = await UserModel.find_one({"_id": user_id, "is_deleted": False})
    if not user:
        return ApiResponseSchema.error(code=status_codes.NOT_FOUND, message=f"用户不存在，ID: {user_id}")
    user.enabled = data.enabled
    user.update_by = current_user.username
    user.update_at = datetime.now()
    await user.save()
    return ApiResponseSchema.success(data=UserResponse.from_doc(user))


@router.get("/groups", response_model=PageResponseSchema[GroupResponse], summary="分页获取用户组列表")
async def get_group_list(
    params: PageParamsSchema = Depends(),
    _: UserModel = Depends(get_current_user),
    __: None = Depends(require_permissions([SystemPerms.GROUP_VIEW])),
):
    query = GroupModel.find({"is_deleted": False})
    total = await query.count()
    groups = await query.skip((params.page - 1) * params.page_size).limit(params.page_size).to_list()
    items = [GroupResponse.from_doc(group) for group in groups]
    return PageResponseSchema.create(items, total, params.page, params.page_size)


@router.post("/groups", response_model=ApiResponseSchema[GroupResponse], summary="创建用户组")
async def create_group(
    data: GroupCreateRequest,
    current_user: UserModel = Depends(get_current_user),
    _: None = Depends(require_permissions([SystemPerms.GROUP_CREATE])),
):
    existing = await GroupModel.find_one({"group_name": data.group_name, "is_deleted": False})
    if existing:
        return ApiResponseSchema.error(code=status_codes.CONFLICT_NAME, message=f"用户组名称已存在: {data.group_name}")

    group = GroupModel(
        id=generate_id(data.group_name + datetime.now().isoformat()),
        group_name=data.group_name,
        display_name=data.display_name,
        remark=data.remark,
        enabled=data.enabled,
        permissions=data.permissions,
        create_by=current_user.username,
    )
    await group.insert()
    return ApiResponseSchema.success(data=GroupResponse.from_doc(group))


@router.put("/groups/{group_id}", response_model=ApiResponseSchema[GroupResponse], summary="更新用户组")
async def update_group(
    group_id: str,
    data: GroupUpdateRequest,
    current_user: UserModel = Depends(get_current_user),
    _: None = Depends(require_permissions([SystemPerms.GROUP_EDIT])),
):
    group = await GroupModel.find_one({"_id": group_id, "is_deleted": False})
    if not group:
        return ApiResponseSchema.error(code=status_codes.NOT_FOUND, message=f"用户组不存在，ID: {group_id}")

    update_data = data.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(group, key, value)
    group.update_by = current_user.username
    group.update_at = datetime.now()
    await group.save()
    return ApiResponseSchema.success(data=GroupResponse.from_doc(group))
