from datetime import datetime

from fastapi import APIRouter, Depends, Query

import app.utils.status_codes as status_codes
from app.core.permissions import SystemPerms
from app.core.security import hash_password
from app.dependencies.auth import get_current_user, require_permissions
from app.models.auth.group import GroupModel
from app.models.auth.permission_code import PermissionCodeModel
from app.models.auth.user import UserModel
from app.schemas.auth.group import GroupCreateRequest, GroupResponse, GroupUpdateRequest
from app.schemas.auth.permission_code import (
    PermissionCodeBatchCreateRequest,
    PermissionCodeCreateRequest,
    PermissionCodeListQuery,
    PermissionCodeResponse,
    PermissionCodeUpdateRequest,
)
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

def _get_permission_code_list_query(
    category: str | None = None,
    enabled: bool | None = None,
    tags: list[str] = Query(default_factory=list),
    keyword: str | None = None,
) -> PermissionCodeListQuery:
    return PermissionCodeListQuery(category=category, enabled=enabled, tags=tags, keyword=keyword)


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


@router.get(
    "/perm-codes",
    response_model=ApiResponseSchema[list[PermissionCodeResponse]],
    summary="获取权限码列表（不分页）",
)
async def get_permission_code_list(
    query: PermissionCodeListQuery = Depends(_get_permission_code_list_query),
    _: UserModel = Depends(get_current_user),
    __: None = Depends(require_permissions([SystemPerms.PERMCODE_VIEW])),
):
    filters: dict = {"is_deleted": False}
    if query.category:
        filters["category"] = query.category
    if query.enabled is not None:
        filters["enabled"] = query.enabled
    if query.tags:
        filters["tags"] = {"$in": query.tags}
    if query.keyword:
        kw = query.keyword.strip()
        if kw:
            filters["$or"] = [
                {"perm_key": {"$regex": kw, "$options": "i"}},
                {"name": {"$regex": kw, "$options": "i"}},
                {"desc": {"$regex": kw, "$options": "i"}},
            ]

    docs = await PermissionCodeModel.find(filters).sort("category", "perm_key").to_list()
    items = [PermissionCodeResponse.from_doc(doc) for doc in docs]
    return ApiResponseSchema.success(data=items)


@router.post(
    "/perm-codes",
    response_model=ApiResponseSchema[PermissionCodeResponse],
    summary="创建权限码",
)
async def create_permission_code(
    data: PermissionCodeCreateRequest,
    current_user: UserModel = Depends(get_current_user),
    _: None = Depends(require_permissions([SystemPerms.PERMCODE_CREATE])),
):
    perm_key = (data.perm_key or "").strip()
    if not perm_key:
        return ApiResponseSchema.error(code=status_codes.INVALID_ARGUMENT, message="perm_key 不能为空")

    existing = await PermissionCodeModel.find_one({"perm_key": perm_key, "is_deleted": False})
    if existing:
        return ApiResponseSchema.error(code=status_codes.CONFLICT_EXISTS, message=f"权限码已存在: {perm_key}")

    doc = PermissionCodeModel(
        id=generate_id(perm_key + datetime.now().isoformat()),
        perm_key=perm_key,
        name=data.name,
        category=data.category,
        desc=data.desc,
        tags=data.tags,
        enabled=data.enabled,
        create_by=current_user.username,
    )
    await doc.insert()
    return ApiResponseSchema.success(data=PermissionCodeResponse.from_doc(doc))


