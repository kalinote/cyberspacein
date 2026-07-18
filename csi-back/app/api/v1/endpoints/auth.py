from fastapi import APIRouter, Depends, Request

import app.utils.status_codes as status_codes
from app.dependencies.auth import get_current_auth_context
from app.schemas.auth.auth import CurrentUserResponse, LoginRequest, LoginResponse
from app.schemas.auth.user import UserResponse
from app.schemas.response import ApiResponseSchema
from app.service.auth import authenticate_user, get_user_permissions
from app.service.auth_session import AuthContext, terminate_session

router = APIRouter(prefix="/auth", tags=["认证鉴权"])


@router.post("/login", response_model=ApiResponseSchema[LoginResponse], summary="用户登录")
async def login(data: LoginRequest, request: Request):
    client_ip = request.client.host if request.client else None
    result = await authenticate_user(
        data.username,
        data.password,
        client_ip,
        request.headers.get("user-agent"),
    )
    if result is None:
        return ApiResponseSchema.error(
            code=status_codes.UNAUTHORIZED,
            message="用户名或密码错误，或账号暂时不可用",
        )
    token, user, permissions, session = result
    return ApiResponseSchema.success(
        data=LoginResponse(
            access_token=token,
            token_type="bearer",
            user=UserResponse.from_doc(user),
            permissions=permissions,
            authorization_version=user.authorization_version,
            session_id=session.id,
            session_expires_at=session.expires_at,
        )
    )


@router.post("/logout", response_model=ApiResponseSchema[None], summary="退出登录")
async def logout(context: AuthContext = Depends(get_current_auth_context)):
    await terminate_session(context.session, reason="user_logout")
    return ApiResponseSchema.success()


@router.get("/me", response_model=ApiResponseSchema[CurrentUserResponse], summary="获取当前登录用户")
async def me(context: AuthContext = Depends(get_current_auth_context)):
    permissions = await get_user_permissions(context.user)
    return ApiResponseSchema.success(
        data=CurrentUserResponse(
            user=UserResponse.from_doc(context.user),
            permissions=permissions,
            authorization_version=context.user.authorization_version,
            session_id=context.session.id,
            session_expires_at=context.session.expires_at,
        )
    )
