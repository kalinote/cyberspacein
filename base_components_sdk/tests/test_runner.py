from __future__ import annotations

import sys
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

import csi_base_component_sdk.runner as runner
from csi_base_component_sdk.context import (
    ComponentCancelled,
    ComponentContext,
    ComponentFailure,
    ComponentTimedOut,
)
from csi_base_component_sdk.runner import _load_entrypoint


def test_load_entrypoint_from_current_component_directory(tmp_path, monkeypatch):
    entry_module = tmp_path / "component_entry.py"
    entry_module.write_text(
        "def run(ctx):\n"
        "    return {'loaded': True}\n",
        encoding="utf-8",
    )
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(
        sys,
        "path",
        [path for path in sys.path if path not in ("", str(tmp_path))],
    )
    sys.modules.pop("component_entry", None)

    try:
        function = _load_entrypoint("component_entry:run")
        assert function(None) == {"loaded": True}
        assert sys.path[0] == str(tmp_path)
    finally:
        sys.modules.pop("component_entry", None)


class _Clock:
    def __init__(self):
        self.current = 0.0

    def monotonic(self):
        return self.current


class _HeartbeatStop:
    def __init__(self, clock):
        self.clock = clock
        self.stopped = False

    def wait(self, timeout):
        if self.stopped:
            return True
        self.clock.current += timeout
        return False


def test_heartbeat_loop_keeps_fixed_monotonic_schedule():
    clock = _Clock()
    stop = _HeartbeatStop(clock)
    call_times = []
    durations = iter([2.0, 4.0, 1.0])

    class _HeartbeatClient:
        def heartbeat(self, _progress, _message):
            call_times.append(clock.current)
            clock.current += next(durations)
            if len(call_times) == 3:
                stop.stopped = True
            return {"command": "continue"}

    context = SimpleNamespace(
        _progress=25,
        _progress_message="运行中",
        _cancelled=MagicMock(),
    )

    runner._heartbeat_loop(
        _HeartbeatClient(),
        context,
        10,
        stop,
        None,
        monotonic=clock.monotonic,
    )

    assert call_times == [10.0, 20.0, 30.0]


def test_heartbeat_loop_retries_quickly_between_regular_ticks():
    clock = _Clock()
    stop = _HeartbeatStop(clock)
    call_times = []

    class _HeartbeatClient:
        def heartbeat(self, _progress, _message):
            call_times.append(clock.current)
            if len(call_times) <= 2:
                clock.current += 5.0
                raise RuntimeError("临时失败")
            stop.stopped = True
            return {"command": "continue"}

    context = SimpleNamespace(
        _progress=25,
        _progress_message="运行中",
        _cancelled=MagicMock(),
    )

    runner._heartbeat_loop(
        _HeartbeatClient(),
        context,
        10,
        stop,
        None,
        monotonic=clock.monotonic,
    )

    assert call_times == [10.0, 16.0, 23.0]


class _Capture:
    original_stderr_fd = None

    def __init__(self, _transport):
        pass

    def start(self):
        pass

    def stop(self):
        pass

    def close_original_fds(self):
        pass


class _Transport:
    def __init__(self, _backend):
        pass

    def emit(self, *_args, **_kwargs):
        pass

    def close(self, timeout):
        pass


def _run_with_context(monkeypatch, context, function):
    monkeypatch.setattr(runner, "_local_context", lambda *_: context)
    monkeypatch.setattr(runner, "_load_entrypoint", lambda _: function)
    monkeypatch.setattr(runner, "save_item", lambda _: None)
    monkeypatch.setattr(runner, "LogTransport", _Transport)
    monkeypatch.setattr(runner, "OutputCapture", _Capture)
    monkeypatch.setattr(runner, "TransportLogHandler", lambda *_: runner.logging.NullHandler())
    return runner.run_component(
        SimpleNamespace(
            local_config="config.json",
            api_base_url=None,
            component_run_id=None,
            component_bootstrap=None,
            entrypoint="component:run",
        )
    )


def test_runner_sends_eos_before_closing_context(monkeypatch):
    events = []
    context = SimpleNamespace(
        action_id="action-1",
        node_instance_id="node-1",
        component_run_id="run-1",
        component_id="component-1",
        attempt=1,
        logger=MagicMock(),
        raise_if_cancelled=lambda: None,
        close_reference_outputs=lambda status: events.append(("control", status)),
        close=lambda: events.append(("close", None)),
    )

    assert _run_with_context(monkeypatch, context, lambda _: {}) == 0
    assert events == [("control", "success"), ("close", None)]


def test_runner_sends_abort_after_component_failure(monkeypatch):
    events = []
    context = SimpleNamespace(
        action_id="action-1",
        node_instance_id="node-1",
        component_run_id="run-1",
        component_id="component-1",
        attempt=1,
        logger=MagicMock(),
        raise_if_cancelled=lambda: None,
        close_reference_outputs=lambda status: events.append(("control", status)),
        close=lambda: events.append(("close", None)),
    )

    def fail(_context):
        raise ComponentFailure("failed")

    assert _run_with_context(monkeypatch, context, fail) == 1
    assert events == [("control", "failed"), ("close", None)]


