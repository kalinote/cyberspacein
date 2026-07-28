"""Reference 父子运行时桥接服务测试。"""

from datetime import datetime, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from app.db import rabbitmq
from app.models import get_all_models
from app.models.action.reference_bridge import (
    ReferenceBridgeDirectionEnum,
    ReferenceBridgeModel,
    ReferenceBridgeStatusEnum,
)
from app.schemas.action.reference import (
    REFERENCE_ABORT_TYPE,
    REFERENCE_EOS_TYPE,
    ReferenceQueueBinding,
    ReferenceStreamDescriptor,
)
from app.service.reference_bridge import (
    ReferenceBridgeService,
    ReferenceBridgeStepResult,
)


def _stream(
    stream_id: str,
    queue_name: str,
    owner_action_id: str,
    producers: list[str] | None = None,
) -> ReferenceStreamDescriptor:
    return ReferenceStreamDescriptor(
        stream_id=stream_id,
        queue_name=queue_name,
        owner_action_id=owner_action_id,
        expected_producer_ids=producers or [],
    )


def _bridge(
    *,
    sources: list[ReferenceStreamDescriptor] | None = None,
    destinations: list[ReferenceStreamDescriptor] | None = None,
) -> ReferenceBridgeModel:
    return ReferenceBridgeModel.model_construct(
        id="bridge-1",
        parent_action_id="parent-1",
        child_action_id="child-1",
        parent_node_instance_id="node-d",
        public_port_id="data",
        direction=ReferenceBridgeDirectionEnum.EGRESS,
        sources=sources or [_stream("source-1", "child-q", "child-1", ["run-1"])],
        destinations=destinations
        or [_stream("target-1", "parent-q", "parent-1", ["bridge:bridge-1"])],
        status=ReferenceBridgeStatusEnum.RUNNING,
        worker_id="worker-1",
        lease_token="lease-1",
        lease_expires_at=datetime.now() + timedelta(minutes=1),
    )


class _FakeDelivery:
    def __init__(self, message, events: list[str]):
        self.message = message
        self.events = events

    async def ack(self):
        self.events.append("ack")
        self.message.processed = True

    async def nack(self, *, requeue=True):
        self.events.append(f"nack:{requeue}")
        self.message.processed = True

    async def close(self):
        self.events.append("close")


def _message(
    *,
    message_type: str | None = None,
    stream_id: str | None = None,
    producer_id: str | None = None,
    body: bytes = b'{"value": 1}',
):
    headers = {}
    if stream_id:
        headers["x-csi-stream-id"] = stream_id
    if producer_id:
        headers["x-csi-producer-id"] = producer_id
    return SimpleNamespace(
        body=body,
        headers=headers,
        type=message_type,
        content_type="application/json",
        content_encoding="utf-8",
        delivery_mode=2,
        priority=3,
        correlation_id="correlation-1",
        reply_to="reply",
        expiration=None,
        message_id="message-1",
        timestamp=None,
        user_id=None,
        app_id="test",
        processed=False,
    )


def test_reference_binding_deduplicates_expected_producers():
    binding = ReferenceQueueBinding(
        edge_id="edge-1",
        stream_id="stream-1",
        queue_name="queue-1",
        owner_action_id="action-1",
        source_node_id="source",
        source_port_id="out",
        target_node_id="target",
        target_port_id="in",
        expected_producer_ids=["run-1", "run-1", "run-2"],
    )
    assert binding.expected_producer_ids == ["run-1", "run-2"]


def test_reference_bridge_model_is_registered():
    assert ReferenceBridgeModel in get_all_models()


def test_reference_control_is_identified_only_from_properties():
    business_message = _message(body=b'{"type": "csi.reference.eos.v1"}')
    eos_message = _message(
        message_type=REFERENCE_EOS_TYPE,
        stream_id="stream-1",
        producer_id="run-1",
    )
    abort_message = _message(
        message_type=REFERENCE_ABORT_TYPE,
        stream_id="stream-1",
        producer_id="run-1",
    )

    assert rabbitmq.get_reference_control_kind(business_message) is None
    assert rabbitmq.get_reference_control_kind(eos_message) == "eos"
    assert rabbitmq.get_reference_control_kind(abort_message) == "abort"
    assert rabbitmq.get_reference_control_identity(eos_message) == (
        "stream-1",
        "run-1",
    )


