from __future__ import annotations

import logging
import threading
import time
from typing import Any

import requests


def _suppress_internal_http_debug_logs() -> None:
    """Prevent SDK transport diagnostics from feeding back into component logs.

    Some component frameworks install their own root handlers and enable DEBUG
    globally.  urllib3 then logs every SDK request, including the request that
    uploads logs.  Capturing that diagnostic creates another upload and can form
    an unbounded feedback loop.  HTTP warnings and errors remain visible.
    """
    for logger_name in ("requests", "urllib3", "urllib3.connectionpool"):
        logging.getLogger(logger_name).setLevel(logging.WARNING)


class BackendClient:
    def __init__(self, api_base_url: str, component_run_id: str):
        _suppress_internal_http_debug_logs()
        self.api_base_url = api_base_url.rstrip("/")
        self.component_run_id = component_run_id
        self._session = requests.Session()
        self._lock = threading.Lock()

    def _url(self, suffix: str) -> str:
        return f"{self.api_base_url}/action/sdk/{self.component_run_id}/{suffix}"

    def _request(self, method: str, suffix: str, **kwargs) -> dict[str, Any]:
        with self._lock:
            response = self._session.request(method, self._url(suffix), **kwargs)
        response.raise_for_status()
        body = response.json()
        if body.get("code") != 0:
            raise RuntimeError(body.get("message") or f"CSI API {suffix} 调用失败")
        return body.get("data") or {}

    def exchange_token(self, bootstrap: str) -> str:
        data = self._request(
            "POST",
            "token",
            headers={"X-Component-Bootstrap": bootstrap},
            timeout=10,
        )
        token = data.get("component_token")
        if not token:
            raise RuntimeError("组件短期凭证交换失败")
        self.set_token(token)
        return token

    def set_token(self, token: str) -> None:
        self._session.headers.update({"Authorization": f"Bearer {token}"})

    def initialize(self) -> dict[str, Any]:
        return self._request("GET", "init", timeout=15)

    def heartbeat(self, progress: float, message: str) -> dict[str, Any]:
        data = self._request(
            "POST",
            "heartbeat",
            json={"progress": progress, "message": message},
            timeout=5,
        )
        refreshed = data.get("component_token")
        if refreshed:
            self.set_token(refreshed)
        return data

    def submit_logs(self, entries: list[dict[str, Any]], dropped_count: int) -> None:
        """提交一个可重试日志批次。"""
        self._request(
            "POST",
            "log-batches",
            json={"entries": entries, "dropped_count": dropped_count},
            timeout=4,
        )

    def submit_result(self, payload: dict[str, Any]) -> None:
        delay = 0.5
        last_error: Exception | None = None
        for _ in range(5):
            try:
                self._request("POST", "result", json=payload, timeout=15)
                return
            except Exception as exc:
                last_error = exc
                time.sleep(delay)
                delay = min(delay * 2, 5)
        raise RuntimeError(f"组件结果提交失败: {last_error}")

    def close(self) -> None:
        self._session.close()
