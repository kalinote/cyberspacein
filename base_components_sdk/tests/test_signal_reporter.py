from datetime import datetime, timezone
from unittest.mock import MagicMock

import pytest

from csi_base_component_sdk.context import (
    ComponentContext,
    ComponentSignalReportError,
)
from csi_base_component_sdk.signals import (
    ComponentSignalInput,
    ComponentSignalReporter,
)


class _Backend:
    """模拟组件信号传输。"""

    def __init__(self, status: str = "accepted") -> None:
        self.status = status
        self.payloads = []

    def submit_signals(self, payload):
        self.payloads.append(payload)
        return {
            "results": [
                {
                    "report_id": item["report_id"],
                    "status": self.status,
                    "observation_id": "observation-1",
                }
                for item in payload["reports"]
            ]
        }


def component_context(reporter) -> ComponentContext:
    """构造注入私有报告器的 SDK 上下文。"""
    return ComponentContext(
        action_id="action-1",
        node_instance_id="node-1",
        component_run_id="run-1",
        component_id="component-a",
        attempt=1,
        config={},
        inputs={},
        outputs={},
        logger=MagicMock(),
        _signal_reporter=reporter,
    )


@pytest.mark.parametrize("status", ["accepted", "duplicate", "stale"])
def test_context_treats_all_terminal_signal_statuses_as_success(status) -> None:
    backend = _Backend(status)
    reporter = ComponentSignalReporter(backend, MagicMock())
    context = component_context(reporter)

    success = context.report_signal(
        report_id="report-1",
        definition_key="component.demo.health",
        definition_version=1,
        resource_id="resource-1",
        resource_name="资源一",
        value="abnormal",
        observed_at=datetime(2026, 7, 30),
    )

    assert success is True
    assert backend.payloads[0]["reports"][0]["observed_at"].endswith("+00:00")


def test_optional_signal_failure_does_not_raise() -> None:
    backend = MagicMock()
    backend.submit_signals.side_effect = RuntimeError("服务暂不可用")
    context = component_context(
        ComponentSignalReporter(backend, MagicMock())
    )

    assert (
        context.report_signal(
            report_id="report-1",
            definition_key="component.demo.health",
            definition_version=1,
            resource_id="resource-1",
            value="abnormal",
        )
        is False
    )
    assert context._signal_report_failure_count == 1


def test_required_signal_failure_raises_component_error() -> None:
    backend = MagicMock()
    backend.submit_signals.side_effect = RuntimeError("服务暂不可用")
    context = component_context(
        ComponentSignalReporter(backend, MagicMock())
    )

    with pytest.raises(ComponentSignalReportError, match="服务暂不可用"):
        context.report_signal(
            report_id="report-1",
            definition_key="component.demo.health",
            definition_version=1,
            resource_id="resource-1",
            value="abnormal",
            required=True,
        )
    assert context._signal_report_failure_count == 1


def test_signal_input_rejects_sensitive_metadata() -> None:
    item = ComponentSignalInput(
        report_id="report-1",
        definition_key="component.demo.health",
        definition_version=1,
        resource_id="resource-1",
        value="abnormal",
        metadata={"diagnostic": {"api_token": "secret"}},
    )

    with pytest.raises(ValueError, match="敏感认证信息"):
        item.to_payload()


def test_signal_input_serializes_datetime_value_as_utc() -> None:
    item = ComponentSignalInput(
        report_id="report-1",
        definition_key="component.demo.time",
        definition_version=1,
        resource_id="resource-1",
        value=datetime(2026, 7, 30, 12, 0),
    )

    assert item.to_payload()["value"] == "2026-07-30T12:00:00+00:00"


def test_report_signals_accepts_dictionary_inputs() -> None:
    backend = _Backend()
    context = component_context(
        ComponentSignalReporter(backend, MagicMock())
    )

    receipt = context.report_signals(
        [
            {
                "report_id": "report-1",
                "definition_key": "component.demo.health",
                "definition_version": 1,
                "resource_id": "resource-1",
                "value": "normal",
                "observed_at": datetime.now(timezone.utc),
            }
        ]
    )

    assert receipt.success is True
    assert receipt.results[0].report_id == "report-1"
