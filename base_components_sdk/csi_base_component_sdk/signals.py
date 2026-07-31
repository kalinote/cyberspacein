from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Protocol

from .context import ComponentSignalReportError

_SENSITIVE_METADATA_PARTS = {
    "apikey",
    "authorization",
    "bearer",
    "cookie",
    "credential",
    "password",
    "passwd",
    "privatekey",
    "proxyauth",
    "secret",
    "session",
    "token",
}


class _SignalBackend(Protocol):
    """定义组件信号报告器需要的最小传输接口。"""

    def submit_signals(self, payload: dict[str, Any]) -> dict[str, Any]:
        """提交一个组件信号批次。"""
        ...


def _contains_sensitive_metadata(value: Any) -> bool:
    """递归检查 metadata 是否包含常见凭证键。"""
    if isinstance(value, dict):
        for key, nested in value.items():
            normalized_key = "".join(
                character
                for character in str(key).lower()
                if character.isalnum()
            )
            if any(part in normalized_key for part in _SENSITIVE_METADATA_PARTS):
                return True
            if _contains_sensitive_metadata(nested):
                return True
    elif isinstance(value, list):
        return any(_contains_sensitive_metadata(item) for item in value)
    return False


@dataclass(slots=True)
class ComponentSignalInput:
    """描述 SDK 准备提交的一条通用组件信号。"""

    report_id: str
    definition_key: str
    definition_version: int
    resource_id: str
    value: Any
    observed_at: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
    resource_name: str | None = None
    source_event_id: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_payload(self) -> dict[str, Any]:
        """校验并序列化为组件信号 API 载荷。"""
        report_id = self.report_id.strip()
        definition_key = self.definition_key.strip()
        resource_id = self.resource_id.strip()
        resource_name = (
            self.resource_name.strip()
            if isinstance(self.resource_name, str)
            else None
        )
        source_event_id = (
            self.source_event_id.strip()
            if isinstance(self.source_event_id, str)
            else None
        )
        if not report_id or len(report_id) > 128:
            raise ValueError("组件信号 report_id 长度必须为 1 到 128")
        if not definition_key or len(definition_key) > 100:
            raise ValueError("组件信号 definition_key 长度必须为 1 到 100")
        if (
            isinstance(self.definition_version, bool)
            or not isinstance(self.definition_version, int)
            or self.definition_version < 1
        ):
            raise ValueError("组件信号 definition_version 必须为正整数")
        if not resource_id or len(resource_id) > 300:
            raise ValueError("组件信号 resource_id 长度必须为 1 到 300")
        if self.resource_name is not None and (
            not resource_name or len(resource_name) > 300
        ):
            raise ValueError("组件信号 resource_name 长度必须为 1 到 300")
        if self.source_event_id is not None and (
            not source_event_id or len(source_event_id) > 500
        ):
            raise ValueError("组件信号 source_event_id 长度必须为 1 到 500")
        if not isinstance(self.observed_at, datetime):
            raise ValueError("组件信号 observed_at 必须是 datetime")
        observed_at = (
            self.observed_at.replace(tzinfo=timezone.utc)
            if self.observed_at.tzinfo is None
            else self.observed_at.astimezone(timezone.utc)
        )
        if not isinstance(self.metadata, dict):
            raise ValueError("组件信号 metadata 必须是字典")
        if _contains_sensitive_metadata(self.metadata):
            raise ValueError("组件信号 metadata 不能包含凭证或敏感认证信息")
        value = self.value
        if isinstance(value, datetime):
            value = (
                value.replace(tzinfo=timezone.utc)
                if value.tzinfo is None
                else value.astimezone(timezone.utc)
            ).isoformat()
        payload = {
            "report_id": report_id,
            "definition_key": definition_key,
            "definition_version": self.definition_version,
            "resource": {
                "resource_id": resource_id,
                "resource_name": resource_name,
            },
            "value": value,
            "observed_at": observed_at.isoformat(),
            "source_event_id": source_event_id,
            "metadata": self.metadata,
        }
        try:
            json.dumps(payload, ensure_ascii=False, allow_nan=False)
        except (TypeError, ValueError) as exc:
            raise ValueError("组件信号载荷必须可以序列化为 JSON") from exc
        return payload


@dataclass(frozen=True, slots=True)
class ComponentSignalResult:
    """表示服务端对单条组件信号的处理结果。"""

    report_id: str
    status: str
    observation_id: str | None = None


@dataclass(frozen=True, slots=True)
class ComponentSignalBatchReceipt:
    """表示一次组件信号批量提交的结果。"""

    success: bool
    results: tuple[ComponentSignalResult, ...] = ()
    error: str | None = None


class ComponentSignalReporter:
    """为 ComponentContext 提供校验、传输和失败策略。"""

    def __init__(self, backend: _SignalBackend, logger: Any) -> None:
        self._backend = backend
        self._logger = logger

    def report_signals(
        self,
        reports: list[ComponentSignalInput | dict[str, Any]],
        *,
        required: bool = False,
    ) -> ComponentSignalBatchReceipt:
        """校验并提交一批组件信号。"""
        try:
            if not 1 <= len(reports) <= 100:
                raise ValueError("组件信号单批数量必须为 1 到 100")
            normalized = [
                item
                if isinstance(item, ComponentSignalInput)
                else ComponentSignalInput(**item)
                for item in reports
            ]
            payload = {"reports": [item.to_payload() for item in normalized]}
            response = self._backend.submit_signals(payload)
            raw_results = response.get("results")
            if not isinstance(raw_results, list) or len(raw_results) != len(
                normalized
            ):
                raise RuntimeError("组件信号服务返回的批次结果不完整")
            expected_ids = [item.report_id.strip() for item in normalized]
            results = []
            for index, item in enumerate(raw_results):
                if not isinstance(item, dict):
                    raise RuntimeError("组件信号服务返回了无效结果")
                report_id = item.get("report_id")
                status = item.get("status")
                if (
                    report_id != expected_ids[index]
                    or status not in {"accepted", "duplicate", "stale"}
                ):
                    raise RuntimeError("组件信号服务返回的结果与请求不一致")
                results.append(
                    ComponentSignalResult(
                        report_id=report_id,
                        status=status,
                        observation_id=item.get("observation_id"),
                    )
                )
            if getattr(self._backend, "is_local", False):
                self._logger.info(
                    "本地模式已校验组件信号",
                    report_count=len(results),
                )
            return ComponentSignalBatchReceipt(
                success=True,
                results=tuple(results),
            )
        except Exception as exc:
            self._logger.error(
                "组件信号上报失败",
                error=str(exc),
                report_count=len(reports),
            )
            if required:
                raise ComponentSignalReportError(
                    f"组件信号上报失败: {exc}"
                ) from exc
            return ComponentSignalBatchReceipt(
                success=False,
                error=str(exc),
            )
