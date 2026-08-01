from __future__ import annotations

import asyncio
from datetime import datetime, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from pymongo.errors import DuplicateKeyError

from app.models.action.entity_content_analysis_run import (
    EntityContentAnalysisDesiredStateEnum,
    EntityContentAnalysisRunModeEnum,
    EntityContentAnalysisRunModel,
    EntityContentAnalysisRunStatusEnum,
)
from app.schemas.action.reference import (
    REFERENCE_ABORT_TYPE,
    REFERENCE_EOS_TYPE,
    ReferenceStreamDescriptor,
)
from app.service.entity_content_analysis import EntityContentAnalysisOutcome
from app.service import entity_content_analysis_runtime as runtime
from app.service.entity_content_analysis_runtime import (
    EntityContentAnalysisRuntimeService,
    EntityContentAnalysisRuntimeWorker,
)


def _stream(
    suffix: str,
    *,
    producers: list[str] | None = None,
) -> ReferenceStreamDescriptor:
    return ReferenceStreamDescriptor(
        stream_id=f"stream-{suffix}",
        queue_name=f"queue-{suffix}",
        owner_action_id="action-1",
        expected_producer_ids=producers or [f"producer-{suffix}"],
    )


def _single_run(**changes) -> EntityContentAnalysisRunModel:
    fields = {
        "id": "run-single",
        "action_id": "action-1",
        "node_instance_id": "node-instance-1",
        "execution_key": "default",
        "model_config_id": "model-1",
        "llm_provider": "openai",
        "mode": EntityContentAnalysisRunModeEnum.SINGLE,
        "single_input": {"clean_content": "待分析内容"},
        "status": EntityContentAnalysisRunStatusEnum.RUNNING,
        "worker_id": "worker-1",
        "lease_token": "lease-1",
        "lease_expires_at": datetime.now() + timedelta(minutes=1),
    }
    fields.update(changes)
    return EntityContentAnalysisRunModel.model_construct(**fields)


def _reference_run(**changes) -> EntityContentAnalysisRunModel:
    fields = {
        "id": "run-reference",
        "action_id": "action-1",
        "node_instance_id": "node-instance-1",
        "execution_key": "default",
        "model_config_id": "model-1",
        "llm_provider": "openai",
        "mode": EntityContentAnalysisRunModeEnum.REFERENCE,
        "source_streams": [_stream("source", producers=["p1", "p2"])],
        "destination_streams": [_stream("destination")],
        "status": EntityContentAnalysisRunStatusEnum.RUNNING,
        "worker_id": "worker-1",
        "lease_token": "lease-1",
        "lease_expires_at": datetime.now() + timedelta(minutes=1),
    }
    fields.update(changes)
    return EntityContentAnalysisRunModel.model_construct(**fields)


def _delivery(
    body: bytes,
    *,
    message_type: str | None = None,
    stream_id: str | None = None,
    producer_id: str | None = None,
):
    headers = {}
    if stream_id:
        headers["x-csi-stream-id"] = stream_id
    if producer_id:
        headers["x-csi-producer-id"] = producer_id
    message = SimpleNamespace(
        body=body,
        type=message_type,
        headers=headers,
        processed=False,
    )
    return SimpleNamespace(
        message=message,
        ack=AsyncMock(),
        nack=AsyncMock(),
        close=AsyncMock(),
    )


def test_run_rejects_mixed_or_incomplete_io_modes() -> None:
    mixed = _single_run(source_streams=[_stream("source")])
    with pytest.raises(ValueError, match="不能配置 Reference"):
        mixed.validate_io_mode()

    incomplete = _reference_run(destination_streams=[])
    with pytest.raises(ValueError, match="至少需要一个目标流"):
        incomplete.validate_io_mode()


