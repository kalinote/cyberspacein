from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

import yaml
from fastapi import Request, Security
from fastapi.routing import APIRoute
from fastapi.security import HTTPAuthorizationCredentials

from app.core.config import settings
from app.core.exceptions import ForbiddenException, InternalServerException
from app.core.permissions import PERMISSION_REGISTRY
from app.dependencies.auth import (
    _bearer_scheme,
    get_component_context,
    get_current_auth_context,
)
from app.service.auth import has_backend_permissions
from app.service.component_auth import consume_component_bootstrap
from app.models.action.action import ActionInstanceNodeModel
from app.models.action.component_run import ComponentRunModel


_MATRIX_FILE = Path(__file__).with_name("route_permissions.yml")
_ALLOWED_METHODS = {"GET", "POST", "PUT", "PATCH", "DELETE", "WEBSOCKET"}
_PUBLIC_ROUTES = {("POST", "/auth/login")}
_AUTHENTICATED_WITHOUT_OPERATION = {
    ("POST", "/auth/logout"),
    ("GET", "/auth/me"),
}


@dataclass(frozen=True, slots=True)
class RoutePermission:
    method: str
    path: str
    principal: str
    permission: str | None = None
    scope: str | None = None


def normalize_api_path(path: str) -> str:
    api_prefix = settings.API_V1_STR.rstrip("/")
    if path == api_prefix:
        return "/"
    if path.startswith(f"{api_prefix}/"):
        return path[len(api_prefix) :]
    return path


def _load_route_matrix() -> tuple[str, tuple[RoutePermission, ...]]:
    raw = yaml.safe_load(_MATRIX_FILE.read_bytes())
    if not isinstance(raw, dict) or not isinstance(raw.get("routes"), list):
        raise RuntimeError("route_permissions.yml 必须包含 routes 列表")
    version = str(raw.get("version") or "").strip()
    if not version:
        raise RuntimeError("route_permissions.yml 缺少 version")
    entries: list[RoutePermission] = []
    seen: set[tuple[str, str]] = set()
    for item in raw["routes"]:
        if not isinstance(item, dict):
            raise RuntimeError("路由矩阵条目必须是对象")
        method = str(item.get("method") or "").upper()
        path = str(item.get("path") or "").strip()
        principal = str(item.get("principal") or "").strip()
        permission = item.get("permission")
        scope = item.get("scope")
        if method not in _ALLOWED_METHODS or not path.startswith("/"):
            raise RuntimeError(f"非法路由矩阵条目: {method} {path}")
        if principal not in {"public", "user", "component", "component_bootstrap"}:
            raise RuntimeError(f"非法路由主体: {principal}")
        key = (method, path)
        if key in seen:
            raise RuntimeError(f"重复路由矩阵条目: {method} {path}")
        seen.add(key)
        if principal == "user" and permission is not None:
            definition = PERMISSION_REGISTRY.get(str(permission))
            if definition is None or not definition.backend_enforced:
                raise RuntimeError(f"路由引用了非后端标准权限: {method} {path} -> {permission}")
        if principal == "user" and permission is None and key not in _AUTHENTICATED_WITHOUT_OPERATION:
            raise RuntimeError(f"业务用户路由缺少 operation 权限: {method} {path}")
        if principal == "component" and not isinstance(scope, str):
            raise RuntimeError(f"Component 路由缺少 scope: {method} {path}")
        if principal in {"public", "component_bootstrap"} and (permission is not None or scope is not None):
            raise RuntimeError(f"公开路由不能声明权限或 scope: {method} {path}")
        if principal == "public" and key not in _PUBLIC_ROUTES:
            raise RuntimeError(f"未批准的公开业务路由: {method} {path}")
        entries.append(
            RoutePermission(
                method=method,
                path=path,
                principal=principal,
                permission=str(permission) if permission is not None else None,
                scope=str(scope) if scope is not None else None,
            )
        )
    return version, tuple(entries)


ROUTE_MATRIX_VERSION, ROUTE_PERMISSIONS = _load_route_matrix()
ROUTE_PERMISSION_MAP = {(item.method, item.path): item for item in ROUTE_PERMISSIONS}


def _registered_route_key(request: Request) -> tuple[str, str]:
    route = request.scope.get("route")
    path = getattr(route, "path", request.url.path)
    return request.method.upper(), normalize_api_path(path)


async def authorize_registered_route(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Security(_bearer_scheme),
) -> None:
    key = _registered_route_key(request)
    rule = ROUTE_PERMISSION_MAP.get(key)
    if rule is None:
        raise InternalServerException(f"接口未登记权限矩阵: {key[0]} {key[1]}")
    if rule.principal == "public":
        return
    if rule.principal == "component_bootstrap":
        component_run_id = str(request.path_params.get("component_run_id") or "")
        context = await consume_component_bootstrap(
            request.headers.get("x-component-bootstrap", ""), component_run_id
        )
        component_run = await ComponentRunModel.find_one(
            {
                "_id": component_run_id,
                "action_id": context.action_id,
                "node_instance_id": context.node_instance_id,
            }
        )
        status = getattr(
            getattr(component_run, "status", None),
            "value",
            getattr(component_run, "status", None),
        )
        if component_run is None or status not in {"dispatched", "running"}:
            raise ForbiddenException("组件运行实例已不处于可调用状态")
        request.state.component_bootstrap_context = context
        return
    if rule.principal == "component":
        context = await get_component_context(request, credentials)
        if rule.scope not in context.scopes:
            raise ForbiddenException("组件凭证缺少所需调用范围")
        return
    context = await get_current_auth_context(request, credentials)
    if rule.permission and not await has_backend_permissions(
        context.user, [rule.permission]
    ):
        raise ForbiddenException("当前账号无权限访问该资源")


def validate_fastapi_routes(routes: Iterable[Any]) -> None:
    actual: set[tuple[str, str]] = set()
    for route in routes:
        if not isinstance(route, APIRoute):
            continue
        if not route.path.startswith(settings.API_V1_STR.rstrip("/") + "/"):
            continue
        for method in route.methods or set():
            normalized_method = method.upper()
            if normalized_method in {"HEAD", "OPTIONS"}:
                continue
            actual.add((normalized_method, normalize_api_path(route.path)))
    declared = set(ROUTE_PERMISSION_MAP)
    missing = sorted(actual - declared)
    unused = sorted(declared - actual)
    if missing or unused:
        details: list[str] = []
        if missing:
            details.append("未登记=" + ", ".join(f"{m} {p}" for m, p in missing))
        if unused:
            details.append("无对应路由=" + ", ".join(f"{m} {p}" for m, p in unused))
        raise RuntimeError("接口权限矩阵与实际路由不一致: " + "; ".join(details))
