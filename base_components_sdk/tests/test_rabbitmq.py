"""RabbitMQ 队列和 REFERENCE EOS 协议测试。"""

from types import SimpleNamespace
from unittest.mock import MagicMock

import pika
import pytest

from csi_base_component_sdk.rabbitmq import (
    REFERENCE_ABORT_TYPE,
    REFERENCE_CONTROL_CONTENT_TYPE,
    REFERENCE_EOS_TYPE,
    RabbitMQClient,
    ReferenceStreamAborted,
)


def _delivery(tag: int):
    return SimpleNamespace(
        delivery_tag=tag,
        exchange="",
        routing_key="queue-1",
        redelivered=False,
    )


def _properties(message_type=None, producer_id=None):
    return SimpleNamespace(
        type=message_type,
        headers=(
            {"x-csi-producer-id": producer_id}
            if producer_id is not None
            else {}
        ),
    )


def _connected_client() -> RabbitMQClient:
    client = RabbitMQClient()
    client.connection = SimpleNamespace(
        is_closed=False,
        process_data_events=MagicMock(),
    )
    client.channel = MagicMock(is_closed=False)
    return client


def test_connect_enables_publisher_confirms(monkeypatch):
    channel = MagicMock()
    connection = MagicMock()
    connection.channel.return_value = channel
    monkeypatch.setattr(
        "csi_base_component_sdk.rabbitmq.pika.BlockingConnection",
        MagicMock(return_value=connection),
    )

    client = RabbitMQClient()

    assert client.connect() is True
    channel.confirm_delivery.assert_called_once_with()


def test_reference_queue_has_no_auto_delete_or_expiration():
    client = _connected_client()

    assert client.send_message("queue-1", {"value": 1}) is True

    client.channel.queue_declare.assert_called_once_with(
        queue="queue-1",
        durable=True,
        exclusive=False,
        auto_delete=False,
        arguments={},
    )


def test_unregistered_queue_returns_immediately_when_empty():
    client = _connected_client()
    client.channel.basic_get.return_value = (None, None, None)

    assert client.get_message("queue-1") is None
    assert client.channel.basic_get.call_count == 1


def test_read_messages_filters_and_acks_eos_without_changing_data_shape():
    client = _connected_client()
    client.configure_reference_streams(
        {
            "data_in": {
                "type": "reference",
                "value": ["queue-1"],
                "streams": [
                    {
                        "queue_name": "queue-1",
                        "stream_id": "stream-1",
                        "protocol": "eos-v1",
                        "expected_producer_ids": ["producer-1"],
                    }
                ],
            }
        },
        {},
    )
    client.channel.basic_get.side_effect = [
        (_delivery(1), _properties(), b'{"value": 1}'),
        (
            _delivery(2),
            _properties(REFERENCE_EOS_TYPE, "producer-1"),
            b"{}",
        ),
    ]

    assert client.read_messages("queue-1") == [
        {"body": {"value": 1}, "delivery_tag": 1}
    ]
    assert client.read_messages("queue-1") == []
    client.channel.basic_ack.assert_called_once_with(delivery_tag=2)


def test_get_message_waits_for_all_expected_producers(monkeypatch):
    client = _connected_client()
    client.configure_reference_streams(
        {
            "data_in": {
                "type": "reference",
                "value": ["queue-1"],
                "streams": [
                    {
                        "queue_name": "queue-1",
                        "stream_id": "stream-1",
                        "protocol": "eos-v1",
                        "expected_producer_ids": ["producer-1", "producer-2"],
                    }
                ],
            }
        },
        {},
    )
    client.channel.basic_get.side_effect = [
        (
            _delivery(1),
            _properties(REFERENCE_EOS_TYPE, "producer-1"),
            b"{}",
        ),
        (None, None, None),
        (_delivery(2), _properties(), b'{"value": 2}'),
        (
            _delivery(3),
            _properties(REFERENCE_EOS_TYPE, "producer-2"),
            b"{}",
        ),
    ]
    monkeypatch.setattr("csi_base_component_sdk.rabbitmq.time.sleep", lambda _: None)

    assert client.get_message("queue-1") == {
        "body": '{"value": 2}',
        "delivery_tag": 2,
    }
    assert client.get_message("queue-1") is None
    assert client.channel.basic_ack.call_count == 2


