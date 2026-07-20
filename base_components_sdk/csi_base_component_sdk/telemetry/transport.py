from __future__ import annotations

import json
import logging
import os
import threading
import time
import traceback
import uuid
from collections import deque
from datetime import datetime, timezone
from typing import Any

from ..backend_client import BackendClient


SENSITIVE_KEYS = {
    "password",
    "passwd",
    "secret",
    "token",
    "authorization",
    "cookie",
    "api_key",
}
LOW_LEVELS = {"TRACE", "DEBUG", "INFO"}


def truncate_utf8(value: str, limit: int = 32 * 1024) -> tuple[str, bool]:
    """按 UTF-8 字节数截断文本并避免产生无效编码。"""
    encoded = value.encode("utf-8")
    if len(encoded) <= limit:
        return value, False
    return encoded[:limit].decode("utf-8", errors="ignore"), True


def redact(value: Any, key: str | None = None) -> Any:
    if key and key.lower() in SENSITIVE_KEYS:
        return "***"
    if isinstance(value, dict):
        return {str(k): redact(v, str(k)) for k, v in value.items()}
    if isinstance(value, list):
        return [redact(item) for item in value]
    if isinstance(value, tuple):
        return [redact(item) for item in value]
    return value


class LogTransport:
    def __init__(
        self,
        client: BackendClient,
        *,
        max_events: int = 10_000,
        max_batch: int = 100,
        max_batch_bytes: int = 256 * 1024,
        interval: float = 0.5,
    ):
        self.client = client
        self.max_events = max_events
        self.max_batch = max_batch
        self.max_batch_bytes = max_batch_bytes
        self.interval = interval
        self._events: deque[dict[str, Any]] = deque()
        self._condition = threading.Condition()
        self._sequence = 0
        self._dropped = 0
        self._closing = False
        self._close_deadline: float | None = None
        self._closed = False
        self._thread = threading.Thread(target=self._run, name="csi-log-sender", daemon=True)
        self._thread.start()

    @property
    def dropped_count(self) -> int:
        with self._condition:
            return self._dropped

    def emit(
        self,
        level: str,
        source: str,
        message: str,
        *,
        logger: str | None = None,
        fields: dict[str, Any] | None = None,
        exception: str | None = None,
    ) -> None:
        if not message:
            return
        message, message_truncated = truncate_utf8(message)
        exception_truncated = False
        if exception:
            exception, exception_truncated = truncate_utf8(exception)
        truncated = message_truncated or exception_truncated
        with self._condition:
            if self._closing:
                return
            if len(self._events) >= self.max_events:
                if level in LOW_LEVELS:
                    self._dropped += 1
                    return
                removed = False
                for index, existing in enumerate(self._events):
                    if existing["level"] in LOW_LEVELS:
                        del self._events[index]
                        self._dropped += 1
                        removed = True
                        break
                if not removed:
                    self._events.popleft()
                    self._dropped += 1
            event = {
                "event_id": str(uuid.uuid4()),
                "sequence": self._sequence,
                "occurred_at": datetime.now(timezone.utc).isoformat(),
                "level": level,
                "source": source,
                "logger": logger,
                "message": message,
                "fields": redact(fields or {}),
                "exception": exception,
                "truncated": truncated,
            }
            self._sequence += 1
            self._events.append(event)
            self._condition.notify_all()

    def _take_batch(self) -> list[dict[str, Any]]:
        batch: list[dict[str, Any]] = []
        size = 0
        while self._events and len(batch) < self.max_batch:
            event = self._events[0]
            event_size = len(
                json.dumps(event, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
            )
            if batch and size + event_size > self.max_batch_bytes:
                break
            batch.append(self._events.popleft())
            size += event_size
        return batch

    def _run(self) -> None:
        delay = 0.5
        while True:
            with self._condition:
                if (
                    self._closing
                    and self._close_deadline is not None
                    and time.monotonic() >= self._close_deadline
                ):
                    self._dropped += len(self._events)
                    self._events.clear()
                    self._closed = True
                    self._condition.notify_all()
                    return
                if not self._events and not self._closing:
                    self._condition.wait(self.interval)
                if self._closing and not self._events:
                    self._closed = True
                    self._condition.notify_all()
                    return
                batch = self._take_batch()
            if not batch:
                continue
            try:
                self.client.submit_logs(batch, self.dropped_count)
                delay = 0.5
            except Exception:
                with self._condition:
                    for event in reversed(batch):
                        self._events.appendleft(event)
                    remaining = (
                        self._close_deadline - time.monotonic()
                        if self._close_deadline is not None
                        else delay
                    )
                    self._condition.wait(max(0, min(delay, remaining)))
                delay = min(delay * 2, 5)

    def close(self, timeout: float = 5) -> None:
        with self._condition:
            self._closing = True
            self._close_deadline = time.monotonic() + timeout
            self._condition.notify_all()
        self._thread.join(timeout)
        with self._condition:
            if self._events:
                self._dropped += len(self._events)
                self._events.clear()


class TransportLogHandler(logging.Handler):
    def __init__(self, transport: LogTransport, original_stderr_fd: int | None = None):
        super().__init__()
        self.transport = transport
        self.original_stderr_fd = original_stderr_fd

    def emit(self, record: logging.LogRecord) -> None:
        try:
            level = "WARNING" if record.levelname == "WARN" else record.levelname
            if level == "CRITICAL":
                level = "FATAL"
            exception = None
            if record.exc_info:
                exception = "".join(traceback.format_exception(*record.exc_info))
            self.transport.emit(
                level if level in {"TRACE", "DEBUG", "INFO", "WARNING", "ERROR", "FATAL"} else "INFO",
                "logging",
                record.getMessage(),
                logger=record.name,
                fields=getattr(record, "csi_fields", {}),
                exception=exception,
            )
            if self.original_stderr_fd is not None:
                rendered = f"[{level}] [{record.name}] {record.getMessage()}\n"
                os.write(self.original_stderr_fd, rendered.encode("utf-8", errors="replace"))
        except Exception:
            self.handleError(record)
