from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Sequence

import aio_pika
from aio_pika.abc import AbstractChannel, AbstractIncomingMessage
from loguru import logger
from urllib.parse import quote

from app.core.config import settings
from app.schemas.action.reference import (
    REFERENCE_ABORT_TYPE,
    REFERENCE_CONTROL_CONTENT_TYPE,
    REFERENCE_EOS_TYPE,
    ReferenceControlFrame,
    ReferenceQueueBinding,
    ReferenceStreamDescriptor,
)

logger = logger.bind(name=__name__)

rabbitmq_connection: aio_pika.Connection = None


@dataclass
class ReferenceMessageDelivery:
    """封装一条手动确认的 Reference 消息及其所属通道。"""

    channel: AbstractChannel
    message: AbstractIncomingMessage

    async def ack(self) -> None:
        """确认源消息。"""
        await self.message.ack()

    async def nack(self, *, requeue: bool = True) -> None:
        """拒绝源消息并按需重新入队。"""
        await self.message.nack(requeue=requeue)

    async def close(self) -> None:
        """关闭消息所属通道。"""
        if not self.channel.is_closed:
            await self.channel.close()


async def init_rabbitmq():
    """初始化RabbitMQ连接"""
    global rabbitmq_connection
    
    try:
        username = quote(settings.RABBITMQ_USERNAME, safe="")
        password = quote(settings.RABBITMQ_PASSWORD, safe="")
        vhost = quote(settings.RABBITMQ_VHOST, safe="")
        url = f"amqp://{username}:{password}@{settings.RABBITMQ_HOST}:{settings.RABBITMQ_PORT}/{vhost}"
        rabbitmq_connection = await aio_pika.connect_robust(url)
        logger.info("已连接到RabbitMQ")
    except Exception as e:
        logger.error(f"RabbitMQ连接失败: {str(e)}")
        raise


async def close_rabbitmq():
    """关闭RabbitMQ连接"""
    global rabbitmq_connection
    if rabbitmq_connection:
        await rabbitmq_connection.close()
        logger.info("已关闭RabbitMQ连接")


async def delete_queue(queue_name: str) -> bool:
    """删除指定名称的队列"""
    global rabbitmq_connection
    if not rabbitmq_connection:
        logger.warning("RabbitMQ连接未初始化，无法删除队列")
        return False
    
    channel = None
    try:
        channel = await rabbitmq_connection.channel()
        await channel.queue_delete(queue_name)
        logger.info(f"已删除队列: {queue_name}")
        return True
    except Exception as e:
        if e.__class__.__name__ in {
            "ChannelNotFoundEntity",
            "ChannelClosed",
        }:
            logger.info(f"队列已不存在，无需重复删除: {queue_name}")
            return True
        logger.error(f"删除队列失败 {queue_name}: {str(e)}")
        return False
    finally:
        if channel is not None and not channel.is_closed:
            try:
                await channel.close()
            except Exception as e:
                logger.warning(f"关闭RabbitMQ队列清理通道失败: {str(e)}")


def get_reference_control_kind(
    message: AbstractIncomingMessage,
) -> Literal["eos", "abort"] | None:
    """仅根据 AMQP Properties 识别 Reference 控制消息。"""
    if message.type == REFERENCE_EOS_TYPE:
        return "eos"
    if message.type == REFERENCE_ABORT_TYPE:
        return "abort"
    return None


def get_reference_control_identity(
    message: AbstractIncomingMessage,
) -> tuple[str | None, str | None]:
    """读取 Reference 控制消息携带的流和生产者身份。"""
    headers = message.headers or {}
    stream_id = headers.get("x-csi-stream-id")
    producer_id = headers.get("x-csi-producer-id")
    if isinstance(stream_id, bytes):
        stream_id = stream_id.decode("utf-8")
    if isinstance(producer_id, bytes):
        producer_id = producer_id.decode("utf-8")
    return (
        str(stream_id) if stream_id else None,
        str(producer_id) if producer_id else None,
    )