def test_component_context_marks_successful_result_once():
    context = ComponentContext(
        action_id="action-1",
        node_instance_id="node-1",
        component_run_id="run-1",
        component_id="component-1",
        attempt=1,
        config={},
        inputs={},
        outputs={},
        logger=MagicMock(),
    )

    assert context.has_successful_result is False
    context.mark_successful_result()
    context.mark_successful_result()
    assert context.has_successful_result is True


def test_component_context_marks_reference_publish_automatically(monkeypatch):
    client = MagicMock()
    client.connect.return_value = True
    monkeypatch.setattr(
        "csi_base_component_sdk.context.RabbitMQClient",
        MagicMock(return_value=client),
    )
    context = ComponentContext(
        action_id="action-1",
        node_instance_id="node-1",
        component_run_id="run-1",
        component_id="component-1",
        attempt=1,
        config={},
        inputs={},
        outputs={"data_out": {"type": "reference"}},
        logger=MagicMock(),
    )

    assert context.rabbitmq is client
    callback = client.configure_reference_streams.call_args.kwargs[
        "successful_result_callback"
    ]
    callback()

    assert context.has_successful_result is True


@pytest.mark.parametrize(
    "value",
    [
        {"id": "entity-1"},
        ["entity-1"],
        "entity-1",
        b"entity-1",
        0,
        False,
    ],
)
def test_declared_non_empty_value_output_is_successful_result(value):
    assert runner._has_declared_value_result(
        {"dict_out": {"type": "value"}},
        {"dict_out": value},
    ) is True


@pytest.mark.parametrize("value", [None, "", b"", {}, [], (), set()])
def test_declared_empty_value_output_is_not_successful_result(value):
    assert runner._has_declared_value_result(
        {"dict_out": {"type": "value"}},
        {"dict_out": value},
    ) is False


def test_undeclared_or_reference_output_is_not_successful_value_result():
    outputs = {"dict_out": {"id": "entity-1"}, "processed": 1}

    assert runner._has_declared_value_result(
        {"data_out": {"type": "reference"}},
        outputs,
    ) is False


def test_runner_marks_declared_value_output_after_success(monkeypatch):
    submitted = []
    local_client = runner._LocalClient

    class _RecordingLocalClient(local_client):
        def submit_result(self, payload):
            submitted.append(payload)

    context = ComponentContext(
        action_id="action-1",
        node_instance_id="node-1",
        component_run_id="run-1",
        component_id="component-1",
        attempt=1,
        config={},
        inputs={},
        outputs={"dict_out": {"type": "value"}},
        logger=MagicMock(),
    )
    monkeypatch.setattr(runner, "_LocalClient", _RecordingLocalClient)

    assert _run_with_context(
        monkeypatch,
        context,
        lambda _: {"dict_out": {"id": "entity-1"}, "processed": 1},
    ) == 0
    assert submitted[0]["has_successful_result"] is True


def test_runner_does_not_mark_value_output_when_finalization_fails(monkeypatch):
    submitted = []
    local_client = runner._LocalClient

    class _RecordingLocalClient(local_client):
        def submit_result(self, payload):
            submitted.append(payload)

    context = ComponentContext(
        action_id="action-1",
        node_instance_id="node-1",
        component_run_id="run-1",
        component_id="component-1",
        attempt=1,
        config={},
        inputs={},
        outputs={"dict_out": {"type": "value"}},
        logger=MagicMock(),
    )
    context.close_reference_outputs = MagicMock(
        side_effect=ComponentFailure("输出收尾失败")
    )
    monkeypatch.setattr(runner, "_LocalClient", _RecordingLocalClient)

    assert _run_with_context(
        monkeypatch,
        context,
        lambda _: {"dict_out": {"id": "entity-1"}},
    ) == 1
    assert submitted[0]["has_successful_result"] is False


def test_runner_submits_successful_result_marker_after_failure(monkeypatch):
    submitted = []
    local_client = runner._LocalClient

    class _RecordingLocalClient(local_client):
        def submit_result(self, payload):
            submitted.append(payload)

    context = ComponentContext(
        action_id="action-1",
        node_instance_id="node-1",
        component_run_id="run-1",
        component_id="component-1",
        attempt=1,
        config={},
        inputs={},
        outputs={},
        logger=MagicMock(),
    )

    def fail_after_result(component):
        component.mark_successful_result()
        raise ComponentFailure("部分数据处理失败")

    monkeypatch.setattr(runner, "_LocalClient", _RecordingLocalClient)

    assert _run_with_context(monkeypatch, context, fail_after_result) == 1
    assert submitted[0]["status"] == "failed"
    assert submitted[0]["has_successful_result"] is True


