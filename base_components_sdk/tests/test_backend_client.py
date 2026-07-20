from __future__ import annotations

import logging

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
