from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from app.core.exceptions import UnauthorizedException
from app.service import auth_session


def _session(**updates):
    now = datetime.now(timezone.utc)
    values = {
        "id": "session-1",
        "user_id": "user-1",
        "status": "active",
        "created_at": now,
        "last_activity_at": now,
        "expires_at": now + timedelta(minutes=30),
        "credential_version": 1,
        "authorization_version": 1,
    }
    values.update(updates)
    return SimpleNamespace(**values, save=AsyncMock())


def _user(**updates):
    values = {
        "id": "user-1",
        "username": "alice",
        "display_name": "Alice",
        "password_hash": "h",
        "enabled": True,
        "expired_at": None,
        "is_deleted": False,
        "groups": [],
        "credential_version": 1,
        "authorization_version": 2,
    }
    values.update(updates)
    return SimpleNamespace(**values)


@pytest.mark.asyncio
async def test_revoked_session_rejects_valid_jwt(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(auth_session, "decode_access_token", lambda _: {"sub": "user-1", "sid": "session-1", "cv": 1})
    monkeypatch.setattr(auth_session.LoginSessionModel, "find_one", AsyncMock(return_value=_session(status="terminated")))
    with pytest.raises(UnauthorizedException, match="登录已失效"):
        await auth_session.authenticate_access_token("jwt")


@pytest.mark.asyncio
async def test_expired_session_is_terminated(monkeypatch: pytest.MonkeyPatch) -> None:
    session = _session(expires_at=datetime.now(timezone.utc) - timedelta(seconds=1))
    monkeypatch.setattr(auth_session, "decode_access_token", lambda _: {"sub": "user-1", "sid": "session-1", "cv": 1})
    monkeypatch.setattr(auth_session.LoginSessionModel, "find_one", AsyncMock(return_value=session))
    with pytest.raises(UnauthorizedException, match="登录已过期"):
        await auth_session.authenticate_access_token("jwt")
    assert session.status == "terminated"
    session.save.assert_awaited_once()


@pytest.mark.asyncio
async def test_credential_change_invalidates_session(monkeypatch: pytest.MonkeyPatch) -> None:
    session = _session()
    monkeypatch.setattr(auth_session, "decode_access_token", lambda _: {"sub": "user-1", "sid": "session-1", "cv": 1})
    monkeypatch.setattr(auth_session.LoginSessionModel, "find_one", AsyncMock(return_value=session))
    monkeypatch.setattr(auth_session.UserModel, "find_one", AsyncMock(return_value=_user(credential_version=2)))
    with pytest.raises(UnauthorizedException, match="凭据已变更"):
        await auth_session.authenticate_access_token("jwt")
    assert session.terminated_reason == "credential_changed"


@pytest.mark.asyncio
async def test_authorization_version_change_uses_live_user(monkeypatch: pytest.MonkeyPatch) -> None:
    session = _session(authorization_version=1)
    user = _user(authorization_version=4)
    monkeypatch.setattr(
        auth_session,
        "decode_access_token",
        lambda _: {"sub": "user-1", "sid": "session-1", "cv": 1, "av": 1},
    )
    monkeypatch.setattr(auth_session.LoginSessionModel, "find_one", AsyncMock(return_value=session))
    monkeypatch.setattr(auth_session.UserModel, "find_one", AsyncMock(return_value=user))
    context = await auth_session.authenticate_access_token("jwt")
    assert context.user.authorization_version == 4