@router.post(
    "/perm-codes/batch",
    response_model=ApiResponseSchema[list[PermissionCodeResponse]],
    summary="批量创建权限码",
)
async def batch_create_permission_codes(
    data: PermissionCodeBatchCreateRequest,
    current_user: UserModel = Depends(get_current_user),
    _: None = Depends(require_permissions([SystemPerms.PERMCODE_CREATE])),
):
    if not data.items:
        return ApiResponseSchema.error(code=status_codes.INVALID_ARGUMENT, message="items 不能为空")

    normalized_keys: list[str] = []
    seen_keys: set[str] = set()
    for item in data.items:
        perm_key = (item.perm_key or "").strip()
        if not perm_key:
            return ApiResponseSchema.error(code=status_codes.INVALID_ARGUMENT, message="perm_key 不能为空")
        if perm_key in seen_keys:
            return ApiResponseSchema.error(code=status_codes.CONFLICT_EXISTS, message=f"请求中存在重复权限码: {perm_key}")
        seen_keys.add(perm_key)
        normalized_keys.append(perm_key)

    existing_docs = await PermissionCodeModel.find(
        {"perm_key": {"$in": normalized_keys}, "is_deleted": False}
    ).to_list()
    if existing_docs:
        existing_key = existing_docs[0].perm_key
        return ApiResponseSchema.error(code=status_codes.CONFLICT_EXISTS, message=f"权限码已存在: {existing_key}")

    docs: list[PermissionCodeModel] = []
    for item, perm_key in zip(data.items, normalized_keys):
        docs.append(
            PermissionCodeModel(
                id=generate_id(perm_key + datetime.now().isoformat()),
                perm_key=perm_key,
                name=item.name,
                category=item.category,
                desc=item.desc,
                tags=item.tags,
                enabled=item.enabled,
                create_by=current_user.username,
            )
        )
    await PermissionCodeModel.insert_many(docs)
    return ApiResponseSchema.success(data=[PermissionCodeResponse.from_doc(doc) for doc in docs])


@router.put(
    "/perm-codes/{perm_code_id}",
    response_model=ApiResponseSchema[PermissionCodeResponse],
    summary="更新权限码",
)
async def update_permission_code(
    perm_code_id: str,
    data: PermissionCodeUpdateRequest,
    current_user: UserModel = Depends(get_current_user),
    _: None = Depends(require_permissions([SystemPerms.PERMCODE_EDIT])),
):
    doc = await PermissionCodeModel.find_one({"_id": perm_code_id, "is_deleted": False})
    if not doc:
        return ApiResponseSchema.error(code=status_codes.NOT_FOUND, message=f"权限码不存在，ID: {perm_code_id}")

    update_data = data.model_dump(exclude_unset=True)
    if "perm_key" in update_data and update_data["perm_key"] is not None:
        new_key = (update_data["perm_key"] or "").strip()
        if not new_key:
            return ApiResponseSchema.error(code=status_codes.INVALID_ARGUMENT, message="perm_key 不能为空")
        if new_key != doc.perm_key:
            exists = await PermissionCodeModel.find_one(
                {"perm_key": new_key, "is_deleted": False, "_id": {"$ne": doc.id}}
            )
            if exists:
                return ApiResponseSchema.error(code=status_codes.CONFLICT_EXISTS, message=f"权限码已存在: {new_key}")
        update_data["perm_key"] = new_key

    for key, value in update_data.items():
        setattr(doc, key, value)
    doc.update_by = current_user.username
    doc.update_at = datetime.now()
    await doc.save()
    return ApiResponseSchema.success(data=PermissionCodeResponse.from_doc(doc))


@router.delete(
    "/perm-codes/{perm_code_id}",
    response_model=ApiResponseSchema[None],
    summary="删除权限码（软删除）",
)
async def delete_permission_code(
    perm_code_id: str,
    current_user: UserModel = Depends(get_current_user),
    _: None = Depends(require_permissions([SystemPerms.PERMCODE_DELETE])),
):
    doc = await PermissionCodeModel.find_one({"_id": perm_code_id, "is_deleted": False})
    if not doc:
        return ApiResponseSchema.error(code=status_codes.NOT_FOUND, message=f"权限码不存在，ID: {perm_code_id}")
    doc.is_deleted = True
    doc.update_by = current_user.username
    doc.update_at = datetime.now()
    await doc.save()
    return ApiResponseSchema.success()
