from __future__ import annotations

import asyncio
from datetime import datetime, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from app.db import rabbitmq
from app.models.action.debug_output_run import (
    DebugOutputDesiredStateEnum,
    DebugOutputInputEdgeModel,
    DebugOutputRunModel,
    DebugOutputRunStatusEnum,
)
from app.models.action.node_execution import ActionNodeExecutionModel
from app.schemas.action.reference import ReferenceStreamDescriptor
from app.schemas.action.reference import REFERENCE_ABORT_TYPE
from app.schemas.action.reference import REFERENCE_EOS_TYPE
from app.schemas.action.execution import (
    NodeExecutionContext,
    NodeExecutionSpec,
    NodeIncomingEdge,
)
from app.schemas.constants import ActionExecutionDriverEnum
from app.service.action.log import ActionLogService
from app.service.debug_output_runtime import (
    DEBUG_OUTPUT_LOG_WRITE_ATTEMPTS,
    DEBUG_OUTPUT_PREVIEW_BYTES,
    DebugOutputLeaseLostError,
    DebugOutputLogWriteError,
    DebugOutputRuntimeService,
    DebugOutputRuntimeWorker,
    build_reference_preview,
    build_value_preview,
)
from app.service.native_nodes.debug_output import DebugOutputNodeHandler


def _value_edge(edge_id: str = "edge-value") -> DebugOutputInputEdgeModel:
    return DebugOutputInputEdgeModel(
        edge_id=edge_id,
        data_type="value",
        source_node_id="source-node",
        source_port_id="source-value",
        target_port_id="data-in",
        value_slot=f"slot-{edge_id}",
    )


def _reference_edge(
    edge_id: str = "edge-reference",
    *,
    producers: list[str] | None = None,
) -> DebugOutputInputEdgeModel:
    return DebugOutputInputEdgeModel(
        edge_id=edge_id,
        data_type="reference",
        source_node_id="source-node",
        source_port_id="source-reference",
        target_port_id="data-in",
        reference_stream=ReferenceStreamDescriptor(
            stream_id=f"stream-{edge_id}",
            queue_name=f"queue-{edge_id}",
            owner_action_id="action-1",
            expected_producer_ids=producers or ["producer-1"],
        ),
    )


def _run(**changes) -> DebugOutputRunModel:
    fields = {
        "id": "debug-run-1",
        "action_id": "action-1",
        "node_instance_id": "node-instance-1",
        "node_execution_id": "execution-1",
        "execution_key": "default",
        "incoming_edges": [_value_edge()],
        "status": DebugOutputRunStatusEnum.RUNNING,
        "worker_id": "worker-1",
        "lease_token": "lease-1",
        "lease_expires_at": datetime.now() + timedelta(minutes=1),
    }
    fields.update(changes)
    return DebugOutputRunModel.model_construct(**fields)


def _execution() -> ActionNodeExecutionModel:
    return ActionNodeExecutionModel.model_construct(
        id="execution-1",
        action_id="action-1",
        node_instance_id="node-instance-1",
        driver="backend_native",
        handler="debug.output",
        idempotency_key="idempotency-1",
    )


def _delivery(
    body: bytes,
    *,
    message_id: str | None = "message-1",
    message_type: str | None = None,
    headers: dict | None = None,
):
    events: list[str] = []

    async def ack() -> None:
        events.append("ack")

    async def nack(*, requeue: bool = True) -> None:
        events.append(f"nack:{requeue}")

    return SimpleNamespace(
        message=SimpleNamespace(
            body=body,
            content_type="application/json",
            content_encoding="utf-8",
            message_id=message_id,
            type=message_type,
            headers=headers or {},
            processed=False,
        ),
        ack=AsyncMock(side_effect=ack),
        nack=AsyncMock(side_effect=nack),
        close=AsyncMock(),
        events=events,
    )


def test_run_rejects_duplicate_edges_and_invalid_reference_contract() -> None:
    run = _run(incoming_edges=[_value_edge(), _value_edge()])
    with pytest.raises(ValueError, match="输入边 ID 不能重复"):
        run.validate_edges()

    with pytest.raises(ValueError, match="必须提供 reference_stream"):
        DebugOutputInputEdgeModel(
            edge_id="edge-1",
            data_type="reference",
            source_node_id="source",
            source_port_id="out",
            target_port_id="in",
        )


