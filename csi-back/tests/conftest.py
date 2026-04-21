import os

import pytest


def apply_minimal_settings_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """为实例化 Settings() 提供一组最小可用的环境变量（与 CI 占位一致）。"""
    env = {
        "API_V1_STR": "/api/v1",
        "APP_NAME": "test-app",
        "DEBUG": "false",
        "MARIADB_URL": "mysql+pymysql://user:pass@127.0.0.1:3306/test",
        "MONGODB_URL": "mongodb://127.0.0.1:27017",
        "MONGODB_USERNAME": "t",
        "MONGODB_PASSWORD": "t",
        "MONGODB_DB_NAME": "t",
        "REDIS_URL": "redis://127.0.0.1:6379/0",
        "REDIS_PASSWORD": "",
        "ELASTICSEARCH_URL": "http://127.0.0.1:9200",
        "ELASTICSEARCH_USER": "t",
        "ELASTICSEARCH_PASSWORD": "t",
        "RABBITMQ_HOST": "127.0.0.1",
        "RABBITMQ_PORT": "5672",
        "RABBITMQ_USERNAME": "t",
        "RABBITMQ_PASSWORD": "t",
        "CRAWLAB_BASE_URL": "http://127.0.0.1",
        "CRAWLAB_TOKEN": "t",
        "COS_ENDPOINT": "https://example.com",
        "COS_ACCESS_KEY_ID": "t",
        "COS_SECRET_ACCESS_KEY": "t",
        "COS_BUCKET_NAME": "t",
        "COS_REGION": "ap-beijing",
    }
    for key, value in env.items():
        monkeypatch.setenv(key, value)


def _ensure_ci_placeholder_env() -> None:
    if not (os.environ.get("CI") or os.environ.get("GITHUB_ACTIONS")):
        return
    placeholders = {
        "API_V1_STR": "/api/v1",
        "APP_NAME": "ci-test",
        "DEBUG": "false",
        "MARIADB_URL": "mysql+pymysql://user:pass@127.0.0.1:3306/test",
        "MONGODB_URL": "mongodb://127.0.0.1:27017",
        "MONGODB_USERNAME": "ci",
        "MONGODB_PASSWORD": "ci",
        "MONGODB_DB_NAME": "ci",
        "REDIS_URL": "redis://127.0.0.1:6379/0",
        "REDIS_PASSWORD": "",
        "ELASTICSEARCH_URL": "http://127.0.0.1:9200",
        "ELASTICSEARCH_USER": "ci",
        "ELASTICSEARCH_PASSWORD": "ci",
        "RABBITMQ_HOST": "127.0.0.1",
        "RABBITMQ_PORT": "5672",
        "RABBITMQ_USERNAME": "ci",
        "RABBITMQ_PASSWORD": "ci",
        "CRAWLAB_BASE_URL": "http://127.0.0.1",
        "CRAWLAB_TOKEN": "ci",
        "COS_ENDPOINT": "https://example.com",
        "COS_ACCESS_KEY_ID": "ci",
        "COS_SECRET_ACCESS_KEY": "ci",
        "COS_BUCKET_NAME": "ci",
        "COS_REGION": "ap-beijing",
    }
    for key, value in placeholders.items():
        if key not in os.environ:
            os.environ[key] = value


_ensure_ci_placeholder_env()
