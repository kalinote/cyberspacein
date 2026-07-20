import asyncio
import logging
import os
import sys
import threading
import types

import pytest

from csi_base_component_sdk.context import StructuredLogger
from csi_base_component_sdk.telemetry import LogTransport, OutputCapture, TransportLogHandler
from csi_base_component_sdk.telemetry.transport import redact


class RecordingClient:
    def __init__(self) -> None:
        self.batches: list[list[dict]] = []
        self.event = threading.Event()

    def submit_logs(self, entries: list[dict], dropped_count: int) -> None:
        self.batches.append(entries)
        self.event.set()


def test_redact_recursively_masks_sensitive_fields() -> None:
    assert redact({"token": "x", "nested": {"api_key": "y", "safe": 1}}) == {
        "token": "***",
        "nested": {"api_key": "***", "safe": 1},
    }


def test_transport_assigns_monotonic_sequence_and_truncates() -> None:
    client = RecordingClient()
    transport = LogTransport(client, interval=0.05)
    transport.emit("INFO", "sdk", "first")
    transport.emit("ERROR", "sdk", "x" * 40_000)
    assert client.event.wait(1)
    transport.close(1)
    events = [event for batch in client.batches for event in batch]
    assert [event["sequence"] for event in events] == list(range(len(events)))
    assert events[-1]["truncated"] is True
    assert len(events[-1]["message"]) == 32768


def test_standard_logging_is_collected_once() -> None:
    client = RecordingClient()
    transport = LogTransport(client, interval=0.05)
    logger = logging.getLogger("sdk-test")
    logger.handlers.clear()
    logger.propagate = False
    logger.setLevel(logging.INFO)
    logger.addHandler(TransportLogHandler(transport))
    StructuredLogger(logger).info("hello", password="secret", value=1)
    assert client.event.wait(1)
    transport.close(1)
    events = [event for batch in client.batches for event in batch]
    assert len(events) == 1
    assert events[0]["fields"] == {"password": "***", "value": 1}


@pytest.mark.skipif(os.name != "posix", reason="文件描述符捕获仅在 Linux/Crawlab 启用")
def test_fd_capture_collects_os_write() -> None:
    client = RecordingClient()
    transport = LogTransport(client, interval=0.05)
    capture = OutputCapture(transport)
    capture.start()
    os.write(1, b"native-output\n")
    capture.stop()
    transport.close(1)
    capture.close_original_fds()
    events = [event for batch in client.batches for event in batch]
    assert any(event["source"] == "stdout" and event["message"] == "native-output" for event in events)


def test_runner_accepts_awaitable_return_value() -> None:
    sys.modules.setdefault("crawlab", types.SimpleNamespace(save_item=lambda _: None))
    from csi_base_component_sdk.runner import _run_callable

    async def component(_):
        await asyncio.sleep(0)
        return {"ok": True}

    assert _run_callable(component, object()) == {"ok": True}
