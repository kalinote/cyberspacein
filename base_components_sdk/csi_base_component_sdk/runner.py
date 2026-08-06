from __future__ import annotations

import argparse
import asyncio
import importlib
import inspect
import json
import logging
import os
import signal
import sys
import threading
import time
import traceback
import uuid
from collections.abc import Sized
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

# TODO(native-scheduler): Crawlab 仅用于开发阶段避免空结果错误。自研 Worker
# 接管运行生命周期后删除此 import、save_item 调用和 crawlab-sdk 依赖。
from crawlab import save_item

from .backend_client import BackendClient
from .context import (
    ComponentCancelled,
    ComponentContext,
    ComponentFailure,
    ComponentTimedOut,
    StructuredLogger,
)
from .signals import ComponentSignalReporter
from .telemetry import LogTransport, OutputCapture, TransportLogHandler


_HEARTBEAT_RETRY_INITIAL_SECONDS = 1.0
_HEARTBEAT_RETRY_MAX_SECONDS = 5.0


class _LocalClient:
    is_local = True

    def __init__(self) -> None:
        self.signal_batches: list[dict[str, Any]] = []

    def submit_logs(self, entries: list[dict[str, Any]], dropped_count: int) -> None:
        return None

    def submit_result(self, payload: dict[str, Any]) -> None:
        return None

    def submit_signals(self, payload: dict[str, Any]) -> dict[str, Any]:
        """保存本地信号批次并模拟服务端接收结果。"""
        self.signal_batches.append(payload)
        return {
            "results": [
                {
                    "report_id": item["report_id"],
                    "status": "accepted",
                    "observation_id": None,
                }
                for item in payload["reports"]
            ]
        }

    def close(self) -> None:
        return None


def _diagnostic(message: str, fd: int | None = None) -> None:
    rendered = f"[CSI Runner] {message}\n".encode("utf-8", errors="replace")
    try:
        os.write(fd if fd is not None else 2, rendered)
    except Exception:
        pass


def _submit_initialization_failure(
    backend: BackendClient,
    attempt: int,
    error_message: str,
    diagnostic_fd: int | None = None,
) -> None:
    """在组件业务代码启动前将初始化失败收敛到后端终态。"""
    try:
        backend.submit_result(
            {
                "result_id": str(uuid.uuid4()),
                "attempt": attempt,
                "status": "failed",
                "outputs": {},
                "has_successful_result": False,
                "error": error_message,
                "exit_code": 2,
            }
        )
    except Exception as exc:
        _diagnostic(f"初始化失败结果提交失败: {exc}", diagnostic_fd)


def _load_entrypoint(spec: str) -> Callable[[ComponentContext], Any]:
    module_name, separator, function_name = spec.partition(":")
    if not separator or not module_name or not function_name:
        raise ComponentFailure("组件入口必须使用 module:function 格式")

    # pip 生成的 console-script 会将 sys.path[0] 指向 Scripts/bin，而不是
    # 当前组件目录。Crawlab 和本地直接运行 csi-component 时都需要显式加入 cwd。
    component_dir = os.getcwd()
    if component_dir not in sys.path:
        sys.path.insert(0, component_dir)

    module = importlib.import_module(module_name)
    function = getattr(module, function_name, None)
    if not callable(function):
        raise ComponentFailure(f"组件入口不存在或不可调用: {spec}")
    return function


def _run_callable(function: Callable, context: ComponentContext) -> dict[str, Any]:
    value = function(context)
    if inspect.isawaitable(value):
        value = asyncio.run(value)
    if value is None:
        return {}
    if not isinstance(value, dict):
        raise ComponentFailure("组件入口返回值必须是 dict 或 None")
    return value


def _has_declared_value_result(
    output_declarations: dict[str, Any],
    outputs: dict[str, Any],
) -> bool:
    """判断组件返回值中是否包含已声明且非空的 Value 输出。"""
    if not isinstance(output_declarations, dict):
        return False
    for name, declaration in output_declarations.items():
        if (
            not isinstance(declaration, dict)
            or declaration.get("type") != "value"
            or name not in outputs
        ):
            continue
        value = outputs[name]
        if value is None:
            continue
        if isinstance(value, Sized):
            try:
                if len(value) == 0:
                    continue
            except Exception:
                pass
        return True
    return False


