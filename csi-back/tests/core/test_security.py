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
    # 签发与校验使用同一密钥时应能解析出 sub
    monkeypatch.setattr(security.settings, "AUTH_SECRET_KEY", "unit-test-secret-key-32bytes!!")
    monkeypatch.setattr(security.settings, "ACCESS_TOKEN_EXPIRE_MINUTES", 30)
    token = security.create_access_token("user-001")
    payload = security.decode_access_token(token)
    assert payload is not None
    assert payload.get("sub") == "user-001"
    assert "exp" in payload and "iat" in payload


def test_decode_access_token_wrong_secret(monkeypatch: pytest.MonkeyPatch) -> None:
    # 密钥被篡改后签名应不匹配
    monkeypatch.setattr(security.settings, "AUTH_SECRET_KEY", "key-a")
    token = security.create_access_token("u1")
    monkeypatch.setattr(security.settings, "AUTH_SECRET_KEY", "key-b")
    assert security.decode_access_token(token) is None


def test_decode_access_token_expired(monkeypatch: pytest.MonkeyPatch) -> None:
    # 过期令牌（负的过期分钟数）应解析为 None
    monkeypatch.setattr(security.settings, "ACCESS_TOKEN_EXPIRE_MINUTES", -1)
    monkeypatch.setattr(security.settings, "AUTH_SECRET_KEY", "unit-test-secret-key-32bytes!!")
    token = security.create_access_token("u1")
    assert security.decode_access_token(token) is None


def test_decode_access_token_malformed():
    # 非两段式或损坏的 token 应返回 None
    assert security.decode_access_token("") is None
    assert security.decode_access_token("onlyonepart") is None
    assert security.decode_access_token("a.b.c") is None