@pytest.mark.asyncio
async def test_transport_rejects_negative_publisher_confirm():
    channel = SimpleNamespace(
        declare_queue=AsyncMock(),
        default_exchange=SimpleNamespace(publish=AsyncMock(return_value=False)),
    )
    delivery = rabbitmq.ReferenceMessageDelivery(
        channel=channel,
        message=_message(),
    )

    with pytest.raises(RuntimeError, match="发布未获确认"):
        await rabbitmq.publish_reference_delivery(delivery, ["target-q"])


@pytest.mark.asyncio
async def test_data_is_published_before_source_ack(monkeypatch):
    events: list[str] = []
    delivery = _FakeDelivery(_message(), events)
    bridge = _bridge()

    monkeypatch.setattr(
        ReferenceBridgeService,
        "_get_owned_bridge",
        AsyncMock(return_value=bridge),
    )
    monkeypatch.setattr(
        rabbitmq,
        "get_reference_message",
        AsyncMock(return_value=delivery),
    )

    async def _publish(_delivery, queues):
        assert queues == ["parent-q"]
        events.append("confirmed")

    async def _record(**_kwargs):
        events.append("recorded")

    monkeypatch.setattr(rabbitmq, "publish_reference_delivery", _publish)
    monkeypatch.setattr(ReferenceBridgeService, "_record_forwarded", _record)

    result = await ReferenceBridgeService.process_once(
        bridge_id=bridge.id,
        worker_id="worker-1",
        lease_token="lease-1",
    )

    assert result == ReferenceBridgeStepResult.FORWARDED
    assert events == ["confirmed", "ack", "recorded", "close"]


@pytest.mark.asyncio
async def test_publish_failure_requeues_source_message(monkeypatch):
    events: list[str] = []
    delivery = _FakeDelivery(_message(), events)
    bridge = _bridge()

    monkeypatch.setattr(
        ReferenceBridgeService,
        "_get_owned_bridge",
        AsyncMock(return_value=bridge),
    )
    monkeypatch.setattr(
        rabbitmq,
        "get_reference_message",
        AsyncMock(return_value=delivery),
    )
    monkeypatch.setattr(
        rabbitmq,
        "publish_reference_delivery",
        AsyncMock(side_effect=RuntimeError("confirm失败")),
    )

    with pytest.raises(RuntimeError, match="confirm失败"):
        await ReferenceBridgeService.process_once(
            bridge_id=bridge.id,
            worker_id="worker-1",
            lease_token="lease-1",
        )

    assert events == ["nack:True", "close"]


@pytest.mark.asyncio
async def test_abort_is_persisted_before_source_ack(monkeypatch):
    events: list[str] = []
    delivery = _FakeDelivery(
        _message(
            message_type=REFERENCE_ABORT_TYPE,
            stream_id="source-1",
            producer_id="run-1",
        ),
        events,
    )
    bridge = _bridge()
    monkeypatch.setattr(
        ReferenceBridgeService,
        "_get_owned_bridge",
        AsyncMock(return_value=bridge),
    )
    monkeypatch.setattr(
        rabbitmq,
        "get_reference_message",
        AsyncMock(return_value=delivery),
    )

    async def _propagate(**_kwargs):
        events.append("propagated")

    async def _fail(**_kwargs):
        events.append("persisted")
        return True

    monkeypatch.setattr(ReferenceBridgeService, "_propagate_abort", _propagate)
    monkeypatch.setattr(ReferenceBridgeService, "_fail", _fail)

    result = await ReferenceBridgeService.process_once(
        bridge_id=bridge.id,
        worker_id="worker-1",
        lease_token="lease-1",
    )

    assert result == ReferenceBridgeStepResult.FAILED
    assert events == ["propagated", "persisted", "ack", "close"]