def test_preview_is_utf8_bounded_and_preserves_payload_digest() -> None:
    value = {"正文": "测试" * 20_000}
    preview = build_value_preview(value)

    assert len(preview.message.encode("utf-8")) <= DEBUG_OUTPUT_PREVIEW_BYTES
    assert preview.truncated is True
    assert preview.content_kind == "json"
    assert preview.original_byte_count > DEBUG_OUTPUT_PREVIEW_BYTES
    assert len(preview.sha256) == 64

    binary = build_reference_preview(
        b"\xff\xfe\x00",
        content_type="application/octet-stream",
        content_encoding="utf-8",
    )
    assert binary.message == "//4A"
    assert binary.content_kind == "base64"


def test_value_preview_falls_back_when_string_conversion_raises() -> None:
    class BrokenString:
        def __str__(self) -> str:
            raise RuntimeError("禁止转换")

    preview = build_value_preview({"broken": BrokenString()})

    assert preview.message == "（数据无法安全序列化）"
    assert preview.content_kind == "unserializable"
    assert preview.truncated is False


@pytest.mark.asyncio
async def test_value_is_logged_before_edge_is_recorded(monkeypatch) -> None:
    run = _run()
    collection = SimpleNamespace(
        update_one=AsyncMock(
            return_value=SimpleNamespace(modified_count=1)
        )
    )
    monkeypatch.setattr(
        DebugOutputRuntimeService,
        "get",
        AsyncMock(return_value=run),
    )
    monkeypatch.setattr(
        DebugOutputRunModel,
        "get_motor_collection",
        classmethod(lambda _cls: collection),
    )
    monkeypatch.setattr(
        ActionNodeExecutionModel,
        "find_one",
        AsyncMock(return_value=_execution()),
    )
    ingest = AsyncMock(return_value=True)
    monkeypatch.setattr(ActionLogService, "ingest_debug_event", ingest)

    accepted = await DebugOutputRuntimeService.observe_value(
        run.id,
        "edge-value",
        {"key": "值"},
    )

    assert accepted is True
    ingest.assert_awaited_once()
    assert ingest.await_args.kwargs["level"] == "DEBUG"
    assert ingest.await_args.kwargs["fields"]["edge_id"] == "edge-value"
    assert ingest.await_args.kwargs["fields"]["data_type"] == "value"
    assert collection.update_one.await_count == 1


@pytest.mark.asyncio
async def test_debug_log_fails_after_three_attempts(monkeypatch) -> None:
    run = _run()
    monkeypatch.setattr(
        ActionNodeExecutionModel,
        "find_one",
        AsyncMock(return_value=_execution()),
    )
    ingest = AsyncMock(return_value=False)
    monkeypatch.setattr(ActionLogService, "ingest_debug_event", ingest)
    monkeypatch.setattr("asyncio.sleep", AsyncMock())

    with pytest.raises(DebugOutputLogWriteError, match="连续3次"):
        await DebugOutputRuntimeService._write_debug_log(
            run,
            event_key="debug:event",
            message="payload",
            fields={},
        )

    assert ingest.await_count == DEBUG_OUTPUT_LOG_WRITE_ATTEMPTS


@pytest.mark.asyncio
async def test_reference_data_is_logged_then_acked(monkeypatch) -> None:
    edge = _reference_edge()
    run = _run(incoming_edges=[edge])
    worker = DebugOutputRuntimeWorker()
    worker.worker_id = "worker-1"
    delivery = _delivery(b'{"name":"example"}')
    events = delivery.events

    async def write_log(*args, **kwargs) -> None:
        events.append("log")

    async def record_data(**kwargs) -> bool:
        events.append("record")
        return True

    monkeypatch.setattr(
        DebugOutputRuntimeService,
        "_write_debug_log",
        write_log,
    )
    monkeypatch.setattr(
        DebugOutputRuntimeService,
        "record_reference_data",
        record_data,
    )
    monkeypatch.setattr(
        DebugOutputRuntimeService,
        "renew_lease",
        AsyncMock(return_value=True),
    )

    ended = await worker._process_reference_delivery(
        run,
        edge,
        delivery,
        "lease-1",
    )

    assert ended is False
    assert events == ["log", "ack", "record"]
    delivery.nack.assert_not_awaited()
    delivery.close.assert_awaited_once()