def _heartbeat_loop(
    client: BackendClient,
    context: ComponentContext,
    interval: int,
    stop: threading.Event,
    original_stderr_fd: int | None,
    *,
    monotonic: Callable[[], float] = time.monotonic,
) -> None:
    """按单调时钟固定节拍发送心跳，并在失败后快速重试。

    常规心跳始终锚定线程启动时的单调时钟，不把请求耗时累加到下一次
    心跳间隔。失败重试会插入常规节拍之间，并在成功后恢复固定节拍。
    """
    interval_seconds = max(float(interval), 1.0)
    retry_delay = _HEARTBEAT_RETRY_INITIAL_SECONDS
    next_regular_at = monotonic() + interval_seconds
    next_attempt_at = next_regular_at

    while not stop.wait(max(next_attempt_at - monotonic(), 0.0)):
        succeeded = False
        try:
            response = client.heartbeat(context._progress, context._progress_message)
            succeeded = True
            if response.get("command") == "cancel":
                context._cancelled.set()
        except Exception as exc:
            _diagnostic(f"心跳上报失败: {exc}", original_stderr_fd)

        now = monotonic()
        if next_regular_at <= now:
            elapsed_intervals = int(
                (now - next_regular_at) // interval_seconds
            ) + 1
            next_regular_at += elapsed_intervals * interval_seconds
        if succeeded:
            retry_delay = _HEARTBEAT_RETRY_INITIAL_SECONDS
            next_attempt_at = next_regular_at
            continue
        next_attempt_at = min(now + retry_delay, next_regular_at)
        retry_delay = min(retry_delay * 2, _HEARTBEAT_RETRY_MAX_SECONDS)


def _local_context(
    path: str,
    logger: StructuredLogger,
    signal_reporter: ComponentSignalReporter,
) -> ComponentContext:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    meta = data.get("meta") or {}
    return ComponentContext(
        action_id=str(meta.get("action_id") or "local-action"),
        node_instance_id=str(meta.get("node_instance_id") or meta.get("node_id") or "local-node"),
        component_run_id=str(meta.get("component_run_id") or "local-component-run"),
        component_id=str(meta.get("component_id") or "local-component"),
        attempt=int(meta.get("attempt") or 1),
        config=data.get("config") or {},
        inputs=data.get("inputs") or {},
        outputs=data.get("outputs") or {},
        logger=logger,
        reference_consumer_ack_timeout_seconds=int(
            data.get("reference_consumer_ack_timeout_seconds")
            or meta.get("reference_consumer_ack_timeout_seconds")
            or 21600
        ),
        reference_consumer_ack_safety_margin_seconds=int(
            data.get("reference_consumer_ack_safety_margin_seconds")
            or meta.get("reference_consumer_ack_safety_margin_seconds")
            or 300
        ),
        _signal_reporter=signal_reporter,
    )


