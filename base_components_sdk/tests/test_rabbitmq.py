"""RabbitMQ 队列和 REFERENCE EOS 协议测试。"""

import json
from types import SimpleNamespace
from unittest.mock import MagicMock

import pika
import pytest
from pika.exceptions import ChannelClosedByBroker, UnroutableError

from csi_base_component_sdk.fragmentation import (
    FRAGMENT_MESSAGE_TYPE,
    FragmentSettings,
)
from csi_base_component_sdk.rabbitmq import (
    REFERENCE_ABORT_TYPE,
    REFERENCE_CONTROL_CONTENT_TYPE,
    REFERENCE_EOS_TYPE,
    RabbitMQClient,
    ReferenceStreamAborted,
    ReferenceStreamTransportError,
)


def _delivery(tag: int):
    return SimpleNamespace(
        delivery_tag=tag,
        exchange="",
        routing_key="queue-1",
        redelivered=False,
    )


def _properties(message_type=None, producer_id=None, message_id=None):
    return SimpleNamespace(
        type=message_type,
        message_id=message_id,
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


def _configure_managed_output(
    client: RabbitMQClient,
    queue_name: str = "queue-1",
) -> None:
    """为测试注册一个后端托管输出流。"""
    client.configure_reference_streams(
        {},
        {
            "data_out": {
                "type": "reference",
                "streams": [
                    {
                        "queue_name": queue_name,
                        "stream_id": "stream-1",
                        "protocol": "eos-v1",
                    }
                ],
            }
        },
    )


def _configure_managed_input(client: RabbitMQClient) -> None:
    """为测试注册一个后端托管输入流。"""
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


def _receive_message(client: RabbitMQClient, tag: int = 1) -> dict:
    """让测试客户端收到一条等待确认的消息。"""
    client.channel.basic_get.return_value = (
        _delivery(tag),
        _properties(message_id=f"data-{tag}"),
        b'{"value": 1}',
    )
    return client.get_message("queue-1")


def test_client_loads_rabbitmq_config_from_parent_dotenv(
    monkeypatch,
    tmp_path,
):
    for key in (
        "RABBITMQ_HOST",
        "RABBITMQ_PORT",
        "RABBITMQ_USERNAME",
        "RABBITMQ_PASSWORD",
        "RABBITMQ_VHOST",
    ):
        monkeypatch.delenv(key, raising=False)
    (tmp_path / ".env").write_text(
        "\n".join(
            (
                "RABBITMQ_HOST=broker.internal",
                "RABBITMQ_PORT=5673",
                "RABBITMQ_USERNAME=component",
                "RABBITMQ_PASSWORD=secret",
                "RABBITMQ_VHOST=/components",
            )
        ),
        encoding="utf-8",
    )
    workdir = tmp_path / "crawler"
    workdir.mkdir()
    monkeypatch.chdir(workdir)

    client = RabbitMQClient()

    assert client.host == "broker.internal"
    assert client.port == 5673
    assert client.username == "component"
    assert client.password == "secret"
    assert client.vhost == "/components"


def test_client_config_priority_is_argument_then_environment_then_dotenv(
    monkeypatch,
    tmp_path,
):
    (tmp_path / ".env").write_text(
        "\n".join(
            (
                "RABBITMQ_HOST=dotenv-host",
                "RABBITMQ_USERNAME=dotenv-user",
                "RABBITMQ_PASSWORD=dotenv-password",
            )
        ),
        encoding="utf-8",
    )
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("RABBITMQ_HOST", "environment-host")
    monkeypatch.setenv("RABBITMQ_USERNAME", "environment-user")
    monkeypatch.setenv("RABBITMQ_PASSWORD", "environment-password")

    client = RabbitMQClient(
        host="argument-host",
        username="argument-user",
    )

    assert client.host == "argument-host"
    assert client.username == "argument-user"
    assert client.password == "environment-password"


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


def test_ensure_connection_rebuilds_closed_channel_with_confirms():
    client = RabbitMQClient()
    replacement_channel = MagicMock(is_closed=False)
    connection = MagicMock(is_closed=False)
    connection.channel.return_value = replacement_channel
    client.connection = connection
    client.channel = MagicMock(is_closed=True)
    client._pending_deliveries[1] = SimpleNamespace(
        queue_name="queue-1",
        is_backend_owned=False,
    )

    assert client._ensure_connection() is True
    assert client.channel is replacement_channel
    assert client._pending_deliveries == {}
    replacement_channel.confirm_delivery.assert_called_once_with()


@pytest.mark.parametrize("closed_part", ["connection", "channel"])
def test_managed_pending_delivery_blocks_reconnect_before_send(
    monkeypatch,
    closed_part,
):
    client = _connected_client()
    _configure_managed_input(client)
    _receive_message(client)
    reconnect = MagicMock()

    if closed_part == "connection":
        client.connection.is_closed = True
        monkeypatch.setattr(
            "csi_base_component_sdk.rabbitmq.pika.BlockingConnection",
            reconnect,
        )
    else:
        client.channel.is_closed = True
        connection = MagicMock(is_closed=False)
        client.connection = connection
        reconnect = connection.channel

    with pytest.raises(ReferenceStreamTransportError, match="拒绝重建"):
        client.send_message("queue-1", {"value": 2})

    reconnect.assert_not_called()
    assert 1 in client._pending_deliveries
    with pytest.raises(ReferenceStreamTransportError, match="ACK 失败"):
        client.ack_message(1)
    with pytest.raises(ReferenceStreamTransportError, match="NACK 失败"):
        client.nack_message(1)
    assert 1 in client._pending_deliveries


@pytest.mark.parametrize("closed_part", ["connection", "channel"])
def test_external_pending_delivery_allows_reconnect_before_send(
    monkeypatch,
    closed_part,
):
    client = _connected_client()
    _receive_message(client)
    replacement_channel = MagicMock(is_closed=False)

    if closed_part == "connection":
        client.connection.is_closed = True
        replacement_connection = MagicMock(is_closed=False)
        replacement_connection.channel.return_value = replacement_channel
        reconnect = MagicMock(return_value=replacement_connection)
        monkeypatch.setattr(
            "csi_base_component_sdk.rabbitmq.pika.BlockingConnection",
            reconnect,
        )
    else:
        client.channel.is_closed = True
        replacement_connection = MagicMock(is_closed=False)
        replacement_connection.channel.return_value = replacement_channel
        client.connection = replacement_connection
        reconnect = replacement_connection.channel

    assert client.send_message("queue-2", {"value": 2}) is True

    reconnect.assert_called_once()
    assert client._pending_deliveries == {}
    assert client.ack_message(1) is False
    replacement_channel.basic_ack.assert_not_called()


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
    properties: pika.BasicProperties = (
        client.channel.basic_publish.call_args.kwargs["properties"]
    )
    assert len(properties.message_id) == 32
    int(properties.message_id, 16)
    assert properties.content_type == "application/json"
    assert properties.content_encoding == "utf-8"


def test_managed_reference_publish_never_declares_and_is_mandatory():
    client = _connected_client()
    _configure_managed_output(client)

    assert client.send_message("queue-1", {"value": 1}) is True

    client.channel.queue_declare.assert_not_called()
    assert client.channel.basic_publish.call_args.kwargs["mandatory"] is True


def test_managed_reference_negative_confirm_raises_transport_error():
    client = _connected_client()
    _configure_managed_output(client)
    client.channel.basic_publish.return_value = False

    with pytest.raises(ReferenceStreamTransportError, match="未获确认"):
        client.send_message("queue-1", {"value": 1})


def test_managed_reference_unroutable_publish_raises_transport_error():
    client = _connected_client()
    _configure_managed_output(client)
    client.channel.basic_publish.side_effect = UnroutableError([])

    with pytest.raises(ReferenceStreamTransportError, match="发布失败"):
        client.send_message("queue-1", {"value": 1})


def test_managed_reference_channel_rebuild_failure_raises_transport_error():
    client = RabbitMQClient()
    connection = MagicMock(is_closed=False)
    connection.channel.side_effect = RuntimeError("channel unavailable")
    client.connection = connection
    client.channel = MagicMock(is_closed=True)
    _configure_managed_output(client)

    with pytest.raises(ReferenceStreamTransportError, match="连接不可用"):
        client.send_message("queue-1", {"value": 1})


def test_send_message_rejects_invalid_explicit_message_id():
    client = _connected_client()

    with pytest.raises(ValueError, match="不能为空"):
        client.send_message("queue-1", {"value": 1}, message_id="")
    with pytest.raises(ValueError, match="255"):
        client.send_message("queue-1", {"value": 1}, message_id="中" * 86)
    with pytest.raises(TypeError, match="字符串"):
        client.send_message("queue-1", {"value": 1}, message_id=123)


def test_send_message_treats_negative_publisher_confirm_as_failure():
    client = _connected_client()
    client.channel.basic_publish.return_value = False

    assert client.send_message("queue-1", {"value": 1}) is False


def test_send_message_fragments_oversized_json_before_publish():
    client = _connected_client()
    client._fragment_settings = FragmentSettings(32, 16, 256)

    assert client.send_message(
        "queue-1",
        {"value": "中" * 30},
        message_id="logical-1",
    ) is True

    calls = client.channel.basic_publish.call_args_list
    assert len(calls) > 1
    assert all(
        call.kwargs["properties"].type == FRAGMENT_MESSAGE_TYPE
        for call in calls
    )
    assert {
        call.kwargs["properties"].headers["x-csi-original-message-id"]
        for call in calls
    } == {"logical-1"}
    assert all(len(call.kwargs["body"]) <= 16 for call in calls)


def test_get_message_reassembles_fragments_and_ack_confirms_every_part():
    client = _connected_client()
    client._fragment_settings = FragmentSettings(16, 8, 128)
    publications = client._build_business_publications(
        {"value": "中" * 12},
        "logical-1",
    )
    client.channel.basic_get.side_effect = [
        (_delivery(index + 1), properties, body)
        for index, (body, properties) in enumerate(publications)
    ]

    message = client.get_message("queue-1")

    assert message is not None
    assert json.loads(message["body"]) == {"value": "中" * 12}
    assert message["message_id"] == "logical-1"
    assert client.ack_message(message["delivery_tag"]) is True
    assert [
        call.kwargs["delivery_tag"]
        for call in client.channel.basic_ack.call_args_list
    ] == list(range(1, len(publications) + 1))


def test_send_messages_batch_reuses_message_id_for_fan_out():
    client = _connected_client()

    assert client.send_messages_batch(
        ["queue-1", "queue-2"],
        {"value": 1},
        message_id="stable-1",
    ) == 2
    assert [
        call.kwargs["properties"].message_id
        for call in client.channel.basic_publish.call_args_list
    ] == ["stable-1", "stable-1"]


def test_send_messages_batch_generates_one_default_id_for_fan_out():
    client = _connected_client()

    assert client.send_messages_batch(
        ["queue-1", "queue-2"],
        {"value": 1},
    ) == 2
    published_ids = [
        call.kwargs["properties"].message_id
        for call in client.channel.basic_publish.call_args_list
    ]
    assert published_ids[0] == published_ids[1]
    assert len(published_ids[0]) == 32


def test_publish_messages_uses_one_id_per_record_across_queues():
    client = _connected_client()

    assert client.publish_messages(
        ["queue-1", "queue-2"],
        [{"value": 1}, {"value": 2}],
        message_ids=["record-1", None],
    ) is True
    published_ids = [
        call.kwargs["properties"].message_id
        for call in client.channel.basic_publish.call_args_list
    ]
    assert published_ids[:2] == ["record-1", "record-1"]
    assert published_ids[2] == published_ids[3]
    assert len(published_ids[2]) == 32
    assert published_ids[2] != "record-1"
    for call in client.channel.basic_publish.call_args_list:
        properties = call.kwargs["properties"]
        assert properties.content_type == "application/json"
        assert properties.content_encoding == "utf-8"


def test_publish_messages_validates_id_count_before_publishing():
    client = _connected_client()

    with pytest.raises(ValueError, match="数量"):
        client.publish_messages(
            "queue-1",
            [{"value": 1}],
            message_ids=[],
        )
    client.channel.basic_publish.assert_not_called()


def test_publish_messages_uses_managed_topology_for_every_record():
    client = _connected_client()
    _configure_managed_output(client)

    assert client.publish_messages(
        "queue-1",
        [{"value": 1}, {"value": 2}],
    ) is True

    client.channel.queue_declare.assert_not_called()
    assert all(
        call.kwargs["mandatory"] is True
        for call in client.channel.basic_publish.call_args_list
    )


def test_mixed_batch_keeps_external_queue_failure_behavior():
    client = _connected_client()
    _configure_managed_output(client, "queue-2")
    client.channel.basic_publish.side_effect = RuntimeError("external failure")

    assert client.publish_messages(
        ["queue-1", "queue-2"],
        [{"value": 1}],
    ) is False


def test_unregistered_queue_returns_immediately_when_empty():
    client = _connected_client()
    client.channel.basic_get.return_value = (None, None, None)

    assert client.get_message("queue-1") is None
    assert client.channel.basic_get.call_count == 1


@pytest.mark.parametrize("operation", ["ack_message", "nack_message"])
def test_managed_delivery_confirmation_removes_tracking(operation):
    client = _connected_client()
    _configure_managed_input(client)
    _receive_message(client)

    assert getattr(client, operation)(1) is True

    assert client._pending_deliveries == {}


def test_managed_ack_raises_when_channel_is_closed():
    client = _connected_client()
    _configure_managed_input(client)
    _receive_message(client)
    client.channel.is_closed = True

    with pytest.raises(ReferenceStreamTransportError, match="ACK 失败"):
        client.ack_message(1)

    with pytest.raises(ReferenceStreamTransportError, match="NACK 失败"):
        client.nack_message(1)

    assert 1 in client._pending_deliveries


def test_external_queue_ack_returns_false_when_channel_is_closed():
    client = _connected_client()
    _receive_message(client)
    client.channel.is_closed = True

    assert client.ack_message(1) is False
    assert client._pending_deliveries == {}


def test_managed_nack_raises_for_amqp_failure():
    client = _connected_client()
    _configure_managed_input(client)
    _receive_message(client)
    client.channel.basic_nack.side_effect = RuntimeError("nack failed")

    with pytest.raises(ReferenceStreamTransportError, match="NACK 失败"):
        client.nack_message(1)


def test_external_queue_nack_returns_false_for_amqp_failure():
    client = _connected_client()
    _receive_message(client)
    client.channel.basic_nack.side_effect = RuntimeError("nack failed")

    assert client.nack_message(1) is False


def test_managed_ack_all_raises_for_amqp_failure():
    client = _connected_client()
    _configure_managed_input(client)
    client.channel.basic_get.side_effect = [
        (_delivery(1), _properties(message_id="data-1"), b'{"value": 1}'),
        (_delivery(2), _properties(message_id="data-2"), b'{"value": 2}'),
    ]
    assert len(client.read_messages("queue-1", batch_size=2)) == 2
    client.channel.basic_ack.side_effect = [None, RuntimeError("ack failed")]

    with pytest.raises(ReferenceStreamTransportError, match="批量 ACK 失败"):
        client.ack_all_message([1, 2])

    assert 1 not in client._pending_deliveries
    assert 2 in client._pending_deliveries


def test_external_queue_ack_all_returns_false_for_amqp_failure():
    client = _connected_client()
    _receive_message(client)
    client.channel.basic_ack.side_effect = RuntimeError("ack failed")

    assert client.ack_all_message([1]) is False


def test_close_clears_pending_delivery_tracking():
    client = _connected_client()
    _configure_managed_input(client)
    _receive_message(client)

    client.close()

    assert client._pending_deliveries == {}


def test_managed_reference_read_never_declares_missing_queue():
    client = _connected_client()
    _configure_managed_input(client)
    client.channel.basic_get.side_effect = ChannelClosedByBroker(
        404,
        "NOT_FOUND",
    )

    with pytest.raises(ReferenceStreamTransportError, match="读取失败"):
        client.get_message("queue-1")

    client.channel.queue_declare.assert_not_called()


def test_managed_reference_batch_read_raises_for_missing_queue():
    client = _connected_client()
    _configure_managed_input(client)
    client.channel.basic_get.side_effect = ChannelClosedByBroker(
        404,
        "NOT_FOUND",
    )

    with pytest.raises(ReferenceStreamTransportError, match="读取失败"):
        client.read_messages("queue-1")

    client.channel.queue_declare.assert_not_called()


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
        (_delivery(1), _properties(message_id="data-1"), b'{"value": 1}'),
        (
            _delivery(2),
            _properties(REFERENCE_EOS_TYPE, "producer-1"),
            b"{}",
        ),
    ]

    assert client.read_messages("queue-1") == [
        {"body": {"value": 1}, "delivery_tag": 1, "message_id": "data-1"}
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
        (_delivery(2), _properties(message_id="data-2"), b'{"value": 2}'),
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
        "message_id": "data-2",
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
    assert client._pending_deliveries == {}


def test_first_eos_ignores_late_abort_for_same_producer(monkeypatch):
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
        (
            _delivery(2),
            _properties(REFERENCE_ABORT_TYPE, "producer-1"),
            b"{}",
        ),
        (_delivery(3), _properties(message_id="data-1"), b'{"value": 1}'),
        (
            _delivery(4),
            _properties(REFERENCE_EOS_TYPE, "producer-2"),
            b"{}",
        ),
    ]
    monkeypatch.setattr("csi_base_component_sdk.rabbitmq.time.sleep", lambda _: None)

    assert client.get_message("queue-1") == {
        "body": '{"value": 1}',
        "delivery_tag": 3,
        "message_id": "data-1",
    }
    assert client.get_message("queue-1") is None
    assert client.channel.basic_ack.call_count == 3


