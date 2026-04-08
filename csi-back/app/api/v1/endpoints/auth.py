from fastapi import APIRouter, Depends, Request

import app.utils.status_codes as status_codes
from app.dependencies.auth import get_current_user
from app.models.auth.user import UserModel
from app.schemas.auth.auth import CurrentUserResponse, LoginRequest, LoginResponse
from app.schemas.auth.user import UserResponse
from app.schemas.response import ApiResponseSchema
from app.service.auth import authenticate_user, get_user_permissions

router = APIRouter(prefix="/auth", tags=["认证鉴权"])


@router.post("/login", response_model=ApiResponseSchema[LoginResponse], summary="用户登录")
async def login(data: LoginRequest, request: Request):
    client_ip = request.client.host if request.client else None
    result = await authenticate_user(data.username, data.password, client_ip)
    if result is None:
        return ApiResponseSchema.error(code=status_codes.UNAUTHORIZED, message="用户名或密码错误，或账号不可用")

    token, user, permissions = result
    return ApiResponseSchema.success(
        data=LoginResponse(
            access_token=token,
            token_type="bearer",
            user=UserResponse.from_doc(user),
            permissions=permissions,
        )
    )


@router.post("/logout", response_model=ApiResponseSchema[None], summary="退出登录")
async def logout(_: UserModel = Depends(get_current_user)):
    return ApiResponseSchema.success()


@router.get("/me", response_model=ApiResponseSchema[CurrentUserResponse], summary="获取当前登录用户")
async def me(current_user: UserModel = Depends(get_current_user)):
    permissions = await get_user_permissions(current_user)
    return ApiResponseSchema.success(
        data=CurrentUserResponse(
            user=UserResponse.from_doc(current_user),
            permissions=permissions,
        )
    )
