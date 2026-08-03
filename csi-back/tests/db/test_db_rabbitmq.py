"""app.db.rabbitmq 行为测试。"""

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

import app.db.rabbitmq as rabbit_mod
from app.db.rabbitmq import ReferenceMessageDelivery, delete_queue


def _message():
    """构造包含完整可转发属性的测试消息。"""
    return SimpleNamespace(
        body=b'{"value": 1}',
        headers={"trace-id": "trace-1"},
        content_type="application/json",
        content_encoding="utf-8",
        delivery_mode=2,
        priority=None,
        correlation_id="action-1",
        reply_to=None,
        expiration=None,
        message_id="message-1",
        timestamp=None,
        type=None,
        user_id=None,
        app_id="test",
    )


@pytest.mark.asyncio
async def test_delete_queue_noop_when_not_connected():
    # 未建立连接时删除队列应直接返回且不抛异常
    rabbit_mod.rabbitmq_connection = None
    await delete_queue("test-queue-nonexist")


@pytest.mark.asyncio
async def test_close_rabbitmq_when_none():
    # 连接对象为 None 时关闭应可重复调用
    rabbit_mod.rabbitmq_connection = None
    await rabbit_mod.close_rabbitmq()


@pytest.mark.asyncio
async def test_provision_reference_queues_declares_durable_queues_once(
    monkeypatch,
):
    channel = SimpleNamespace(
        declare_queue=AsyncMock(),
        close=AsyncMock(),
        is_closed=False,
    )
    connection = SimpleNamespace(channel=AsyncMock(return_value=channel))
    monkeypatch.setattr(rabbit_mod, "rabbitmq_connection", connection)

    provisioned = await rabbit_mod.provision_reference_queues(
        ["queue-1", "queue-1", "queue-2"]
    )

    assert provisioned == ["queue-1", "queue-2"]
    assert channel.declare_queue.await_count == 2
    channel.declare_queue.assert_any_await(
        "queue-1",
        durable=True,
        exclusive=False,
        auto_delete=False,
        arguments={},
    )
    channel.declare_queue.assert_any_await(
        "queue-2",
        durable=True,
        exclusive=False,
        auto_delete=False,
        arguments={},
    )
    channel.close.assert_awaited_once()


@pytest.mark.asyncio
async def test_provision_reference_queues_closes_channel_after_failure(
    monkeypatch,
):
    channel = SimpleNamespace(
        declare_queue=AsyncMock(side_effect=RuntimeError("声明失败")),
        close=AsyncMock(),
        is_closed=False,
    )
    connection = SimpleNamespace(channel=AsyncMock(return_value=channel))
    monkeypatch.setattr(rabbit_mod, "rabbitmq_connection", connection)

    with pytest.raises(RuntimeError, match="声明失败"):
        await rabbit_mod.provision_reference_queues(["queue-1"])

    channel.close.assert_awaited_once()


@pytest.mark.asyncio
async def test_provision_reference_queues_stops_when_guard_is_closed(
    monkeypatch,
):
    channel = SimpleNamespace(
        declare_queue=AsyncMock(),
        close=AsyncMock(),
        is_closed=False,
    )
    connection = SimpleNamespace(channel=AsyncMock(return_value=channel))
    monkeypatch.setattr(rabbit_mod, "rabbitmq_connection", connection)
    before_declare = AsyncMock(return_value=False)

    with pytest.raises(RuntimeError, match="预声明租约已失效"):
        await rabbit_mod.provision_reference_queues(
            ["queue-1"],
            before_declare=before_declare,
        )

    before_declare.assert_awaited_once_with()
    channel.declare_queue.assert_not_awaited()
    channel.close.assert_awaited_once()


@pytest.mark.asyncio
async def test_provision_reference_queues_guards_each_deduplicated_queue(
    monkeypatch,
):
    channel = SimpleNamespace(
        declare_queue=AsyncMock(),
        close=AsyncMock(),
        is_closed=False,
    )
    connection = SimpleNamespace(channel=AsyncMock(return_value=channel))
    monkeypatch.setattr(rabbit_mod, "rabbitmq_connection", connection)
    before_declare = AsyncMock(return_value=True)

    provisioned = await rabbit_mod.provision_reference_queues(
        ["queue-1", "queue-1", "queue-2"],
        before_declare=before_declare,
        declare_timeout_seconds=1,
    )

    assert provisioned == ["queue-1", "queue-2"]
    assert before_declare.await_count == 2
    assert channel.declare_queue.await_count == 2
    channel.declare_queue.assert_any_await(
        "queue-1",
        durable=True,
        exclusive=False,
        auto_delete=False,
        arguments={},
    )
    channel.declare_queue.assert_any_await(
        "queue-2",
        durable=True,
        exclusive=False,
        auto_delete=False,
        arguments={},
    )
    channel.close.assert_awaited_once()