def test_first_abort_cannot_be_overwritten_by_late_eos():
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
                        "expected_producer_ids": ["producer-1", "producer-2"],
                    }
                ],
            }
        },
        {},
    )

    with pytest.raises(ReferenceStreamAborted):
        client._handle_control(
            "queue-1",
            1,
            _properties(REFERENCE_ABORT_TYPE, "producer-1"),
        )
    with pytest.raises(ReferenceStreamAborted):
        client._handle_control(
            "queue-1",
            2,
            _properties(REFERENCE_EOS_TYPE, "producer-1"),
        )

    state = client._reference_inputs["queue-1"]
    assert state.terminal_by_producer_id["producer-1"] == REFERENCE_ABORT_TYPE
    assert "producer-1" not in state.completed_producer_ids
    assert client.channel.basic_ack.call_count == 2


@pytest.mark.parametrize(
    "control_type",
    [REFERENCE_EOS_TYPE, REFERENCE_ABORT_TYPE],
)
def test_repeated_reference_terminal_keeps_first_state(control_type):
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
                        "expected_producer_ids": ["producer-1", "producer-2"],
                    }
                ],
            }
        },
        {},
    )

    for delivery_tag in (1, 2):
        if control_type == REFERENCE_ABORT_TYPE:
            with pytest.raises(ReferenceStreamAborted):
                client._handle_control(
                    "queue-1",
                    delivery_tag,
                    _properties(control_type, "producer-1"),
                )
        else:
            client._handle_control(
                "queue-1",
                delivery_tag,
                _properties(control_type, "producer-1"),
            )

    state = client._reference_inputs["queue-1"]
    assert state.terminal_by_producer_id == {"producer-1": control_type}
    assert client.channel.basic_ack.call_count == 2


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


def test_managed_reference_control_is_mandatory_without_declaration():
    client = _connected_client()
    _configure_managed_output(client)

    assert client.close_reference_outputs(
        action_id="action-1",
        producer_id="run-1",
        status="success",
    )

    client.channel.queue_declare.assert_not_called()
    assert client.channel.basic_publish.call_args.kwargs["mandatory"] is True


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
        "message_id": None,
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
        (_delivery(1), _properties(message_id="data-1"), b'{"value": 1}'),
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
                    "message_id": "data-1",
                },
            )
        ]
    )
    assert client.channel.basic_ack.call_count == 2
    assert client._pending_deliveries == {}


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