@pytest.mark.asyncio
async def test_lost_lease_does_not_ack_and_closes_reference_consumer(
    monkeypatch,
) -> None:
    edge = _reference_edge()
    run = _run(incoming_edges=[edge])
    worker = DebugOutputRuntimeWorker()
    worker.worker_id = "worker-1"
    delivery = _delivery(b'{"name":"example"}')
    consumer_closed = AsyncMock()

    class SingleDeliveryConsumer:
        def __init__(self) -> None:
            self.delivered = False

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, traceback) -> None:
            await consumer_closed()

        async def receive(self):
            if self.delivered:
                await asyncio.Future()
            self.delivered = True
            return delivery

    monkeypatch.setattr(
        DebugOutputRuntimeService,
        "get_owned",
        AsyncMock(return_value=run),
    )
    monkeypatch.setattr(
        DebugOutputRuntimeService,
        "_write_debug_log",
        AsyncMock(),
    )
    monkeypatch.setattr(
        DebugOutputRuntimeService,
        "renew_lease",
        AsyncMock(return_value=False),
    )
    record_data = AsyncMock(return_value=True)
    monkeypatch.setattr(
        DebugOutputRuntimeService,
        "record_reference_data",
        record_data,
    )
    monkeypatch.setattr(
        rabbitmq,
        "open_reference_consumer",
        AsyncMock(return_value=SingleDeliveryConsumer()),
    )

    with pytest.raises(DebugOutputLeaseLostError, match="确认.*前"):
        await worker._consume_reference_edge(run, edge, "lease-1")

    delivery.ack.assert_not_awaited()
    delivery.nack.assert_not_awaited()
    delivery.close.assert_awaited_once()
    consumer_closed.assert_awaited_once()
    record_data.assert_not_awaited()


