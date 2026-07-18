"""Authentication dependency tests for server-side sessions and component identity."""

from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock

import pytest
from fastapi import Depends, FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.security import HTTPAuthorizationCredentials
from starlette.testclient import TestClient

import app.utils.status_codes as status_codes
from app.core.exceptions import ApiException, UnauthorizedException
from app.dependencies.auth import get_current_auth_context, get_current_user, require_permissions
from app.models.auth.session import LoginSessionModel
from app.models.auth.user import UserModel
from app.schemas.response import ApiResponseSchema
from app.service.auth_session import AuthContext


def _sample_context() -> AuthContext:
    now = datetime.now(timezone.utc)
    user = UserModel.model_construct(
        id="user-1", username="alice", display_name="Alice", password_hash="h",
        enabled=True, is_system=False, groups=[], authorization_version=2,
        credential_version=1,
    )
    session = LoginSessionModel.model_construct(
        id="session-1", user_id=user.id, status="active", created_at=now,
        last_activity_at=now, expires_at=now + timedelta(minutes=30),
        credential_version=1, authorization_version=2,
    )
    return AuthContext(user=user, session=session, claims={"sub": user.id, "sid": session.id})


def _request() -> Request:
    return Request({"type": "http", "method": "GET", "path": "/", "headers": []})


@pytest.mark.asyncio
async def test_context_rejects_missing_bearer() -> None:
    with pytest.raises(UnauthorizedException, match="未登录"):
        await get_current_auth_context(_request(), None)


@pytest.mark.asyncio
async def test_context_uses_server_session_authenticator(monkeypatch: pytest.MonkeyPatch) -> None:
    context = _sample_context()
    authenticate = AsyncMock(return_value=context)
    monkeypatch.setattr("app.dependencies.auth.authenticate_access_token", authenticate)
    request = _request()
    got = await get_current_auth_context(
        request, HTTPAuthorizationCredentials(scheme="Bearer", credentials="jwt")
    )
    assert got is context
    assert request.state.authorization_version == 2
    authenticate.assert_awaited_once_with("jwt")


def _guard_client(monkeypatch: pytest.MonkeyPatch, allowed: bool) -> TestClient:
    app = FastAPI()

    @app.exception_handler(ApiException)
    async def handler(_: Request, exc: ApiException):
        return JSONResponse(status_code=200, content=ApiResponseSchema.error(code=exc.code, message=exc.message).model_dump())

    app.dependency_overrides[get_current_user] = lambda: _sample_context().user
    monkeypatch.setattr("app.dependencies.auth.has_backend_permissions", AsyncMock(return_value=allowed))

    @app.get("/guard")
    async def guarded(_: None = Depends(require_permissions(["operation:overview:dashboard:read"]))):
        return {"ok": True}

    return TestClient(app)


def test_required_backend_permission_allows(monkeypatch: pytest.MonkeyPatch) -> None:
    assert _guard_client(monkeypatch, True).get("/guard").json() == {"ok": True}


def test_required_backend_permission_denies(monkeypatch: pytest.MonkeyPatch) -> None:
    body = _guard_client(monkeypatch, False).get("/guard").json()
    assert body["code"] == status_codes.FORBIDDEN
