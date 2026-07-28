from __future__ import annotations

import sys
from types import SimpleNamespace
from unittest.mock import MagicMock

import csi_base_component_sdk.runner as runner
from csi_base_component_sdk.context import ComponentFailure
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
    assert "上下文格式异常" in submitted[0]["error"]