@pytest.mark.asyncio
async def test_get_reference_message_uses_passive_queue(monkeypatch):
    queue = SimpleNamespace(get=AsyncMock(return_value=None))
    channel = SimpleNamespace(
        declare_queue=AsyncMock(return_value=queue),
        close=AsyncMock(),
        is_closed=False,
    )
    connection = SimpleNamespace(channel=AsyncMock(return_value=channel))
    monkeypatch.setattr(rabbit_mod, "rabbitmq_connection", connection)

    message = await rabbit_mod.get_reference_message("managed-queue")

    assert message is None
    connection.channel.assert_awaited_once_with(
        publisher_confirms=True,
        on_return_raises=True,
    )
    channel.declare_queue.assert_awaited_once_with(
        "managed-queue",
        passive=True,
    )
    queue.get.assert_awaited_once_with(fail=False, no_ack=False)
    channel.close.assert_awaited_once()


@pytest.mark.asyncio
async def test_open_reference_consumer_uses_passive_queue(monkeypatch):
    iterator = SimpleNamespace(
        __aenter__=AsyncMock(),
        close=AsyncMock(),
    )
    queue = SimpleNamespace(iterator=MagicMock(return_value=iterator))
    channel = SimpleNamespace(
        declare_queue=AsyncMock(return_value=queue),
        set_qos=AsyncMock(),
        close=AsyncMock(),
        is_closed=False,
    )
    connection = SimpleNamespace(channel=AsyncMock(return_value=channel))
    monkeypatch.setattr(rabbit_mod, "rabbitmq_connection", connection)

    consumer = await rabbit_mod.open_reference_consumer(
        "managed-queue",
        prefetch_count=2,
    )

    channel.set_qos.assert_awaited_once_with(prefetch_count=2)
    channel.declare_queue.assert_awaited_once_with(
        "managed-queue",
        passive=True,
    )
    queue.iterator.assert_called_once_with(no_ack=False)
    iterator.__aenter__.assert_awaited_once()
    await consumer.close()
    iterator.close.assert_awaited_once()
    channel.close.assert_awaited_once()


@pytest.mark.asyncio
async def test_publish_reference_delivery_never_declares_destination():
    publish = AsyncMock(return_value=True)
    channel = SimpleNamespace(
        declare_queue=AsyncMock(),
        default_exchange=SimpleNamespace(publish=publish),
    )
    delivery = ReferenceMessageDelivery(channel=channel, message=_message())

    await rabbit_mod.publish_reference_delivery(
        delivery,
        ["queue-1", "queue-2", "queue-1"],
    )

    channel.declare_queue.assert_not_awaited()
    assert publish.await_count == 2
    assert [call.kwargs for call in publish.await_args_list] == [
        {"routing_key": "queue-1", "mandatory": True},
        {"routing_key": "queue-2", "mandatory": True},
    ]


@pytest.mark.asyncio
async def test_publish_reference_json_delivery_does_not_declare_managed_queue():
    publish = AsyncMock(return_value=True)
    channel = SimpleNamespace(
        declare_queue=AsyncMock(),
        default_exchange=SimpleNamespace(publish=publish),
    )
    delivery = ReferenceMessageDelivery(channel=channel, message=_message())

    await rabbit_mod.publish_reference_json_delivery(
        delivery,
        ["managed-queue"],
        {"value": "已转换"},
    )

    channel.declare_queue.assert_not_awaited()
    assert publish.await_args.kwargs == {
        "routing_key": "managed-queue",
        "mandatory": True,
    }


@pytest.mark.asyncio
async def test_publish_reference_control_does_not_declare_managed_queue(
    monkeypatch,
):
    publish = AsyncMock(return_value=True)
    channel = SimpleNamespace(
        declare_queue=AsyncMock(),
        default_exchange=SimpleNamespace(publish=publish),
        close=AsyncMock(),
        is_closed=False,
    )
    connection = SimpleNamespace(channel=AsyncMock(return_value=channel))
    monkeypatch.setattr(rabbit_mod, "rabbitmq_connection", connection)

    await rabbit_mod.publish_reference_control(
        queue_names=["managed-queue"],
        stream_id="stream-1",
        producer_id="producer-1",
        action_id="action-1",
        status="abort",
        reason="测试失败",
    )

    connection.channel.assert_awaited_once_with(
        publisher_confirms=True,
        on_return_raises=True,
    )
    channel.declare_queue.assert_not_awaited()
    assert publish.await_args.kwargs == {
        "routing_key": "managed-queue",
        "mandatory": True,
    }
    channel.close.assert_awaited_once()
