from __future__ import annotations

import logging
import threading
from dataclasses import dataclass, field
from typing import Any

from .rabbitmq import RabbitMQClient


class ComponentFailure(RuntimeError):
    """可预期的组件业务失败。"""


class ComponentCancelled(ComponentFailure):
    """后端请求取消组件运行。"""


class ComponentTimedOut(ComponentFailure):
    """组件超过后端下发的运行时限。"""


class StructuredLogger:
    def __init__(self, logger: logging.Logger):
        self._logger = logger

    def _log(self, level: int, message: str, **fields: Any) -> None:
        self._logger.log(level, message, extra={"csi_fields": fields})

    def debug(self, message: str, **fields: Any) -> None:
        self._log(logging.DEBUG, message, **fields)

    def info(self, message: str, **fields: Any) -> None:
        self._log(logging.INFO, message, **fields)

    def warning(self, message: str, **fields: Any) -> None:
        self._log(logging.WARNING, message, **fields)

    def error(self, message: str, **fields: Any) -> None:
        self._log(logging.ERROR, message, **fields)

    def exception(self, message: str, **fields: Any) -> None:
        self._logger.exception(message, extra={"csi_fields": fields})


@dataclass
class ComponentContext:
    action_id: str
    node_instance_id: str
    component_run_id: str
    component_id: str
    attempt: int
    config: dict[str, Any]
    inputs: dict[str, Any]
    outputs: dict[str, Any]
    logger: StructuredLogger
    _cancelled: threading.Event = field(default_factory=threading.Event, repr=False)
    _timed_out: threading.Event = field(default_factory=threading.Event, repr=False)
    _progress: float = field(default=0, repr=False)
    _progress_message: str = field(default="", repr=False)
    _rabbitmq: RabbitMQClient | None = field(default=None, repr=False)

    def get_config(self, key: str, default: Any = None) -> Any:
        value = self.config.get(key, default)
        if isinstance(value, dict) and "type" in value:
            return value.get("value", value.get("content", value.get("uri", default)))
        return value

    def report_progress(self, percentage: float, message: str = "") -> None:
        self.raise_if_cancelled()
        self._progress = max(0, min(100, float(percentage)))
        self._progress_message = message

    def raise_if_cancelled(self) -> None:
        if self._timed_out.is_set():
            raise ComponentTimedOut("组件运行超时")
        if self._cancelled.is_set():
            raise ComponentCancelled("组件运行已被取消")

    @property
    def rabbitmq(self) -> RabbitMQClient:
        if self._rabbitmq is None:
            client = RabbitMQClient()
            if not client.connect():
                raise ComponentFailure("无法连接 RabbitMQ")
            self._rabbitmq = client
        return self._rabbitmq

    def close(self) -> None:
        if self._rabbitmq is not None:
            self._rabbitmq.close()
            self._rabbitmq = None