async def get_reference_message(queue_name: str) -> ReferenceMessageDelivery | None:
    """从持久队列获取一条需手动确认的 Reference 消息。"""
    if not rabbitmq_connection:
        raise RuntimeError("RabbitMQ连接未初始化")
    channel = await rabbitmq_connection.channel(
        publisher_confirms=True,
        on_return_raises=True,
    )
    try:
        queue = await channel.declare_queue(
            queue_name,
            durable=True,
            exclusive=False,
            auto_delete=False,
        )
        message = await queue.get(fail=False, no_ack=False)
        if message is None:
            await channel.close()
            return None
        return ReferenceMessageDelivery(channel=channel, message=message)
    except Exception:
        if not channel.is_closed:
            await channel.close()
        raise


def clone_reference_message(message: AbstractIncomingMessage) -> aio_pika.Message:
    """克隆 DATA 消息，完整保留可转发的 AMQP Properties。"""
    return aio_pika.Message(
        body=message.body,
        headers=dict(message.headers or {}),
        content_type=message.content_type,
        content_encoding=message.content_encoding,
        delivery_mode=message.delivery_mode,
        priority=message.priority,
        correlation_id=message.correlation_id,
        reply_to=message.reply_to,
        expiration=message.expiration,
        message_id=message.message_id,
        timestamp=message.timestamp,
        type=message.type,
        user_id=message.user_id,
        app_id=message.app_id,
    )


async def publish_reference_delivery(
    delivery: ReferenceMessageDelivery,
    queue_names: Sequence[str],
) -> None:
    """确认式发布 DATA；调用方只能在本函数成功后确认源消息。"""
    for queue_name in dict.fromkeys(queue_names):
        await delivery.channel.declare_queue(
            queue_name,
            durable=True,
            exclusive=False,
            auto_delete=False,
        )
        confirmation = await delivery.channel.default_exchange.publish(
            clone_reference_message(delivery.message),
            routing_key=queue_name,
            mandatory=True,
        )
        if confirmation is False:
            raise RuntimeError(f"Reference消息发布未获确认: {queue_name}")


async def publish_reference_control(
    *,
    queue_names: Sequence[str],
    stream_id: str,
    producer_id: str,
    action_id: str,
    status: Literal["eos", "abort"],
    reason: str | None = None,
) -> None:
    """向目标流发送经 publisher confirm 确认的 EOS 或 ABORT。"""
    if not rabbitmq_connection:
        raise RuntimeError("RabbitMQ连接未初始化")
    channel = await rabbitmq_connection.channel(
        publisher_confirms=True,
        on_return_raises=True,
    )
    try:
        message_type = (
            REFERENCE_EOS_TYPE if status == "eos" else REFERENCE_ABORT_TYPE
        )
        body = ReferenceControlFrame(
            stream_id=stream_id,
            producer_id=producer_id,
            action_id=action_id,
            status=status,
            reason=reason,
        ).model_dump_json().encode("utf-8")
        for queue_name in dict.fromkeys(queue_names):
            await channel.declare_queue(
                queue_name,
                durable=True,
                exclusive=False,
                auto_delete=False,
            )
            confirmation = await channel.default_exchange.publish(
                aio_pika.Message(
                    body=body,
                    headers={
                        "x-csi-producer-id": producer_id,
                        "x-csi-stream-id": stream_id,
                    },
                    content_type=REFERENCE_CONTROL_CONTENT_TYPE,
                    delivery_mode=aio_pika.DeliveryMode.PERSISTENT,
                    correlation_id=action_id,
                    message_id=f"{status}:{stream_id}:{producer_id}",
                    type=message_type,
                ),
                routing_key=queue_name,
                mandatory=True,
            )
            if confirmation is False:
                raise RuntimeError(f"Reference控制消息发布未获确认: {queue_name}")
    finally:
        if not channel.is_closed:
            await channel.close()


async def delete_owned_queues(
    owner_action_id: str,
    streams: Sequence[ReferenceStreamDescriptor | ReferenceQueueBinding],
) -> list[str]:
    """幂等删除指定 Action 拥有的队列并返回成功项。"""
    deleted: list[str] = []
    for stream in streams:
        if stream.owner_action_id != owner_action_id:
            continue
        if await delete_queue(stream.queue_name):
            deleted.append(stream.queue_name)
    return list(dict.fromkeys(deleted))

