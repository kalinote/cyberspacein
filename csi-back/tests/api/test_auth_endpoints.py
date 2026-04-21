"""app.api.v1.endpoints.auth 路由测试（不启动完整 lifespan，依赖 mock）。"""

from datetime import datetime
from unittest.mock import AsyncMock

import pytest
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from starlette.testclient import TestClient

import app.utils.status_codes as status_codes
from app.api.v1.endpoints import auth as auth_ep
from app.core.exceptions import ApiException
from app.models.auth.user import UserModel
from app.schemas.response import ApiResponseSchema


def _make_client() -> TestClient:
    app = FastAPI()

    @app.exception_handler(ApiException)
    async def _handle_api(request: Request, exc: ApiException) -> JSONResponse:
        return JSONResponse(
            status_code=200,
            content=ApiResponseSchema.error(
                code=exc.code,
                message=exc.message,
                data=exc.data,
            ).model_dump(),
        )

    app.include_router(auth_ep.router, prefix="/api/v1")
    return TestClient(app)


def test_login_failed_returns_unauthorized(monkeypatch: pytest.MonkeyPatch) -> None:
    # 认证失败时返回业务未授权码
    monkeypatch.setattr(
        "app.api.v1.endpoints.auth.authenticate_user",
        AsyncMock(return_value=None),
    )
    client = _make_client()
    r = client.post("/api/v1/auth/login", json={"username": "n", "password": "p"})
    assert r.status_code == 200
    body = r.json()
    assert body["code"] == status_codes.UNAUTHORIZED


def test_login_success_returns_token_and_user(monkeypatch: pytest.MonkeyPatch) -> None:
    # 认证成功时返回 token 与用户信息
    user = UserModel.model_construct(
        id="u-1",
        username="alice",
        display_name="A",
        password_hash="h",
        create_by="sys",
        create_at=datetime(2024, 1, 1, 0, 0, 0),
        groups=[],
    )
    monkeypatch.setattr(
        "app.api.v1.endpoints.auth.authenticate_user",
        AsyncMock(return_value=("access-token", user, ["perm.a"])),
    )
    client = _make_client()
    r = client.post("/api/v1/auth/login", json={"username": "alice", "password": "ok"})
    assert r.status_code == 200
    body = r.json()
    assert body["code"] == 0
    assert body["data"]["access_token"] == "access-token"
    assert body["data"]["user"]["uuid"] == "u-1"
    assert body["data"]["permissions"] == ["perm.a"]


def test_me_without_token_returns_unauthorized(monkeypatch: pytest.MonkeyPatch) -> None:
    # 未携带 Bearer 时依赖抛出未授权
    client = _make_client()
    r = client.get("/api/v1/auth/me")
    assert r.status_code == 200
    assert r.json()["code"] == status_codes.UNAUTHORIZED


def test_logout_without_token_returns_unauthorized():
    # 退出登录同样需要已登录用户
    client = _make_client()
    r = client.post("/api/v1/auth/logout")
    assert r.status_code == 200
    assert r.json()["code"] == status_codes.UNAUTHORIZED