@pytest.mark.asyncio
async def test_reference_consumer_waits_then_processes_data(monkeypatch) -> None:
    edge = _reference_edge()
    run = _run(incoming_edges=[edge])
    control_key = (
        f"{edge.edge_id}\x1f{edge.reference_stream.stream_id}\x1fproducer-1"
    )
    ended_run = _run(
        incoming_edges=[edge],
        received_eos_keys=[control_key],
    )
    worker = DebugOutputRuntimeWorker()
    worker.worker_id = "worker-1"
    data_delivery = _delivery(b'{"name":"late"}')
    eos_delivery = _delivery(
        b"{}",
        message_id="eos-message",
        message_type=REFERENCE_EOS_TYPE,
        headers={
            "x-csi-stream-id": edge.reference_stream.stream_id,
            "x-csi-producer-id": "producer-1",
        },
    )
    waiting = asyncio.Event()
    release_data = asyncio.Event()
    consumer_closed = AsyncMock()

    class DelayedConsumer:
        def __init__(self) -> None:
            self.index = 0

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, traceback) -> None:
            await consumer_closed()

        async def receive(self):
            if self.index == 0:
                waiting.set()
                await release_data.wait()
                self.index += 1
                return data_delivery
            self.index += 1
            return eos_delivery

    monkeypatch.setattr(
        DebugOutputRuntimeService,
        "get_owned",
        AsyncMock(return_value=run),
    )
    write_log = AsyncMock()
    monkeypatch.setattr(
        DebugOutputRuntimeService,
        "_write_debug_log",
        write_log,
    )
    monkeypatch.setattr(
        DebugOutputRuntimeService,
        "renew_lease",
        AsyncMock(return_value=True),
    )
    monkeypatch.setattr(
        DebugOutputRuntimeService,
        "record_reference_data",
        AsyncMock(return_value=True),
    )
    monkeypatch.setattr(
        DebugOutputRuntimeService,
        "record_control",
        AsyncMock(return_value=(ended_run, True)),
    )
    open_consumer = AsyncMock(return_value=DelayedConsumer())
    monkeypatch.setattr(
        rabbitmq,
        "open_reference_consumer",
        open_consumer,
    )

    consume_task = asyncio.create_task(
        worker._consume_reference_edge(run, edge, "lease-1")
    )
    await asyncio.wait_for(waiting.wait(), timeout=1)
    await asyncio.sleep(0)

    assert consume_task.done() is False
    write_log.assert_not_awaited()

    release_data.set()
    await asyncio.wait_for(consume_task, timeout=1)

    open_consumer.assert_awaited_once_with(
        edge.reference_stream.queue_name,
        prefetch_count=1,
    )
    data_delivery.ack.assert_awaited_once()
    eos_delivery.ack.assert_awaited_once()
    consumer_closed.assert_awaited_once()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("desired_state", "mark_paused_result", "expected_transition"),
    [
        (DebugOutputDesiredStateEnum.PAUSED, True, "paused"),
        (DebugOutputDesiredStateEnum.PAUSED, False, "resumed"),
        (DebugOutputDesiredStateEnum.CANCELLED, True, "cancelled"),
    ],
)
async def test_control_transition_closes_active_reference_consumer(
    monkeypatch,
    desired_state: DebugOutputDesiredStateEnum,
    mark_paused_result: bool,
    expected_transition: str,
) -> None:
    edge = _reference_edge()
    run = _run(incoming_edges=[edge])
    controlled_run = _run(
        incoming_edges=[edge],
        desired_state=desired_state,
        requested_reason="测试控制",
    )
    worker = DebugOutputRuntimeWorker(
        poll_seconds=0.05,
        heartbeat_seconds=10,
    )
    worker.worker_id = "worker-1"
    consumer_waiting = asyncio.Event()
    consumer_closed = AsyncMock()

    class BlockingConsumer:
        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, traceback) -> None:
            await consumer_closed()

        async def receive(self):
            consumer_waiting.set()
            await asyncio.Future()

    async def get_controlled_run(run_id: str):
        await consumer_waiting.wait()
        return controlled_run

    monkeypatch.setattr(
        rabbitmq,
        "open_reference_consumer",
        AsyncMock(return_value=BlockingConsumer()),
    )
    monkeypatch.setattr(
        DebugOutputRuntimeService,
        "get",
        AsyncMock(side_effect=get_controlled_run),
    )
    monkeypatch.setattr(
        DebugOutputRuntimeService,
        "get_owned",
        AsyncMock(return_value=run),
    )
    mark_paused = AsyncMock(return_value=mark_paused_result)
    release_lease = AsyncMock(return_value=True)
    finish = AsyncMock(return_value=True)
    monkeypatch.setattr(
        DebugOutputRuntimeService,
        "mark_paused",
        mark_paused,
    )
    monkeypatch.setattr(
        DebugOutputRuntimeService,
        "release_lease",
        release_lease,
    )
    monkeypatch.setattr(DebugOutputRuntimeService, "finish", finish)

    await asyncio.wait_for(worker._execute_run(run), timeout=2)

    consumer_closed.assert_awaited_once()
    if expected_transition == "paused":
        mark_paused.assert_awaited_once()
        release_lease.assert_not_awaited()
        finish.assert_not_awaited()
    elif expected_transition == "resumed":
        mark_paused.assert_awaited_once()
        release_lease.assert_awaited_once()
        finish.assert_not_awaited()
    else:
        mark_paused.assert_not_awaited()
        release_lease.assert_not_awaited()
        finish.assert_awaited_once()
        assert (
            finish.await_args.kwargs["status"]
            == DebugOutputRunStatusEnum.CANCELLED
        )


@pytest.mark.asyncio
async def test_reference_log_failure_requeues_and_fails_run(monkeypatch) -> None:
    edge = _reference_edge()
    run = _run(incoming_edges=[edge])
    worker = DebugOutputRuntimeWorker()
    worker.worker_id = "worker-1"
    delivery = _delivery(b"payload")
    monkeypatch.setattr(
        DebugOutputRuntimeService,
        "_write_debug_log",
        AsyncMock(side_effect=DebugOutputLogWriteError("写入失败")),
    )
    monkeypatch.setattr(
        worker,
        "_fail_owned",
        AsyncMock(return_value=True),
    )

    with pytest.raises(RuntimeError, match="写入失败"):
        await worker._process_reference_delivery(
            run,
            edge,
            delivery,
            "lease-1",
        )

    delivery.nack.assert_awaited_once_with(requeue=True)
    delivery.ack.assert_not_awaited()


