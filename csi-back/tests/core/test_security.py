"""app.core.security 密码哈希与访问令牌测试。"""

import pytest

import app.core.security as security


def test_hash_password_and_verify_round_trip():
    # 同一密码哈希后可校验通过，且每次盐值不同导致密文不同
    raw = "my-secret-password"
    h1 = security.hash_password(raw)
    h2 = security.hash_password(raw)
    assert h1 != h2
    assert security.verify_password(raw, h1) is True
    assert security.verify_password(raw, h2) is True


def test_verify_password_wrong_password():
    # 错误密码应校验失败
    h = security.hash_password("a")
    assert security.verify_password("b", h) is False


def test_verify_password_malformed_encoded():
    # 非法格式的 encoded 字符串应安全返回 False
    assert security.verify_password("x", "not-valid") is False
    assert security.verify_password("x", "pbkdf2_sha256$abc$only$two$parts") is False


def test_verify_password_wrong_algorithm():
    # 非 pbkdf2_sha256 算法应拒绝
    assert security.verify_password("x", "other_algo$120000$salt$digest") is False


def test_create_and_decode_access_token_round_trip(monkeypatch: pytest.MonkeyPatch) -> None:
    # 标准三段 JWT 必须带完整的用户会话与版本声明。
    monkeypatch.setattr(security.settings, "AUTH_SECRET_KEY", "unit-test-secret-key-32bytes!!")
    monkeypatch.setattr(security.settings, "ACCESS_TOKEN_EXPIRE_MINUTES", 30)
    token = security.create_access_token("user-001", "session-001", 3, 4)
    assert len(token.split(".")) == 3
    payload = security.decode_access_token(token)
    assert payload is not None
    assert payload.get("sub") == "user-001"
    assert payload.get("sid") == "session-001"
    assert payload.get("av") == 3
    assert payload.get("cv") == 4
    assert payload.get("purpose") == "user_access"
    assert "exp" in payload and "iat" in payload


def test_decode_access_token_wrong_secret(monkeypatch: pytest.MonkeyPatch) -> None:
    # 密钥被篡改后签名应不匹配
    monkeypatch.setattr(security.settings, "AUTH_SECRET_KEY", "key-a")
    token = security.create_access_token("u1", "s1", 0, 0)
    monkeypatch.setattr(security.settings, "AUTH_SECRET_KEY", "key-b")
    assert security.decode_access_token(token) is None


def test_decode_access_token_expired(monkeypatch: pytest.MonkeyPatch) -> None:
    # 过期令牌（负的过期分钟数）应解析为 None
    monkeypatch.setattr(security.settings, "ACCESS_TOKEN_EXPIRE_MINUTES", -1)
    monkeypatch.setattr(security.settings, "AUTH_SECRET_KEY", "unit-test-secret-key-32bytes!!")
    token = security.create_access_token("u1", "s1", 0, 0)
    assert security.decode_access_token(token) is None


def test_decode_access_token_malformed():
    # 非三段式或损坏的 token 应返回 None
    assert security.decode_access_token("") is None
    assert security.decode_access_token("onlyonepart") is None
    assert security.decode_access_token("a.b.c") is None


def test_component_token_isolated_from_user_audience(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(security.settings, "AUTH_SECRET_KEY", "unit-test-secret-key-32bytes!!")
    token = security.create_component_token("action-1", "node-1", "run-1")
    assert security.decode_access_token(token) is None
    claims = security.decode_component_token(token)
    assert claims is not None
    assert claims["action_id"] == "action-1"
    assert claims["node_id"] == "node-1"
    assert claims["component_run_id"] == "run-1"
    assert set(claims["scope"]) == {"sdk:init", "sdk:result", "sdk:heartbeat", "sdk:logs"}