@pytest.mark.asyncio
async def test_abort_requeues_when_terminal_state_cannot_be_persisted(monkeypatch):
    events: list[str] = []
    delivery = _FakeDelivery(
        _message(
            message_type=REFERENCE_ABORT_TYPE,
            stream_id="source-1",
            producer_id="run-1",
        ),
        events,
    )
    bridge = _bridge()
    monkeypatch.setattr(
        ReferenceBridgeService,
        "_get_owned_bridge",
        AsyncMock(return_value=bridge),
    )
    monkeypatch.setattr(
        rabbitmq,
        "get_reference_message",
        AsyncMock(return_value=delivery),
    )
    monkeypatch.setattr(
        ReferenceBridgeService,
        "_propagate_abort",
        AsyncMock(),
    )
    monkeypatch.setattr(
        ReferenceBridgeService,
        "_fail",
        AsyncMock(return_value=False),
    )

    result = await ReferenceBridgeService.process_once(
        bridge_id=bridge.id,
        worker_id="worker-1",
        lease_token="lease-1",
    )

    assert result == ReferenceBridgeStepResult.LEASE_LOST
    assert events == ["nack:True", "close"]


def test_eos_requires_all_declared_producers_and_sources():
    bridge = _bridge(
        sources=[
            _stream("source-a", "qa", "child-1", ["run-1", "run-2"]),
            _stream("source-b", "qb", "child-1", ["run-3"]),
        ]
    )
    bridge.received_eos_keys = [
        ReferenceBridgeService._control_key("source-a", "run-1"),
        ReferenceBridgeService._control_key("source-a", "run-2"),
    ]
    assert ReferenceBridgeService._ended_stream_ids(bridge) == {"source-a"}
    assert ReferenceBridgeService._all_sources_ended(bridge) is False

    bridge.received_eos_keys.append(
        ReferenceBridgeService._control_key("source-b", "run-3")
    )
    assert ReferenceBridgeService._all_sources_ended(bridge) is True


@pytest.mark.asyncio
async def test_complete_publishes_one_aggregate_eos_per_destination(monkeypatch):
    bridge = _bridge(
        destinations=[
            _stream("parent-a", "parent-qa", "parent-1"),
            _stream("parent-b", "parent-qb", "parent-1"),
        ]
    )
    bridge.received_eos_keys = [
        ReferenceBridgeService._control_key("source-1", "run-1")
    ]
    publish = AsyncMock()
    monkeypatch.setattr(rabbitmq, "publish_reference_control", publish)

    collection = SimpleNamespace(
        update_one=AsyncMock(return_value=SimpleNamespace(modified_count=1))
    )
    monkeypatch.setattr(
        ReferenceBridgeModel,
        "get_motor_collection",
        classmethod(lambda cls: collection),
    )

    result = await ReferenceBridgeService._complete(
        bridge=bridge,
        worker_id="worker-1",
        lease_token="lease-1",
    )

    assert result == ReferenceBridgeStepResult.COMPLETED
    assert publish.await_count == 2
    assert {
        call.kwargs["stream_id"] for call in publish.await_args_list
    } == {"parent-a", "parent-b"}
    assert all(
        call.kwargs["producer_id"] == "bridge:bridge-1"
        for call in publish.await_args_list
    )


@pytest.mark.asyncio
async def test_complete_uses_destination_expected_producer_identity(monkeypatch):
    bridge = _bridge(
        destinations=[
            _stream(
                "parent-a",
                "parent-qa",
                "parent-1",
                ["encapsulated-node-run"],
            )
        ]
    )
    bridge.received_eos_keys = [
        ReferenceBridgeService._control_key("source-1", "run-1")
    ]
    publish = AsyncMock()
    monkeypatch.setattr(rabbitmq, "publish_reference_control", publish)
    collection = SimpleNamespace(
        update_one=AsyncMock(return_value=SimpleNamespace(modified_count=1))
    )
    monkeypatch.setattr(
        ReferenceBridgeModel,
        "get_motor_collection",
        classmethod(lambda cls: collection),
    )

    await ReferenceBridgeService._complete(
        bridge=bridge,
        worker_id="worker-1",
        lease_token="lease-1",
    )

    assert publish.await_args.kwargs["producer_id"] == "encapsulated-node-run"


