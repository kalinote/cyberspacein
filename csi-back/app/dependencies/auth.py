from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from fastapi import Depends, Request, Security
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.core.exceptions import ForbiddenException, UnauthorizedException
from app.core.security import decode_component_token
from app.models.action.action import ActionInstanceNodeModel
from app.models.action.component_run import ComponentRunModel
from app.models.auth.user import UserModel
from app.service.auth import has_backend_permissions
from app.service.auth_session import AuthContext, authenticate_access_token


_bearer_scheme = HTTPBearer(auto_error=False)


def _extract_bearer(credentials: HTTPAuthorizationCredentials | None) -> str:
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise UnauthorizedException("未登录或登录状态无效")
    token = (credentials.credentials or "").strip()
    if not token:
        raise UnauthorizedException("未登录或登录状态无效")
    return token


async def get_current_auth_context(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Security(_bearer_scheme),
) -> AuthContext:
    cached = getattr(request.state, "auth_context", None)
    if isinstance(cached, AuthContext):
        return cached
    context = await authenticate_access_token(_extract_bearer(credentials))
    request.state.auth_context = context
    request.state.authorization_version = context.user.authorization_version
    return context


async def get_current_user(
    context: AuthContext = Depends(get_current_auth_context),
) -> UserModel:
    return context.user


def require_permissions(required_permissions: list[str]):
    """Reusable explicit guard for non-matrix subrouters and isolated handlers."""
    required = list(dict.fromkeys(required_permissions))

    async def _checker(user: UserModel = Depends(get_current_user)):
        if not await has_backend_permissions(user, required):
            raise ForbiddenException("当前账号无权限访问该资源")

    return _checker


@dataclass(slots=True)
class ComponentContext:
    action_id: str
    node_instance_id: str
    component_run_id: str
    scopes: frozenset[str]
    claims: dict[str, Any]


async def get_component_context(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Security(_bearer_scheme),
) -> ComponentContext:
    cached = getattr(request.state, "component_context", None)
    if isinstance(cached, ComponentContext):
        return cached
    token = _extract_bearer(credentials)
    claims = decode_component_token(token)
    if claims is None:
        raise UnauthorizedException("组件凭证无效或已过期")
    node_instance_id = str(claims["node_id"])
    action_id = str(claims["action_id"])
    component_run_id = str(claims["component_run_id"])
    requested_run_id = str(request.path_params.get("component_run_id") or "")
    if requested_run_id != component_run_id:
        raise ForbiddenException("组件凭证不能跨运行实例使用")
    node = await ActionInstanceNodeModel.find_one(
        {"_id": node_instance_id, "action_id": action_id}
    )
    if node is None:
        raise UnauthorizedException("组件凭证绑定的节点不存在")
    component_run = await ComponentRunModel.find_one(
        {
            "_id": component_run_id,
            "node_instance_id": node_instance_id,
            "action_id": action_id,
        }
    )
    if component_run is None:
        raise UnauthorizedException("组件凭证绑定的运行实例不存在")
    status = getattr(component_run.status, "value", component_run.status)
    if status not in {
        "dispatched",
        "running",
        "succeeded",
        "failed",
        "cancelled",
        "timed_out",
    }:
        raise UnauthorizedException("组件运行实例已不处于可调用状态")
    context = ComponentContext(
        action_id=action_id,
        node_instance_id=node_instance_id,
        component_run_id=component_run_id,
        scopes=frozenset(claims["scope"]),
        claims=claims,
    )
    request.state.component_context = context
    return context


def require_component_scope(scope: str):
    async def _checker(
        context: ComponentContext = Depends(get_component_context),
    ) -> ComponentContext:
        if scope not in context.scopes:
            raise ForbiddenException("组件凭证缺少所需调用范围")
        return context

    return _checker
