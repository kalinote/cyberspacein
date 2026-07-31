from __future__ import annotations

import logging
import os
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
        self.attempt: int | None = None
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
        attempt = data.get("attempt")
        if not isinstance(attempt, int) or attempt < 1:
            raise RuntimeError("组件短期凭证响应缺少有效运行次数")
        self.attempt = attempt
        self.set_token(token)
        return token

    def set_token(self, token: str) -> None:
        self._session.headers.update({"Authorization": f"Bearer {token}"})

    def initialize(self) -> dict[str, Any]:
        return self._request(
            "GET",
            "init",
            timeout=15,
        )

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

    def submit_signals(self, payload: dict[str, Any]) -> dict[str, Any]:
        """使用固定次数指数退避提交组件信号。"""
        try:
            attempts = max(
                1,
                int(os.getenv("COMPONENT_SIGNAL_HTTP_RETRY_ATTEMPTS", "5")),
            )
            max_delay = max(
                0.1,
                float(
                    os.getenv(
                        "COMPONENT_SIGNAL_HTTP_RETRY_MAX_SECONDS",
                        "5",
                    )
                ),
            )
        except ValueError as exc:
            raise RuntimeError("组件信号 SDK 重试配置无效") from exc
        delay = min(0.5, max_delay)
        last_error: Exception | None = None
        for index in range(attempts):
            try:
                return self._request(
                    "POST",
                    "signals",
                    json=payload,
                    timeout=15,
                )
            except Exception as exc:
                last_error = exc
                if index + 1 < attempts:
                    time.sleep(delay)
                    delay = min(delay * 2, max_delay)
        raise RuntimeError(f"组件信号提交失败: {last_error}")

    def close(self) -> None:
        self._session.close()