def run_component(args: argparse.Namespace) -> int:
    started_at = datetime.now(timezone.utc)
    remote = not bool(args.local_config)
    backend: BackendClient | _LocalClient
    init_data: dict[str, Any] = {}
    if remote:
        if not args.api_base_url or not args.component_run_id or not args.component_bootstrap:
            _diagnostic("远程运行缺少 api-base-url、component-run-id 或 component-bootstrap")
            return 2
        backend = BackendClient(args.api_base_url, args.component_run_id)
        token_exchanged = False
        try:
            backend.exchange_token(args.component_bootstrap)
            token_exchanged = True
            init_data = backend.initialize()
        except Exception as exc:
            error_message = f"运行上下文初始化失败: {exc}"
            _diagnostic(error_message)
            if token_exchanged and backend.attempt is not None:
                _submit_initialization_failure(
                    backend,
                    backend.attempt,
                    error_message,
                )
            backend.close()
            return 2
    else:
        backend = _LocalClient()

    transport = LogTransport(backend)  # type: ignore[arg-type]
    capture = OutputCapture(transport)
    capture.start()
    handler = TransportLogHandler(transport, capture.original_stderr_fd)
    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(logging.INFO)
    structured_logger = StructuredLogger(logging.getLogger("component"))
    signal_reporter = ComponentSignalReporter(backend, structured_logger)

    try:
        if remote:
            context = ComponentContext(
                action_id=init_data["action_id"],
                node_instance_id=init_data["node_instance_id"],
                component_run_id=init_data["component_run_id"],
                component_id=init_data["component_id"],
                attempt=int(init_data["attempt"]),
                config=init_data.get("config") or {},
                inputs=init_data.get("inputs") or {},
                outputs=init_data.get("outputs") or {},
                logger=structured_logger,
                reference_consumer_ack_timeout_seconds=int(
                    init_data["reference_consumer_ack_timeout_seconds"]
                ),
                reference_consumer_ack_safety_margin_seconds=int(
                    init_data[
                        "reference_consumer_ack_safety_margin_seconds"
                    ]
                ),
                _signal_reporter=signal_reporter,
            )
        else:
            context = _local_context(
                args.local_config,
                structured_logger,
                signal_reporter,
            )
    except Exception as exc:
        error_message = f"运行上下文无效: {exc}"
        capture.stop()
        transport.close(timeout=1)
        root.removeHandler(handler)
        if remote and backend.attempt is not None:
            _submit_initialization_failure(
                backend,
                backend.attempt,
                error_message,
                capture.original_stderr_fd,
            )
        backend.close()
        capture.close_original_fds()
        _diagnostic(error_message)
        return 2

    heartbeat_stop = threading.Event()
    heartbeat_thread: threading.Thread | None = None
    timeout_timer: threading.Timer | None = None
    previous_alarm_handler = None
    if remote:
        heartbeat_thread = threading.Thread(
            target=_heartbeat_loop,
            args=(
                backend,
                context,
                int(init_data.get("heartbeat_interval") or 10),
                heartbeat_stop,
                capture.original_stderr_fd,
            ),
            name="csi-heartbeat",
            daemon=True,
        )
        heartbeat_thread.start()

        timeout_seconds = int(init_data.get("timeout_seconds") or 0)
        if timeout_seconds > 0:
            if os.name == "posix" and threading.current_thread() is threading.main_thread():
                previous_alarm_handler = signal.getsignal(signal.SIGALRM)

                def _raise_timeout(_signum, _frame):
                    raise ComponentTimedOut("组件运行超时")

                signal.signal(signal.SIGALRM, _raise_timeout)
                signal.setitimer(signal.ITIMER_REAL, timeout_seconds)
            else:
                timeout_timer = threading.Timer(timeout_seconds, context._timed_out.set)
                timeout_timer.daemon = True
                timeout_timer.start()

    status = "success"
    outputs: dict[str, Any] = {}
    error: str | None = None
    exit_code = 0
    try:
        context.logger.info("组件运行开始", entrypoint=args.entrypoint)
        outputs = _run_callable(_load_entrypoint(args.entrypoint), context)
        context.raise_if_cancelled()
        context.close_reference_outputs("success")
        context.logger.info("组件运行成功")
    except ComponentCancelled as exc:
        status = "cancelled"
        error = str(exc)
        exit_code = 1
        context.logger.warning("组件运行已取消", error=error)
    except ComponentTimedOut as exc:
        status = "timed_out"
        error = str(exc)
        exit_code = 1
        context.logger.error("组件运行超时", error=error)
    except ComponentFailure as exc:
        status = "failed"
        error = str(exc)
        exit_code = 1
        context.logger.error("组件业务失败", error=error)
    except BaseException as exc:
        status = "failed"
        error = str(exc)
        exit_code = 1
        transport.emit(
            "FATAL",
            "exception",
            "组件发生未处理异常",
            logger="component",
            exception="".join(traceback.format_exception(type(exc), exc, exc.__traceback__)),
        )
    finally:
        if timeout_timer:
            timeout_timer.cancel()
        if previous_alarm_handler is not None:
            signal.setitimer(signal.ITIMER_REAL, 0)
            signal.signal(signal.SIGALRM, previous_alarm_handler)
        heartbeat_stop.set()
        if heartbeat_thread:
            heartbeat_thread.join(timeout=2)
        if status != "success":
            try:
                context.close_reference_outputs(status)
            except Exception as exc:
                _diagnostic(
                    f"REFERENCE 输出流 ABORT 发送失败: {exc}",
                    capture.original_stderr_fd,
                )
        if getattr(context, "_signal_report_failure_count", 0):
            context.logger.warning(
                "组件运行期间存在信号上报失败",
                failure_count=context._signal_report_failure_count,
            )
        context.close()
        capture.stop()
        transport.close(timeout=5)
        root.removeHandler(handler)

    if status == "success" and _has_declared_value_result(
        getattr(context, "outputs", {}),
        outputs,
    ):
        context.mark_successful_result()

    finished_at = datetime.now(timezone.utc)
    crawlab_payload = {
        "component_run_id": context.component_run_id,
        "status": status,
        "has_successful_result": bool(
            getattr(context, "has_successful_result", False)
        ),
        "message": error or "运行成功",
        "outputs": json.dumps(outputs, ensure_ascii=False),
        "created_at": started_at.isoformat(),
        "finished_at": finished_at.isoformat(),
    }
    try:
        # TODO(native-scheduler): 自研 Worker 上线后删除此临时 Crawlab 结果提交。
        save_item(crawlab_payload)
    except Exception as exc:
        _diagnostic(f"Crawlab 临时结果提交失败（不影响 CSI 结果）: {exc}", capture.original_stderr_fd)

    result_payload = {
        "result_id": str(uuid.uuid4()),
        "attempt": context.attempt,
        "status": status,
        "outputs": outputs,
        "has_successful_result": bool(
            getattr(context, "has_successful_result", False)
        ),
        "error": error,
        "exit_code": exit_code,
    }
    try:
        backend.submit_result(result_payload)
    except Exception as exc:
        _diagnostic(str(exc), capture.original_stderr_fd)
        exit_code = 1
    backend.close()
    capture.close_original_fds()
    return exit_code


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="csi-component")
    subparsers = parser.add_subparsers(dest="command", required=True)
    run_parser = subparsers.add_parser("run", help="运行基础组件")
    run_parser.add_argument("entrypoint", help="组件入口，格式为 module:function")
    run_parser.add_argument("--api-base-url", default=os.getenv("API_BASE_URL"))
    run_parser.add_argument("--component-run-id", default=os.getenv("COMPONENT_RUN_ID"))
    run_parser.add_argument("--component-bootstrap", default=os.getenv("COMPONENT_BOOTSTRAP"))
    run_parser.add_argument("--local-config")
    return parser


def main() -> None:
    args = build_parser().parse_args()
    if args.command == "run":
        raise SystemExit(run_component(args))


if __name__ == "__main__":
    main()