def test_eos_wait_honors_context_cancellation(monkeypatch):
    client = _connected_client()
    checks = 0

    def cancel_check():
        nonlocal checks
        checks += 1
        if checks >= 2:
            raise RuntimeError("cancelled")

    client.configure_reference_streams(
        {
            "data_in": {
                "type": "reference",
                "streams": [
                    {
                        "queue_name": "queue-1",
                        "stream_id": "stream-1",
                        "protocol": "eos-v1",
                        "expected_producer_ids": ["producer-1"],
                    }
                ],
            }
        },
        {},
        cancel_check,
    )
    client.channel.basic_get.return_value = (None, None, None)
    monkeypatch.setattr("csi_base_component_sdk.rabbitmq.time.sleep", lambda _: None)

    with pytest.raises(RuntimeError, match="cancelled"):
        client.get_message("queue-1")


def test_abort_is_acked_and_hidden_from_component():
    client = _connected_client()
    client.configure_reference_streams(
        {
            "data_in": {
                "type": "reference",
                "streams": [
                    {
                        "queue_name": "queue-1",
                        "stream_id": "stream-1",
                        "protocol": "eos-v1",
                    }
                ],
            }
        },
        {},
    )
    client.channel.basic_get.return_value = (
        _delivery(1),
        _properties(REFERENCE_ABORT_TYPE, "producer-1"),
        b"{}",
    )

    with pytest.raises(ReferenceStreamAborted):
        client.get_message("queue-1")
    client.channel.basic_ack.assert_called_once_with(delivery_tag=1)


def test_close_reference_outputs_publishes_amqp_eos_properties():
    client = _connected_client()
    client.configure_reference_streams(
        {},
        {
            "data_out": {
                "type": "reference",
                "value": ["queue-1"],
                "streams": [
                    {
                        "queue_name": "queue-1",
                        "stream_id": "stream-1",
                        "protocol": "eos-v1",
                    }
                ],
            }
        },
    )

    assert client.close_reference_outputs(
        action_id="action-1",
        producer_id="run-1",
        status="success",
    )
    publish = client.channel.basic_publish.call_args.kwargs
    properties: pika.BasicProperties = publish["properties"]
    assert properties.type == REFERENCE_EOS_TYPE
    assert properties.content_type == REFERENCE_CONTROL_CONTENT_TYPE
    assert properties.message_id == "eos:stream-1:run-1"
    assert properties.correlation_id == "action-1"
    assert properties.headers == {
        "x-csi-producer-id": "run-1",
        "x-csi-stream-id": "stream-1",
    }


def test_control_frame_detection_uses_properties_not_business_json():
    client = _connected_client()
    client.configure_reference_streams(
        {
            "data_in": {
                "type": "reference",
                "streams": [
                    {
                        "queue_name": "queue-1",
                        "stream_id": "stream-1",
                        "protocol": "eos-v1",
                    }
                ],
            }
        },
        {},
    )
    client.channel.basic_get.return_value = (
        _delivery(1),
        _properties(),
        b'{"type": "csi.reference.eos.v1"}',
    )

    assert client.get_message("queue-1") == {
        "body": '{"type": "csi.reference.eos.v1"}',
        "delivery_tag": 1,
    }


def test_consume_all_filters_eos_and_preserves_callback_shape():
    client = _connected_client()
    callback = MagicMock(return_value=True)
    client.configure_reference_streams(
        {
            "data_in": {
                "type": "reference",
                "streams": [
                    {
                        "queue_name": "queue-1",
                        "stream_id": "stream-1",
                        "protocol": "eos-v1",
                        "expected_producer_ids": ["producer-1"],
                    }
                ],
            }
        },
        {},
    )
    client.channel.basic_get.side_effect = [
        (_delivery(1), _properties(), b'{"value": 1}'),
        (
            _delivery(2),
            _properties(REFERENCE_EOS_TYPE, "producer-1"),
            b"{}",
        ),
    ]

    assert client.consume_all("queue-1", callback) == 1
    callback.assert_called_once_with(
        [
            (
                '{"value": 1}',
                {
                    "delivery_tag": 1,
                    "exchange": "",
                    "routing_key": "queue-1",
                    "redelivered": False,
                },
            )
        ]
    )
    assert client.channel.basic_ack.call_count == 2


def test_failed_output_closure_uses_abort_control_type():
    client = _connected_client()
    client.configure_reference_streams(
        {},
        {
            "data_out": {
                "type": "reference",
                "streams": [
                    {
                        "queue_name": "queue-1",
                        "stream_id": "stream-1",
                        "protocol": "eos-v1",
                    }
                ],
            }
        },
    )

    assert client.close_reference_outputs(
        action_id="action-1",
        producer_id="run-1",
        status="failed",
    )
    properties = client.channel.basic_publish.call_args.kwargs["properties"]
    assert properties.type == REFERENCE_ABORT_TYPE
    assert properties.message_id == "abort:stream-1:run-1"
