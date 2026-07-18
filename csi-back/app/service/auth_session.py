from __future__ import annotations

import hashlib
import secrets
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any

from app.core.config import settings
from app.core.exceptions import UnauthorizedException
from app.core.security import create_access_token, decode_access_token
from app.db.redis import get_redis
from app.models.auth.session import LoginSessionModel
from app.models.auth.user import UserModel


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


@dataclass(slots=True)
class AuthContext:
    user: UserModel
    session: LoginSessionModel
    claims: dict[str, Any]


def _redis_key(kind: str, value: str) -> str:
    digest = hashlib.sha256(value.strip().lower().encode("utf-8")).hexdigest()
    return f"{settings.AUTH_REDIS_NAMESPACE}:{kind}:{digest}"


async def _increment_with_window(key: str, window_seconds: int) -> int:
    redis = get_redis()
    if redis is None:
        return 1
    value = await redis.incr(key)
    if value == 1:
        await redis.expire(key, window_seconds)
    return int(value)


async def ensure_login_allowed(username: str, source: str | None) -> None:
    redis = get_redis()
    if redis is None:
        return
    account_key = _redis_key("rate:account", username)
    source_key = _redis_key("rate:source", source or "unknown")
    lock_key = _redis_key("lock", username)
    if await redis.exists(lock_key):
        raise UnauthorizedException("用户名或密码错误，或账号暂时不可用")
    account_count = await _increment_with_window(
        account_key, settings.LOGIN_RATE_LIMIT_WINDOW_SECONDS
    )
    source_count = await _increment_with_window(
        source_key, settings.LOGIN_RATE_LIMIT_WINDOW_SECONDS
    )
    if (
        account_count > settings.LOGIN_RATE_LIMIT_ACCOUNT
        or source_count > settings.LOGIN_RATE_LIMIT_SOURCE
    ):
        raise UnauthorizedException("用户名或密码错误，或账号暂时不可用")


async def record_login_failure(username: str) -> None:
    redis = get_redis()
    if redis is None:
        return
    failure_key = _redis_key("failure", username)
    count = await _increment_with_window(
        failure_key, settings.LOGIN_FAILURE_WINDOW_SECONDS
    )
    if count >= settings.LOGIN_FAILURE_THRESHOLD:
        await redis.set(
            _redis_key("lock", username),
            "1",
            ex=settings.LOGIN_LOCK_SECONDS,
        )
        await redis.delete(failure_key)


async def clear_login_failures(username: str) -> None:
    redis = get_redis()
    if redis is not None:
        await redis.delete(_redis_key("failure", username))


async def create_user_session(
    user: UserModel,
    *,
    login_ip: str | None,
    user_agent: str | None,
) -> tuple[str, LoginSessionModel]:
    now = utcnow()
    expires_at = now + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    session = LoginSessionModel(
        id=secrets.token_urlsafe(32),
        user_id=user.id,
        status="active",
        created_at=now,
        last_activity_at=now,
        expires_at=expires_at,
        login_ip=login_ip,
        user_agent=(user_agent or "")[:512] or None,
        credential_version=user.credential_version,
        authorization_version=user.authorization_version,
    )
    await session.insert()
    token = create_access_token(
        user.id,
        session.id,
        user.authorization_version,
        user.credential_version,
    )
    return token, session


async def terminate_session(
    session: LoginSessionModel,
    *,
    reason: str,
) -> None:
    if session.status == "terminated":
        return
    session.status = "terminated"
    session.terminated_at = utcnow()
    session.terminated_reason = reason[:200]
    await session.save()


async def terminate_session_by_id(
    session_id: str,
    *,
    reason: str,
    user_id: str | None = None,
) -> bool:
    query: dict[str, Any] = {"_id": session_id}
    if user_id is not None:
        query["user_id"] = user_id
    session = await LoginSessionModel.find_one(query)
    if session is None:
        return False
    await terminate_session(session, reason=reason)
    return True


async def terminate_user_sessions(user_id: str, *, reason: str) -> int:
    sessions = await LoginSessionModel.find(
        {"user_id": user_id, "status": "active"}
    ).to_list()
    for session in sessions:
        await terminate_session(session, reason=reason)
    return len(sessions)


async def authenticate_access_token(token: str) -> AuthContext:
    claims = decode_access_token(token)
    if claims is None:
        raise UnauthorizedException("登录已失效，请重新登录")

    user_id = str(claims.get("sub") or "")
    session_id = str(claims.get("sid") or "")
    if not user_id or not session_id:
        raise UnauthorizedException("登录状态无效")

    session = await LoginSessionModel.find_one({"_id": session_id})
    if session is None or session.status != "active" or session.user_id != user_id:
        raise UnauthorizedException("登录已失效，请重新登录")
    now = utcnow()
    if as_utc(session.expires_at) <= now:
        await terminate_session(session, reason="session_expired")
        raise UnauthorizedException("登录已过期，请重新登录")

    user = await UserModel.find_one({"_id": user_id, "is_deleted": False})
    if user is None or not user.enabled:
        await terminate_session(session, reason="user_unavailable")
        raise UnauthorizedException("用户不可用")
    if user.expired_at is not None and as_utc(user.expired_at) <= now:
        await terminate_user_sessions(user.id, reason="account_expired")
        raise UnauthorizedException("账号已到期")

    try:
        claim_credential_version = int(claims["cv"])
    except (KeyError, TypeError, ValueError):
        raise UnauthorizedException("登录状态无效")
    if (
        claim_credential_version != user.credential_version
        or session.credential_version != user.credential_version
    ):
        await terminate_session(session, reason="credential_changed")
        raise UnauthorizedException("凭据已变更，请重新登录")

    if (now - as_utc(session.last_activity_at)).total_seconds() >= 60:
        session.last_activity_at = now
        await session.save()
    return AuthContext(user=user, session=session, claims=claims)
