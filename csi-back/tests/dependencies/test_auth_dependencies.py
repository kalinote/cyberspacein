"""app.dependencies.auth 鉴权依赖测试。"""

from unittest.mock import AsyncMock

import pytest
from fastapi import Depends, FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.security import HTTPAuthorizationCredentials
from starlette.testclient import TestClient

import app.utils.status_codes as status_codes
from app.core.exceptions import ApiException, UnauthorizedException
from app.dependencies.auth import get_current_user, require_permissions
from app.models.auth.user import UserModel
from app.schemas.response import ApiResponseSchema


def _api_exception_handler(request: Request, exc: ApiException) -> JSONResponse:
    return JSONResponse(
        status_code=200,
        content=ApiResponseSchema.error(
            code=exc.code,
            message=exc.message,
            data=exc.data,
        ).model_dump(),
    )


def _sample_user(**overrides) -> UserModel:
    # Beanie Document 在未 init_beanie 时不可用 __init__，使用 model_construct 构造内存对象
    data = {
        "id": "user-id-1",
        "username": "alice",
        "display_name": "Alice",
        "password_hash": "pbkdf2_sha256$120000$s$s",
        "enabled": True,
    }
    data.update(overrides)
    return UserModel.model_construct(**data)


def _client_with_guarded_route(required: list[str]):
    app = FastAPI()
    app.add_exception_handler(ApiException, _api_exception_handler)

    @app.get("/guard")
    async def guarded(_: None = Depends(require_permissions(required))):
        return {"ok": True}

    return TestClient(app)


@pytest.mark.asyncio
async def test_get_current_user_no_credentials():
    # 无 Authorization 时应拒绝
    with pytest.raises(UnauthorizedException, match="未登录"):
        await get_current_user(None)


@pytest.mark.asyncio
async def test_get_current_user_non_bearer_scheme():
    # 非 Bearer 方案应拒绝
    creds = HTTPAuthorizationCredentials(scheme="Basic", credentials="dGVzdA==")
    with pytest.raises(UnauthorizedException, match="未登录"):
        await get_current_user(creds)


@pytest.mark.asyncio
async def test_get_current_user_empty_token(monkeypatch: pytest.MonkeyPatch) -> None:
    # Bearer 但 token 为空或仅空白应拒绝
    monkeypatch.setattr(
        "app.dependencies.auth.decode_access_token",
        lambda t: {"sub": "x"},
    )
    creds = HTTPAuthorizationCredentials(scheme="Bearer", credentials="   ")
    with pytest.raises(UnauthorizedException, match="未登录"):
        await get_current_user(creds)


@pytest.mark.asyncio
async def test_get_current_user_decode_fails(monkeypatch: pytest.MonkeyPatch) -> None:
    # 令牌无法解析时应拒绝
    monkeypatch.setattr("app.dependencies.auth.decode_access_token", lambda t: None)
    creds = HTTPAuthorizationCredentials(scheme="Bearer", credentials="any")
    with pytest.raises(UnauthorizedException, match="登录已失效"):
        await get_current_user(creds)


@pytest.mark.asyncio
async def test_get_current_user_missing_sub(monkeypatch: pytest.MonkeyPatch) -> None:
    # payload 无 sub 时应拒绝
    monkeypatch.setattr(
        "app.dependencies.auth.decode_access_token",
        lambda t: {"exp": 9999999999},
    )
    creds = HTTPAuthorizationCredentials(scheme="Bearer", credentials="tok")
    with pytest.raises(UnauthorizedException, match="登录状态无效"):
        await get_current_user(creds)


@pytest.mark.asyncio
async def test_get_current_user_empty_sub(monkeypatch: pytest.MonkeyPatch) -> None:
    # sub 为空字符串应拒绝
    monkeypatch.setattr(
        "app.dependencies.auth.decode_access_token",
        lambda t: {"sub": ""},
    )
    creds = HTTPAuthorizationCredentials(scheme="Bearer", credentials="tok")
    with pytest.raises(UnauthorizedException, match="登录状态无效"):
        await get_current_user(creds)


@pytest.mark.asyncio
async def test_get_current_user_not_found(monkeypatch: pytest.MonkeyPatch) -> None:
    # 数据库无对应用户时应拒绝
    monkeypatch.setattr(
        "app.dependencies.auth.decode_access_token",
        lambda t: {"sub": "missing"},
    )
    monkeypatch.setattr(
        "app.dependencies.auth.UserModel.find_one",
        AsyncMock(return_value=None),
    )
    creds = HTTPAuthorizationCredentials(scheme="Bearer", credentials="tok")
    with pytest.raises(UnauthorizedException, match="用户不可用"):
        await get_current_user(creds)


