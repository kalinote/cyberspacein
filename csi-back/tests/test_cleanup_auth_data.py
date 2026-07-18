import pytest

from scripts.cleanup_auth_data import CleanupTarget, validate_cleanup_confirmation


def _target(environment: str = "development", namespace: str = "csi:auth") -> CleanupTarget:
    return CleanupTarget(
        environment=environment,
        database="test_auth_db",
        collections=("auth_users",),
        redis_namespace=namespace,
    )


def test_cleanup_requires_explicit_development_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("ENVIRONMENT", raising=False)
    with pytest.raises(RuntimeError, match="显式设置"):
        validate_cleanup_confirmation(_target(), "DELETE AUTH DATA FROM test_auth_db")


def test_cleanup_requires_exact_confirmation(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ENVIRONMENT", "development")
    with pytest.raises(RuntimeError, match="确认文本不匹配"):
        validate_cleanup_confirmation(_target(), "yes")


def test_cleanup_rejects_unsafe_redis_namespace(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ENVIRONMENT", "development")
    with pytest.raises(RuntimeError, match="namespace"):
        validate_cleanup_confirmation(_target(namespace="*"), "DELETE AUTH DATA FROM test_auth_db")


def test_cleanup_accepts_exact_development_target(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ENVIRONMENT", "development")
    validate_cleanup_confirmation(_target(), "DELETE AUTH DATA FROM test_auth_db")