@pytest.mark.asyncio
async def test_submit_is_idempotent_for_same_execution_key(
    monkeypatch,
) -> None:
    existing = _single_run(
        id="existing-run",
        status=EntityContentAnalysisRunStatusEnum.PENDING,
        worker_id=None,
        lease_token=None,
        lease_expires_at=None,
        analysis_field="body",
        min_analysis_length=10,
        chunk_size=2000,
        user_prompt_override="关注主体",
        single_input={"body": "内容"},
    )
    monkeypatch.setattr(
        EntityContentAnalysisRunModel,
        "insert",
        AsyncMock(side_effect=DuplicateKeyError("duplicate")),
    )
    monkeypatch.setattr(
        EntityContentAnalysisRunModel,
        "find_one",
        AsyncMock(return_value=existing),
    )
    monkeypatch.setattr(
        EntityContentAnalysisRunModel,
        "get_motor_collection",
        classmethod(lambda _cls: object()),
    )

    submitted = await EntityContentAnalysisRuntimeService.submit(
        "action-1",
        "node-instance-1",
        "default",
        "model-1",
        "openai",
        single_input={"body": "内容"},
        analysis_field="body",
        min_analysis_length=10,
        chunk_size=2000,
        user_prompt_override="关注主体",
    )

    assert submitted is existing


@pytest.mark.asyncio
async def test_claim_recovers_expired_run_with_new_fencing_token(
    monkeypatch,
) -> None:
    claimed = _reference_run(
        worker_id="worker-new",
        lease_token="lease-new",
        attempt=2,
    )
    raw = claimed.model_dump(mode="python", by_alias=True)
    collection = SimpleNamespace(
        find_one_and_update=AsyncMock(return_value=raw)
    )
    monkeypatch.setattr(
        EntityContentAnalysisRunModel,
        "get_motor_collection",
        classmethod(lambda _cls: collection),
    )

    result = await EntityContentAnalysisRuntimeService.claim_next(
        "worker-new",
        lease_seconds=20,
    )

    query = collection.find_one_and_update.await_args.args[0]
    update = collection.find_one_and_update.await_args.args[1]
    assert {
        "status": EntityContentAnalysisRunStatusEnum.RUNNING.value,
        "lease_expires_at": query["$or"][1]["lease_expires_at"],
    } == query["$or"][1]
    assert query["$expr"] == {"$lt": ["$attempt", "$max_attempts"]}
    assert update["$set"]["worker_id"] == "worker-new"
    assert update["$set"]["lease_token"]
    assert result.lease_token == "lease-new"


@pytest.mark.asyncio
async def test_renew_lease_requires_current_fencing_token(
    monkeypatch,
) -> None:
    collection = SimpleNamespace(
        update_one=AsyncMock(
            return_value=SimpleNamespace(modified_count=1)
        )
    )
    monkeypatch.setattr(
        EntityContentAnalysisRunModel,
        "get_motor_collection",
        classmethod(lambda _cls: collection),
    )

    renewed = await EntityContentAnalysisRuntimeService.renew_lease(
        "run-1",
        "worker-1",
        "lease-1",
        lease_seconds=20,
    )

    query = collection.update_one.await_args.args[0]
    assert renewed is True
    assert query["worker_id"] == "worker-1"
    assert query["lease_token"] == "lease-1"
    assert query["lease_expires_at"]["$gt"] <= datetime.now()


@pytest.mark.asyncio
async def test_single_run_uses_explicit_service_outcome(
    monkeypatch,
) -> None:
    analyzer = SimpleNamespace(
        analyze_with_outcome=AsyncMock(
            return_value=EntityContentAnalysisOutcome(
                data={"clean_content": "短文"},
                skipped=True,
                skip_reason="长度不足",
                chunk_count=0,
                analysis_length=2,
            )
        )
    )
    from_model_config = AsyncMock(return_value=analyzer)
    monkeypatch.setattr(
        "app.service.entity_content_analysis."
        "EntityContentAnalysisService.from_model_config",
        from_model_config,
    )
    worker = EntityContentAnalysisRuntimeWorker()
    run = _single_run(
        single_input={"clean_content": "短文"},
        min_analysis_length=50,
    )

    outcome = await worker._process_run(run, "lease-1")

    from_model_config.assert_awaited_once_with("model-1", "openai")
    analyzer.analyze_with_outcome.assert_awaited_once_with(
        {"clean_content": "短文"},
        analysis_field="clean_content",
        min_analysis_length=50,
        chunk_size=8000,
        user_prompt_override=None,
    )
    assert outcome.status == EntityContentAnalysisRunStatusEnum.COMPLETED
    assert outcome.single_output == {"clean_content": "短文"}
    assert outcome.processed_count == 1
    assert outcome.skipped_count == 1


