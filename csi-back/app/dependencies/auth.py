from fastapi import Depends, Security
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.core.exceptions import ForbiddenException, UnauthorizedException
from app.core.security import decode_access_token
from app.models.auth.user import UserModel
from app.service.auth import get_user_permissions


_bearer_scheme = HTTPBearer(auto_error=False)


async def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Security(_bearer_scheme),
) -> UserModel:
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise UnauthorizedException("未登录或登录状态无效")

    token = (credentials.credentials or "").strip()
    if not token:
        raise UnauthorizedException("未登录或登录状态无效")
    payload = decode_access_token(token)
    if payload is None:
        raise UnauthorizedException("登录已失效，请重新登录")

    user_id = payload.get("sub")
    if not user_id:
        raise UnauthorizedException("登录状态无效")

    user = await UserModel.find_one({"_id": user_id, "is_deleted": False})
    if not user or not user.enabled:
        raise UnauthorizedException("用户不可用")
    return user


def require_permissions(required_permissions: list[str]):
    async def _checker(user: UserModel = Depends(get_current_user)):
        current_permissions = await get_user_permissions(user)
        if "*" in current_permissions:
            return
        if not all(code in current_permissions for code in required_permissions):
            raise ForbiddenException("当前账号无权限访问该资源")

    return _checker