def test_runner_submits_false_marker_when_no_result_succeeded(monkeypatch):
    submitted = []
    local_client = runner._LocalClient

    class _RecordingLocalClient(local_client):
        def submit_result(self, payload):
            submitted.append(payload)

    context = ComponentContext(
        action_id="action-1",
        node_instance_id="node-1",
        component_run_id="run-1",
        component_id="component-1",
        attempt=1,
        config={},
        inputs={},
        outputs={},
        logger=MagicMock(),
    )

    monkeypatch.setattr(runner, "_LocalClient", _RecordingLocalClient)

    assert _run_with_context(monkeypatch, context, lambda _: {}) == 0
    assert submitted[0]["status"] == "success"
    assert submitted[0]["has_successful_result"] is False


def test_runner_submits_successful_result_marker_after_success(monkeypatch):
    submitted = []
    local_client = runner._LocalClient

    class _RecordingLocalClient(local_client):
        def submit_result(self, payload):
            submitted.append(payload)

    context = ComponentContext(
        action_id="action-1",
        node_instance_id="node-1",
        component_run_id="run-1",
        component_id="component-1",
        attempt=1,
        config={},
        inputs={},
        outputs={},
        logger=MagicMock(),
    )

    def succeed_with_result(component):
        component.mark_successful_result()
        return {}

    monkeypatch.setattr(runner, "_LocalClient", _RecordingLocalClient)

    assert _run_with_context(monkeypatch, context, succeed_with_result) == 0
    assert submitted[0]["status"] == "success"
    assert submitted[0]["has_successful_result"] is True


@pytest.mark.parametrize(
    ("exception", "expected_status"),
    [
        (ComponentCancelled("用户取消"), "cancelled"),
        (ComponentTimedOut("组件超时"), "timed_out"),
        (KeyboardInterrupt("未知中断"), "failed"),
    ],
)
def test_runner_preserves_successful_result_marker_for_terminal_errors(
    monkeypatch,
    exception,
    expected_status,
):
    submitted = []
    local_client = runner._LocalClient

    class _RecordingLocalClient(local_client):
        def submit_result(self, payload):
            submitted.append(payload)

    context = ComponentContext(
        action_id="action-1",
        node_instance_id="node-1",
        component_run_id="run-1",
        component_id="component-1",
        attempt=1,
        config={},
        inputs={},
        outputs={},
        logger=MagicMock(),
    )

    def fail_after_result(component):
        component.mark_successful_result()
        raise exception

    monkeypatch.setattr(runner, "_LocalClient", _RecordingLocalClient)

    assert _run_with_context(monkeypatch, context, fail_after_result) == 1
    assert submitted[0]["status"] == expected_status
    assert submitted[0]["has_successful_result"] is True


def test_runner_reports_failure_when_remote_initialization_fails(monkeypatch):
    submitted = []

    class _FailingInitBackend:
        def __init__(self, _api_base_url, _component_run_id):
            self.attempt = None

        def exchange_token(self, _bootstrap):
            self.attempt = 2
            return "token"

        def initialize(self):
            raise RuntimeError("初始化接口异常")

        def submit_result(self, payload):
            submitted.append(payload)

        def close(self):
            pass

    monkeypatch.setattr(runner, "BackendClient", _FailingInitBackend)

    exit_code = runner.run_component(
        SimpleNamespace(
            local_config=None,
            api_base_url="http://localhost:8000/api/v1",
            component_run_id="run-1",
            component_bootstrap="bootstrap",
            entrypoint="component:run",
        )
    )

    assert exit_code == 2
    assert submitted[0]["attempt"] == 2
    assert submitted[0]["status"] == "failed"
    assert submitted[0]["has_successful_result"] is False
    assert submitted[0]["exit_code"] == 2
    assert "初始化接口异常" in submitted[0]["error"]


def test_runner_reports_failure_when_remote_context_is_invalid(monkeypatch):
    submitted = []

    class _InvalidContextBackend:
        def __init__(self, _api_base_url, _component_run_id):
            self.attempt = None

        def exchange_token(self, _bootstrap):
            self.attempt = 1
            return "token"

        def initialize(self):
            return {
                "action_id": "action-1",
                "node_instance_id": "node-1",
                "component_run_id": "run-1",
                "component_id": "component-1",
                "attempt": 1,
            }

        def submit_result(self, payload):
            submitted.append(payload)

        def close(self):
            pass

    monkeypatch.setattr(runner, "BackendClient", _InvalidContextBackend)
    monkeypatch.setattr(
        runner,
        "ComponentContext",
        lambda **_kwargs: (_ for _ in ()).throw(RuntimeError("上下文格式异常")),
    )
    monkeypatch.setattr(runner, "LogTransport", _Transport)
    monkeypatch.setattr(runner, "OutputCapture", _Capture)
    monkeypatch.setattr(
        runner,
        "TransportLogHandler",
        lambda *_: runner.logging.NullHandler(),
    )

    exit_code = runner.run_component(
        SimpleNamespace(
            local_config=None,
            api_base_url="http://localhost:8000/api/v1",
            component_run_id="run-1",
            component_bootstrap="bootstrap",
            entrypoint="component:run",
        )
    )

    assert exit_code == 2
    assert submitted[0]["attempt"] == 1
    assert submitted[0]["status"] == "failed"
    assert submitted[0]["has_successful_result"] is False
    assert "上下文格式异常" in submitted[0]["error"]