@pytest.mark.asyncio
async def test_cleanup_owner_never_deletes_parent_queue(monkeypatch):
    bridge = _bridge()
    query = SimpleNamespace(to_list=AsyncMock(return_value=[bridge]))
    monkeypatch.setattr(
        ReferenceBridgeModel,
        "find",
        classmethod(lambda cls, _query: query),
    )
    delete_owned = AsyncMock(return_value=["child-q"])
    monkeypatch.setattr(rabbitmq, "delete_owned_queues", delete_owned)

    deleted = await ReferenceBridgeService.cleanup_owner_queues("child-1")

    assert deleted == ["child-q"]
    streams = delete_owned.await_args.args[1]
    assert [stream.queue_name for stream in streams] == ["child-q"]


@pytest.mark.asyncio
async def test_claim_uses_expired_lease_filter_and_returns_fencing_token(
    monkeypatch,
):
    raw = _bridge().model_dump(mode="python", by_alias=True)
    raw["lease_token"] = "new-token"
    collection = SimpleNamespace(find_one_and_update=AsyncMock(return_value=raw))
    monkeypatch.setattr(
        ReferenceBridgeModel,
        "get_motor_collection",
        classmethod(lambda cls: collection),
    )
    monkeypatch.setattr(
        "app.service.reference_bridge.uuid.uuid4",
        lambda: "new-token",
    )

    claimed = await ReferenceBridgeService.claim(
        worker_id="worker-2",
        bridge_id="bridge-1",
    )

    assert claimed is not None
    query = collection.find_one_and_update.await_args.args[0]
    assert query["_id"] == "bridge-1"
    assert {"lease_expires_at": {"$lte": query["$or"][2]["lease_expires_at"]["$lte"]}} in query[
        "$or"
    ]
    update = collection.find_one_and_update.await_args.args[1]
    assert update["$set"]["lease_token"] == "new-token"


@pytest.mark.asyncio
async def test_worker_error_releases_lease_for_recovery(monkeypatch):
    monkeypatch.setattr(
        ReferenceBridgeService,
        "renew_lease",
        AsyncMock(return_value=True),
    )
    monkeypatch.setattr(
        ReferenceBridgeService,
        "process_once",
        AsyncMock(side_effect=RuntimeError("RabbitMQ暂时不可用")),
    )
    collection = SimpleNamespace(
        update_one=AsyncMock(return_value=SimpleNamespace(modified_count=1))
    )
    monkeypatch.setattr(
        ReferenceBridgeModel,
        "get_motor_collection",
        classmethod(lambda cls: collection),
    )

    with pytest.raises(RuntimeError, match="RabbitMQ暂时不可用"):
        await ReferenceBridgeService.run_claimed(
            bridge_id="bridge-1",
            worker_id="worker-1",
            lease_token="lease-1",
        )

    update = collection.update_one.await_args.args[1]["$set"]
    assert update["last_error"] == "RabbitMQ暂时不可用"
    assert update["lease_expires_at"] <= datetime.now() + timedelta(seconds=2)


@pytest.mark.asyncio
async def test_cancel_is_idempotent(monkeypatch):
    collection = SimpleNamespace(
        update_one=AsyncMock(
            side_effect=[
                SimpleNamespace(modified_count=1),
                SimpleNamespace(modified_count=0),
            ]
        )
    )
    monkeypatch.setattr(
        ReferenceBridgeModel,
        "get_motor_collection",
        classmethod(lambda cls: collection),
    )
    monkeypatch.setattr(
        ReferenceBridgeModel,
        "find_one",
        AsyncMock(
            return_value=ReferenceBridgeModel.model_construct(
                id="bridge-1",
                status=ReferenceBridgeStatusEnum.CANCELLED,
            )
        ),
    )

    assert await ReferenceBridgeService.cancel("bridge-1") is True
    assert await ReferenceBridgeService.cancel("bridge-1") is True
