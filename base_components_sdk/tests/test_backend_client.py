from __future__ import annotations

import logging
import threading
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


def test_submit_signals_retries_with_same_payload(monkeypatch) -> None:
    client = BackendClient("http://localhost:8000/api/v1", "test-run")
    payload = {"reports": [{"report_id": "report-1"}]}
    request = MagicMock(
        side_effect=[
            RuntimeError("temporary"),
            {"results": [{"report_id": "report-1", "status": "accepted"}]},
        ]
    )
    monkeypatch.setattr(client, "_request", request)
    monkeypatch.setattr("csi_base_component_sdk.backend_client.time.sleep", lambda _: None)

    try:
        result = client.submit_signals(payload)
    finally:
        client.close()

    assert result["results"][0]["status"] == "accepted"
    assert request.call_count == 2
    assert all(call.kwargs["json"] is payload for call in request.call_args_list)


def test_heartbeat_uses_independent_session_and_lock(monkeypatch) -> None:
    control_session = MagicMock()
    heartbeat_session = MagicMock()
    heartbeat_response = MagicMock()
    heartbeat_response.json.return_value = {
        "code": 0,
        "data": {"command": "continue"},
    }
    heartbeat_session.request.return_value = heartbeat_response
    session_factory = MagicMock(side_effect=[control_session, heartbeat_session])
    monkeypatch.setattr(
        "csi_base_component_sdk.backend_client.requests.Session",
        session_factory,
    )
    client = BackendClient("http://localhost:8000/api/v1", "test-run")
    client.set_token("component-token")
    finished = threading.Event()
    result = []

    def send_heartbeat() -> None:
        result.append(client.heartbeat(25, "运行中"))
        finished.set()

    client._lock.acquire()
    heartbeat_thread = threading.Thread(target=send_heartbeat)
    try:
        heartbeat_thread.start()
        assert finished.wait(1)
    finally:
        client._lock.release()
        heartbeat_thread.join(timeout=1)
        client.close()

    assert client._session is not client._heartbeat_session
    assert client._lock is not client._heartbeat_lock
    assert result == [{"command": "continue"}]
    control_session.request.assert_not_called()
    heartbeat_session.request.assert_called_once()
    assert (
        heartbeat_session.request.call_args.kwargs["headers"]["Authorization"]
        == "Bearer component-token"
    )
    control_session.close.assert_called_once()
    heartbeat_session.close.assert_called_once()