def test_reference_edge_collects_eos_and_abort_from_all_producers() -> None:
    edge = _reference_edge(producers=["producer-1", "producer-2"])
    prefix = f"{edge.edge_id}\x1f{edge.reference_stream.stream_id}\x1f"
    partial = _run(
        incoming_edges=[edge],
        received_eos_keys=[f"{prefix}producer-1"],
    )
    completed = _run(
        incoming_edges=[edge],
        received_eos_keys=[f"{prefix}producer-1"],
        received_abort_keys=[f"{prefix}producer-2"],
        warning_count=1,
    )

    assert DebugOutputRuntimeWorker._edge_ended(partial, edge) is False
    assert DebugOutputRuntimeWorker._edge_ended(completed, edge) is True
    assert DebugOutputRuntimeWorker._all_inputs_ended(completed) is True


@pytest.mark.asyncio
async def test_abort_control_is_persisted_and_logged_before_ack(monkeypatch) -> None:
    edge = _reference_edge()
    run = _run(incoming_edges=[edge])
    worker = DebugOutputRuntimeWorker()
    worker.worker_id = "worker-1"
    delivery = _delivery(
        '{"reason":"上游失败"}'.encode("utf-8"),
        message_id="abort-message",
        message_type=REFERENCE_ABORT_TYPE,
        headers={
            "x-csi-stream-id": edge.reference_stream.stream_id,
            "x-csi-producer-id": "producer-1",
        },
    )
    events = delivery.events
    updated = _run(
        incoming_edges=[edge],
        received_abort_keys=[
            f"{edge.edge_id}\x1f{edge.reference_stream.stream_id}"
            "\x1fproducer-1"
        ],
        warning_count=1,
    )

    async def record_control(**kwargs):
        events.append("record-control")
        return updated, True

    async def log_warning(*args, **kwargs):
        events.append("log-warning")

    monkeypatch.setattr(
        DebugOutputRuntimeService,
        "record_control",
        record_control,
    )
    monkeypatch.setattr(worker, "_log_control_warning", log_warning)

    ended = await worker._process_reference_control(
        run,
        edge,
        delivery,
        "lease-1",
        "abort",
    )

    assert ended is True
    assert events == ["record-control", "log-warning", "ack"]
    delivery.nack.assert_not_awaited()


@pytest.mark.asyncio
async def test_persistent_delivery_does_not_close_shared_channel() -> None:
    channel = SimpleNamespace(is_closed=False, close=AsyncMock())
    message = SimpleNamespace(ack=AsyncMock(), nack=AsyncMock())
    delivery = rabbitmq.ReferenceMessageDelivery(
        channel=channel,
        message=message,
        owns_channel=False,
    )

    await delivery.close()

    channel.close.assert_not_awaited()


@pytest.mark.asyncio
async def test_empty_run_writes_summary_and_completes(monkeypatch) -> None:
    run = _run(incoming_edges=[])
    worker = DebugOutputRuntimeWorker()
    worker.worker_id = "worker-1"
    monkeypatch.setattr(
        DebugOutputRuntimeService,
        "get_owned",
        AsyncMock(return_value=run),
    )
    write_log = AsyncMock()
    monkeypatch.setattr(
        DebugOutputRuntimeService,
        "_write_debug_log",
        write_log,
    )

    outcome = await worker._process_run(run, "lease-1")

    assert outcome.status == DebugOutputRunStatusEnum.COMPLETED
    assert write_log.await_args.kwargs["event_key"] == "debug:summary"


@pytest.mark.asyncio
async def test_native_handler_submits_structured_edge_and_initial_value(
    monkeypatch,
) -> None:
    handler = DebugOutputNodeHandler()
    run = _run(status=DebugOutputRunStatusEnum.PENDING)
    submit = AsyncMock(return_value=run)
    observe = AsyncMock(return_value=True)
    monkeypatch.setattr(DebugOutputRuntimeService, "submit", submit)
    monkeypatch.setattr(DebugOutputRuntimeService, "observe_value", observe)
    context = NodeExecutionContext(
        action_id="action-1",
        node_instance_id="node-instance-1",
        node_id="debug-node",
        execution_id="execution-1",
        debug=True,
        incoming_edges=[
            NodeIncomingEdge(
                edge_id="edge-value",
                source_node_id="source-node",
                source_port_id="source-value",
                target_port_id="data-in",
                data_type="value",
                value_slot="slot-edge-value",
                value_available=True,
                value={"name": "测试"},
            )
        ],
    )
    spec = NodeExecutionSpec(
        driver=ActionExecutionDriverEnum.BACKEND_NATIVE,
        handler="debug.output",
    )

    result = await handler.start(context, spec)

    assert result.state == "running"
    assert result.provider_run_id == run.id
    edge = submit.await_args.kwargs["incoming_edges"][0]
    assert edge.edge_id == "edge-value"
    assert edge.data_type == "value"
    observe.assert_awaited_once_with(
        run.id,
        "edge-value",
        {"name": "测试"},
    )