@pytest.mark.asyncio
async def test_monitor_cancels_work_after_persisted_cancel(
    monkeypatch,
) -> None:
    cancelled = _single_run(
        desired_state=EntityContentAnalysisDesiredStateEnum.CANCELLED,
    )
    monkeypatch.setattr(
        EntityContentAnalysisRuntimeService,
        "get",
        AsyncMock(return_value=cancelled),
    )
    worker = EntityContentAnalysisRuntimeWorker(
        poll_seconds=0.1,
        heartbeat_seconds=1,
    )
    worker.worker_id = "worker-1"
    work = asyncio.create_task(asyncio.sleep(10))

    result = await worker._monitor_run("run-single", "lease-1", work)
    await asyncio.gather(work, return_exceptions=True)

    assert result == runtime._MonitorResult.CANCELLED
    assert work.cancelled()


@pytest.mark.asyncio
async def test_reference_data_is_published_before_ack(
    monkeypatch,
) -> None:
    events: list[str] = []
    analyzer = SimpleNamespace(
        analyze_with_outcome=AsyncMock(
            return_value=EntityContentAnalysisOutcome(
                data={
                    "clean_content": "足够长的内容",
                    "keywords": ["关键词"],
                },
                skipped=False,
                skip_reason=None,
                chunk_count=1,
                analysis_length=100,
            )
        )
    )
    delivery = _delivery('{"clean_content":"足够长的内容"}'.encode())

    async def publish(*_args):
        events.append("publish")

    async def ack():
        events.append("ack")

    delivery.ack.side_effect = ack
    monkeypatch.setattr(
        runtime.rabbitmq,
        "publish_reference_json_delivery",
        AsyncMock(side_effect=publish),
    )
    record_processed = AsyncMock(return_value=True)
    monkeypatch.setattr(
        EntityContentAnalysisRuntimeService,
        "record_processed",
        record_processed,
    )
    worker = EntityContentAnalysisRuntimeWorker()
    run = _reference_run(
        destination_streams=[
            _stream("destination-a"),
            _stream("destination-b"),
        ]
    )

    await worker._process_reference_delivery(
        analyzer,
        run,
        run.source_streams[0],
        delivery,
        "lease-1",
    )

    assert events == ["publish", "ack"]
    runtime.rabbitmq.publish_reference_json_delivery.assert_awaited_once_with(
        delivery,
        ["queue-destination-a", "queue-destination-b"],
        {
            "clean_content": "足够长的内容",
            "keywords": ["关键词"],
        },
    )
    record_processed.assert_awaited_once()
    delivery.nack.assert_not_awaited()
    delivery.close.assert_awaited_once()


