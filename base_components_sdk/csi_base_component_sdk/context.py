from __future__ import annotations

import logging
import threading
from dataclasses import dataclass, field
from datetime import datetime
from typing import TYPE_CHECKING, Any

from .rabbitmq import RabbitMQClient

if TYPE_CHECKING:
    from .signals import (
        ComponentSignalBatchReceipt,
        ComponentSignalInput,
        ComponentSignalReporter,
    )


class ComponentFailure(RuntimeError):
    """可预期的组件业务失败。"""


class ComponentCancelled(ComponentFailure):
    """后端请求取消组件运行。"""


class ComponentTimedOut(ComponentFailure):
    """组件超过后端下发的运行时限。"""


class ComponentSignalReportError(ComponentFailure):
    """关键组件信号无法提交。"""


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
    _has_successful_result: threading.Event = field(
        default_factory=threading.Event,
        repr=False,
    )
    _rabbitmq: RabbitMQClient | None = field(default=None, repr=False)
    _signal_reporter: ComponentSignalReporter | None = field(
        default=None,
        repr=False,
    )
    _signal_report_failure_count: int = field(default=0, repr=False)

    def get_config(self, key: str, default: Any = None) -> Any:
        value = self.config.get(key, default)
        if isinstance(value, dict) and "type" in value:
            return value.get("value", value.get("content", value.get("uri", default)))
        return value

    def report_progress(self, percentage: float, message: str = "") -> None:
        self.raise_if_cancelled()
        self._progress = max(0, min(100, float(percentage)))
        self._progress_message = message

    def mark_successful_result(self) -> None:
        """标记当前组件已经确认至少一条成功业务结果。"""
        self._has_successful_result.set()

    @property
    def has_successful_result(self) -> bool:
        """返回当前组件是否已经确认成功业务结果。"""
        return self._has_successful_result.is_set()

    def raise_if_cancelled(self) -> None:
        if self._timed_out.is_set():
            raise ComponentTimedOut("组件运行超时")
        if self._cancelled.is_set():
            raise ComponentCancelled("组件运行已被取消")

    def report_signal(
        self,
        *,
        report_id: str,
        definition_key: str,
        definition_version: int,
        resource_id: str,
        value: Any,
        observed_at: datetime | None = None,
        resource_name: str | None = None,
        source_event_id: str | None = None,
        metadata: dict[str, Any] | None = None,
        required: bool = False,
    ) -> bool:
        """上报一条通用资源信号并返回是否成功接收。"""
        from datetime import timezone

        from .signals import ComponentSignalInput

        receipt = self.report_signals(
            [
                ComponentSignalInput(
                    report_id=report_id,
                    definition_key=definition_key,
                    definition_version=definition_version,
                    resource_id=resource_id,
                    value=value,
                    observed_at=observed_at
                    if observed_at is not None
                    else datetime.now(timezone.utc),
                    resource_name=resource_name,
                    source_event_id=source_event_id,
                    metadata=metadata if metadata is not None else {},
                )
            ],
            required=required,
        )
        return receipt.success

    def report_signals(
        self,
        reports: list[ComponentSignalInput | dict[str, Any]],
        *,
        required: bool = False,
    ) -> ComponentSignalBatchReceipt:
        """批量上报通用资源信号。"""
        from .signals import ComponentSignalBatchReceipt

        if self._signal_reporter is None:
            self._signal_report_failure_count += 1
            message = "组件运行上下文未配置组件信号报告器"
            self.logger.error(message, report_count=len(reports))
            if required:
                raise ComponentSignalReportError(message)
            return ComponentSignalBatchReceipt(success=False, error=message)
        try:
            receipt = self._signal_reporter.report_signals(
                reports,
                required=required,
            )
        except ComponentSignalReportError:
            self._signal_report_failure_count += 1
            raise
        if not receipt.success:
            self._signal_report_failure_count += 1
        return receipt

    @property
    def rabbitmq(self) -> RabbitMQClient:
        if self._rabbitmq is None:
            client = RabbitMQClient()
            client.configure_reference_streams(
                self.inputs,
                self.outputs,
                cancel_check=self.raise_if_cancelled,
                successful_result_callback=self.mark_successful_result,
            )
            if not client.connect():
                raise ComponentFailure("无法连接 RabbitMQ")
            self._rabbitmq = client
        return self._rabbitmq

    def close_reference_outputs(self, status: str) -> None:
        """由 Runner 自动关闭当前组件声明的 REFERENCE 输出流。"""
        has_eos_output = any(
            isinstance(value, dict)
            and value.get("type") == "reference"
            and any(
                isinstance(stream, dict) and stream.get("protocol") == "eos-v1"
                for stream in value.get("streams") or []
            )
            for value in self.outputs.values()
        )
        if not has_eos_output:
            return
        published = self.rabbitmq.close_reference_outputs(
            action_id=self.action_id,
            producer_id=self.component_run_id,
            status=status,
        )
        if status == "success" and not published:
            raise ComponentFailure("REFERENCE 输出流 EOS 发送失败")

    def close(self) -> None:
        if self._rabbitmq is not None:
            self._rabbitmq.close()
            self._rabbitmq = None