@pytest.mark.asyncio
async def test_native_handler_restores_value_edge_aborted_before_start(
    monkeypatch,
) -> None:
    run = _run(status=DebugOutputRunStatusEnum.PENDING)
    monkeypatch.setattr(
        DebugOutputRuntimeService,
        "submit",
        AsyncMock(return_value=run),
    )
    abort = AsyncMock(return_value=True)
    observe = AsyncMock(return_value=True)
    monkeypatch.setattr(DebugOutputRuntimeService, "abort_input", abort)
    monkeypatch.setattr(DebugOutputRuntimeService, "observe_value", observe)

    result = await DebugOutputNodeHandler().start(
        NodeExecutionContext(
            action_id="action-1",
            node_instance_id="node-instance-1",
            node_id="debug-node",
            execution_id="execution-1",
            debug=True,
            incoming_edges=[
                NodeIncomingEdge(
                    edge_id="edge-value",
                    source_node_id="source-node",
                    source_port_id="source-value",
                    target_port_id="data-in",
                    data_type="value",
                    aborted=True,
                )
            ],
        ),
        NodeExecutionSpec(
            driver=ActionExecutionDriverEnum.BACKEND_NATIVE,
            handler="debug.output",
        ),
    )

    assert result.state == "running"
    abort.assert_awaited_once_with(
        run.id,
        "edge-value",
        "上游输入边在调试观察节点启动前已经中止",
    )
    observe.assert_not_awaited()


@pytest.mark.asyncio
async def test_resume_reverses_pause_intent_before_worker_settles(
    monkeypatch,
) -> None:
    collection = SimpleNamespace(
        update_one=AsyncMock(
            side_effect=[
                SimpleNamespace(modified_count=0),
                SimpleNamespace(modified_count=1),
            ]
        )
    )
    monkeypatch.setattr(
        DebugOutputRunModel,
        "get_motor_collection",
        classmethod(lambda _cls: collection),
    )

    assert await DebugOutputRuntimeService.resume("debug-run-1") is True
    assert collection.update_one.await_count == 2
    second_filter = collection.update_one.await_args_list[1].args[0]
    assert second_filter["status"] == DebugOutputRunStatusEnum.RUNNING.value


@pytest.mark.asyncio
async def test_lease_renewal_is_fenced_by_running_intent(monkeypatch) -> None:
    collection = SimpleNamespace(
        update_one=AsyncMock(return_value=SimpleNamespace(modified_count=1))
    )
    monkeypatch.setattr(
        DebugOutputRunModel,
        "get_motor_collection",
        classmethod(lambda _cls: collection),
    )

    assert await DebugOutputRuntimeService.renew_lease(
        "debug-run-1",
        "worker-1",
        "lease-1",
    ) is True
    lease_filter = collection.update_one.await_args.args[0]
    assert lease_filter["desired_state"] == (
        DebugOutputDesiredStateEnum.RUNNING.value
    )


@pytest.mark.asyncio
async def test_native_handler_never_starts_runtime_outside_debug_mode(
    monkeypatch,
) -> None:
    submit = AsyncMock()
    monkeypatch.setattr(DebugOutputRuntimeService, "submit", submit)
    result = await DebugOutputNodeHandler().start(
        NodeExecutionContext(
            action_id="action-1",
            node_instance_id="node-instance-1",
            node_id="debug-node",
            execution_id="execution-1",
            debug=False,
        ),
        NodeExecutionSpec(
            driver=ActionExecutionDriverEnum.BACKEND_NATIVE,
            handler="debug.output",
        ),
    )

    assert result.state == "completed"
    assert result.extension_result["reason"] == "非调试运行"
    submit.assert_not_awaited()
