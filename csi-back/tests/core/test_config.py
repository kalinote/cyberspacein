"""app.core.config 配置与 Settings 行为测试。"""

import pytest

from app.core.config import Settings
from tests.conftest import apply_minimal_settings_env


def test_settings_api_base_url_uses_server_host_and_port(monkeypatch: pytest.MonkeyPatch) -> None:
    # 显式配置 SERVER_HOST / SERVER_PORT 时，api_base_url 应拼接为 http://host:port + API_V1_STR
    apply_minimal_settings_env(monkeypatch)
    monkeypatch.setenv("SERVER_HOST", "192.168.1.10")
    monkeypatch.setenv("SERVER_PORT", "9000")
    monkeypatch.setenv("API_V1_STR", "/api/v1")
    s = Settings()
    assert s.api_base_url == "http://192.168.1.10:9000/api/v1"


def test_settings_api_base_url_fallback_local_ip_and_default_port(monkeypatch: pytest.MonkeyPatch) -> None:
    # 未配置有效 SERVER_HOST / SERVER_PORT 时，主机使用 get_local_ip，端口默认为 8080（覆盖 .env）
    apply_minimal_settings_env(monkeypatch)
    monkeypatch.setenv("SERVER_HOST", "")
    monkeypatch.setenv("SERVER_PORT", "0")
    monkeypatch.setattr("app.core.config.get_local_ip", lambda: "10.0.0.5")
    s = Settings()
    assert s.api_base_url == "http://10.0.0.5:8080/api/v1"


def test_settings_optional_defaults_and_extra_env_ignored(monkeypatch: pytest.MonkeyPatch) -> None:
    # 可选字段有合理默认值；extra=ignore 时未知环境变量不导致加载失败
    apply_minimal_settings_env(monkeypatch)
    monkeypatch.setenv("UNKNOWN_TEST_ENV_FOR_SETTINGS", "should_be_ignored")
    s = Settings()
    assert s.RABBITMQ_VHOST == "/"
    assert s.HYBRID_TOTAL_CAP == 10000