@pytest.mark.asyncio
async def test_get_current_user_disabled(monkeypatch: pytest.MonkeyPatch) -> None:
    # 用户已禁用时应拒绝
    monkeypatch.setattr(
        "app.dependencies.auth.decode_access_token",
        lambda t: {"sub": "u1"},
    )
    monkeypatch.setattr(
        "app.dependencies.auth.UserModel.find_one",
        AsyncMock(return_value=_sample_user(enabled=False)),
    )
    creds = HTTPAuthorizationCredentials(scheme="Bearer", credentials="tok")
    with pytest.raises(UnauthorizedException, match="用户不可用"):
        await get_current_user(creds)


@pytest.mark.asyncio
async def test_get_current_user_success(monkeypatch: pytest.MonkeyPatch) -> None:
    # 正常 Bearer + 有效用户应返回 UserModel
    user = _sample_user()
    monkeypatch.setattr(
        "app.dependencies.auth.decode_access_token",
        lambda t: {"sub": user.id},
    )
    monkeypatch.setattr(
        "app.dependencies.auth.UserModel.find_one",
        AsyncMock(return_value=user),
    )
    creds = HTTPAuthorizationCredentials(scheme="Bearer", credentials="valid-token")
    got = await get_current_user(creds)
    assert got.id == user.id
    assert got.username == user.username


def test_require_permissions_success(monkeypatch: pytest.MonkeyPatch) -> None:
    # 权限齐全时应进入路由
    monkeypatch.setattr(
        "app.dependencies.auth.decode_access_token",
        lambda t: {"sub": "u1"},
    )
    monkeypatch.setattr(
        "app.dependencies.auth.UserModel.find_one",
        AsyncMock(return_value=_sample_user()),
    )
    monkeypatch.setattr(
        "app.dependencies.auth.get_user_permissions",
        AsyncMock(return_value=["a", "b"]),
    )
    client = _client_with_guarded_route(["a"])
    r = client.get("/guard", headers={"Authorization": "Bearer t"})
    assert r.status_code == 200
    assert r.json() == {"ok": True}


def test_require_permissions_wildcard(monkeypatch: pytest.MonkeyPatch) -> None:
    # 通配符 * 时跳过逐项校验
    monkeypatch.setattr(
        "app.dependencies.auth.decode_access_token",
        lambda t: {"sub": "u1"},
    )
    monkeypatch.setattr(
        "app.dependencies.auth.UserModel.find_one",
        AsyncMock(return_value=_sample_user()),
    )
    monkeypatch.setattr(
        "app.dependencies.auth.get_user_permissions",
        AsyncMock(return_value=["*"]),
    )
    client = _client_with_guarded_route(["any:perm"])
    r = client.get("/guard", headers={"Authorization": "Bearer t"})
    assert r.status_code == 200
    assert r.json() == {"ok": True}


def test_require_permissions_insufficient(monkeypatch: pytest.MonkeyPatch) -> None:
    # 缺少任一权限时应 403（经 ApiResponseSchema 返回）
    monkeypatch.setattr(
        "app.dependencies.auth.decode_access_token",
        lambda t: {"sub": "u1"},
    )
    monkeypatch.setattr(
        "app.dependencies.auth.UserModel.find_one",
        AsyncMock(return_value=_sample_user()),
    )
    monkeypatch.setattr(
        "app.dependencies.auth.get_user_permissions",
        AsyncMock(return_value=["only-one"]),
    )
    client = _client_with_guarded_route(["need-a", "need-b"])
    r = client.get("/guard", headers={"Authorization": "Bearer t"})
    assert r.status_code == 200
    body = r.json()
    assert body["code"] == status_codes.FORBIDDEN
    assert "无权限" in body["message"]


def test_require_permissions_empty_required_always_ok(monkeypatch: pytest.MonkeyPatch) -> None:
    # 要求列表为空时 all([]) 为真，应放行
    monkeypatch.setattr(
        "app.dependencies.auth.decode_access_token",
        lambda t: {"sub": "u1"},
    )
    monkeypatch.setattr(
        "app.dependencies.auth.UserModel.find_one",
        AsyncMock(return_value=_sample_user()),
    )
    monkeypatch.setattr(
        "app.dependencies.auth.get_user_permissions",
        AsyncMock(return_value=[]),
    )
    client = _client_with_guarded_route([])
    r = client.get("/guard", headers={"Authorization": "Bearer t"})
    assert r.status_code == 200
    assert r.json() == {"ok": True}


def test_guarded_route_without_auth(monkeypatch: pytest.MonkeyPatch) -> None:
    # 未带令牌时应返回未授权错误码
    monkeypatch.setattr(
        "app.dependencies.auth.decode_access_token",
        lambda t: None,
    )
    client = _client_with_guarded_route(["x"])
    r = client.get("/guard")
    assert r.status_code == 200
    assert r.json()["code"] == status_codes.UNAUTHORIZED
