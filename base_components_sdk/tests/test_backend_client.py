from __future__ import annotations

import logging
from unittest.mock import MagicMock

from csi_base_component_sdk.backend_client import BackendClient


def test_backend_client_suppresses_internal_http_debug_logs() -> None:
    logger_names = ("requests", "urllib3", "urllib3.connectionpool")
    loggers = [logging.getLogger(name) for name in logger_names]
    original_levels = [logger.level for logger in loggers]
    client = None

    try:
        for logger in loggers:
            logger.setLevel(logging.DEBUG)

        client = BackendClient("http://localhost:8000/api/v1", "test-run")

        assert all(logger.level == logging.WARNING for logger in loggers)
    finally:
        if client is not None:
            client.close()
        for logger, level in zip(loggers, original_levels):
            logger.setLevel(level)


def test_initialize_requests_component_context(monkeypatch) -> None:
    client = BackendClient("http://localhost:8000/api/v1", "test-run")
    request = MagicMock(return_value={})
    monkeypatch.setattr(client, "_request", request)

    try:
        client.initialize()
    finally:
        client.close()

    request.assert_called_once_with(
        "GET",
        "init",
        timeout=15,
    )


def test_exchange_token_records_component_attempt(monkeypatch) -> None:
    client = BackendClient("http://localhost:8000/api/v1", "test-run")
    request = MagicMock(
        return_value={"component_token": "component-token", "attempt": 3}
    )
    monkeypatch.setattr(client, "_request", request)

    try:
        assert client.exchange_token("bootstrap") == "component-token"
        assert client.attempt == 3
    finally:
        client.close()

    request.assert_called_once_with(
        "POST",
        "token",
        headers={"X-Component-Bootstrap": "bootstrap"},
        timeout=10,
    )