@pytest.mark.asyncio
async def test_reference_publish_error_nacks_and_keeps_run_retryable(
    monkeypatch,
) -> None:
    analyzer = SimpleNamespace(
        analyze_with_outcome=AsyncMock(
            return_value=EntityContentAnalysisOutcome(
                data={"clean_content": "处理结果"},
                skipped=False,
                skip_reason=None,
                chunk_count=1,
                analysis_length=100,
            )
        )
    )
    delivery = _delivery('{"clean_content":"原文"}'.encode())
    monkeypatch.setattr(
        runtime.rabbitmq,
        "publish_reference_json_delivery",
        AsyncMock(side_effect=RuntimeError("RabbitMQ 暂时不可用")),
    )
    transient = AsyncMock(return_value=True)
    monkeypatch.setattr(
        EntityContentAnalysisRuntimeService,
        "set_transient_error",
        transient,
    )
    worker = EntityContentAnalysisRuntimeWorker(poll_seconds=0.1)
    run = _reference_run()

    await worker._process_reference_delivery(
        analyzer,
        run,
        run.source_streams[0],
        delivery,
        "lease-1",
    )

    delivery.nack.assert_awaited_once_with(requeue=True)
    delivery.ack.assert_not_awaited()
    transient.assert_awaited_once()
    delivery.close.assert_awaited_once()


@pytest.mark.asyncio
async def test_bad_reference_json_fails_and_discards_delivery(
    monkeypatch,
) -> None:
    finish = AsyncMock(return_value=True)
    monkeypatch.setattr(
        EntityContentAnalysisRuntimeService,
        "finish",
        finish,
    )
    worker = EntityContentAnalysisRuntimeWorker()
    run = _reference_run()
    delivery = _delivery(b"not-json")

    with pytest.raises(runtime._RunAlreadySettled):
        await worker._process_reference_delivery(
            SimpleNamespace(),
            run,
            run.source_streams[0],
            delivery,
            "lease-1",
        )

    assert (
        finish.await_args.kwargs["status"]
        == EntityContentAnalysisRunStatusEnum.FAILED
    )
    delivery.nack.assert_awaited_once_with(requeue=False)
    delivery.close.assert_awaited_once()


@pytest.mark.asyncio
async def test_unknown_eos_producer_fails_deterministically(
    monkeypatch,
) -> None:
    finish = AsyncMock(return_value=True)
    monkeypatch.setattr(
        EntityContentAnalysisRuntimeService,
        "finish",
        finish,
    )
    worker = EntityContentAnalysisRuntimeWorker()
    run = _reference_run()
    delivery = _delivery(
        b"{}",
        message_type=REFERENCE_EOS_TYPE,
        stream_id="stream-source",
        producer_id="unknown",
    )

    with pytest.raises(runtime._RunAlreadySettled):
        await worker._process_reference_delivery(
            SimpleNamespace(),
            run,
            run.source_streams[0],
            delivery,
            "lease-1",
        )

    assert "未声明的生产者" in finish.await_args.kwargs["error_message"]
    delivery.nack.assert_awaited_once_with(requeue=False)


@pytest.mark.asyncio
async def test_abort_is_persisted_before_ack(monkeypatch) -> None:
    events: list[str] = []

    async def finish(**_kwargs):
        events.append("finish")
        return True

    async def ack():
        events.append("ack")

    monkeypatch.setattr(
        EntityContentAnalysisRuntimeService,
        "finish",
        AsyncMock(side_effect=finish),
    )
    worker = EntityContentAnalysisRuntimeWorker()
    run = _reference_run()
    delivery = _delivery(
        b"{}",
        message_type=REFERENCE_ABORT_TYPE,
        stream_id="stream-source",
        producer_id="p1",
    )
    delivery.ack.side_effect = ack

    with pytest.raises(runtime._RunAlreadySettled):
        await worker._process_reference_delivery(
            SimpleNamespace(),
            run,
            run.source_streams[0],
            delivery,
            "lease-1",
        )

    assert events == ["finish", "ack"]
    assert (
        EntityContentAnalysisRuntimeService.finish.await_args.kwargs[
            "abort_key"
        ]
        == "stream-source\x1fp1"
    )


def test_eos_requires_every_declared_producer() -> None:
    run = _reference_run(received_eos_keys=["stream-source\x1fp1"])

    assert not EntityContentAnalysisRuntimeWorker._all_sources_ended(run)

    run.received_eos_keys.append("stream-source\x1fp2")

    assert EntityContentAnalysisRuntimeWorker._all_sources_ended(run)
