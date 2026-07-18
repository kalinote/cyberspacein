import base64
import hashlib
import hmac
import json
import secrets
from datetime import datetime, timedelta, timezone
from typing import Any

from app.core.config import settings


def _urlsafe_b64encode(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("utf-8")


def _urlsafe_b64decode(raw: str) -> bytes:
    padding = "=" * (-len(raw) % 4)
    return base64.urlsafe_b64decode((raw + padding).encode("utf-8"))


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, 120000)
    return f"pbkdf2_sha256$120000${_urlsafe_b64encode(salt)}${_urlsafe_b64encode(digest)}"


def verify_password(password: str, encoded: str) -> bool:
    try:
        algorithm, iterations_str, salt_b64, digest_b64 = encoded.split("$", 3)
        if algorithm != "pbkdf2_sha256":
            return False
        iterations = int(iterations_str)
        salt = _urlsafe_b64decode(salt_b64)
        expected_digest = _urlsafe_b64decode(digest_b64)
        digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, iterations)
        return hmac.compare_digest(digest, expected_digest)
    except Exception:
        return False


def _jwt_encode(payload: dict[str, Any]) -> str:
    header = {"alg": "HS256", "typ": "JWT"}
    header_encoded = _urlsafe_b64encode(
        json.dumps(header, ensure_ascii=False, separators=(",", ":"), sort_keys=True).encode("utf-8")
    )
    payload_encoded = _urlsafe_b64encode(
        json.dumps(payload, ensure_ascii=False, separators=(",", ":"), sort_keys=True).encode("utf-8")
    )
    signing_input = f"{header_encoded}.{payload_encoded}"
    signature = hmac.new(
        settings.AUTH_SECRET_KEY.encode("utf-8"),
        signing_input.encode("ascii"),
        hashlib.sha256,
    ).digest()
    return f"{signing_input}.{_urlsafe_b64encode(signature)}"


def _jwt_decode(token: str) -> tuple[dict[str, Any], dict[str, Any]] | None:
    try:
        header_encoded, payload_encoded, signature_encoded = token.split(".")
        signing_input = f"{header_encoded}.{payload_encoded}"
        expected_signature = hmac.new(
            settings.AUTH_SECRET_KEY.encode("utf-8"),
            signing_input.encode("ascii"),
            hashlib.sha256,
        ).digest()
        provided_signature = _urlsafe_b64decode(signature_encoded)
        if not hmac.compare_digest(expected_signature, provided_signature):
            return None
        header = json.loads(_urlsafe_b64decode(header_encoded).decode("utf-8"))
        payload = json.loads(_urlsafe_b64decode(payload_encoded).decode("utf-8"))
        if header != {"alg": "HS256", "typ": "JWT"}:
            return None
        if not isinstance(payload, dict):
            return None
        return header, payload
    except (ValueError, TypeError, json.JSONDecodeError, UnicodeDecodeError):
        return None


def _validate_registered_claims(
    payload: dict[str, Any],
    *,
    audience: str,
    purpose: str,
) -> bool:
    now = int(datetime.now(timezone.utc).timestamp())
    try:
        issued_at = int(payload["iat"])
        expires_at = int(payload["exp"])
    except (KeyError, TypeError, ValueError):
        return False
    if issued_at > now + 30 or expires_at <= now or expires_at <= issued_at:
        return False
    return (
        payload.get("iss") == settings.AUTH_ISSUER
        and payload.get("aud") == audience
        and payload.get("purpose") == purpose
    )


def create_access_token(
    user_id: str,
    session_id: str,
    authorization_version: int,
    credential_version: int,
) -> str:
    now = datetime.now(timezone.utc)
    exp = now + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    payload = {
        "sub": user_id,
        "sid": session_id,
        "iat": int(now.timestamp()),
        "exp": int(exp.timestamp()),
        "iss": settings.AUTH_ISSUER,
        "aud": settings.AUTH_AUDIENCE,
        "purpose": "user_access",
        "av": authorization_version,
        "cv": credential_version,
    }
    return _jwt_encode(payload)


def decode_access_token(token: str) -> dict | None:
    decoded = _jwt_decode(token)
    if decoded is None:
        return None
    _, payload = decoded
    if not _validate_registered_claims(
        payload,
        audience=settings.AUTH_AUDIENCE,
        purpose="user_access",
    ):
        return None
    required = {"sub", "sid", "av", "cv"}
    if not required.issubset(payload):
        return None
    return payload


def create_component_token(action_id: str, node_instance_id: str) -> str:
    now = datetime.now(timezone.utc)
    exp = now + timedelta(minutes=settings.COMPONENT_TOKEN_EXPIRE_MINUTES)
    return _jwt_encode(
        {
            "sub": node_instance_id,
            "action_id": action_id,
            "node_id": node_instance_id,
            "iat": int(now.timestamp()),
            "exp": int(exp.timestamp()),
            "iss": settings.AUTH_ISSUER,
            "aud": settings.COMPONENT_AUTH_AUDIENCE,
            "purpose": "action_component",
            "scope": ["sdk:init", "sdk:result", "sdk:heartbeat"],
        }
    )


def decode_component_token(token: str) -> dict | None:
    decoded = _jwt_decode(token)
    if decoded is None:
        return None
    _, payload = decoded
    if not _validate_registered_claims(
        payload,
        audience=settings.COMPONENT_AUTH_AUDIENCE,
        purpose="action_component",
    ):
        return None
    if not payload.get("action_id") or not payload.get("node_id"):
        return None
    scope = payload.get("scope")
    if not isinstance(scope, list) or not all(isinstance(item, str) for item in scope):
        return None
    return payload
