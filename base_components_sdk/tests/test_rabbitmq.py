"""RabbitMQ 队列持久化声明测试。"""

from types import SimpleNamespace
from unittest.mock import MagicMock

from csi_base_component_sdk.rabbitmq import RabbitMQClient


def test_reference_queue_has_no_auto_delete_or_expiration():
    client = RabbitMQClient()
    client.connection = SimpleNamespace(is_closed=False)
    client.channel = MagicMock(is_closed=False)

    assert client.send_message("queue-1", {"value": 1}) is True

    client.channel.queue_declare.assert_called_once_with(
        queue="queue-1",
        durable=True,
        exclusive=False,
        auto_delete=False,
        arguments={},
    )
