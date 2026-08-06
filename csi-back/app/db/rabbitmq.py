from __future__ import annotations

import asyncio
import json
from collections.abc import Awaitable, Callable
from contextlib import suppress
from dataclasses import dataclass
from typing import Any, Literal, Sequence
from uuid import uuid4

import aio_pika
from aio_pika.abc import (
    AbstractChannel,
    AbstractIncomingMessage,
    AbstractQueueIterator,
)
from loguru import logger
from pamqp.commands import Basic
from urllib.parse import quote

from app.core.config import settings
from app.db.rabbitmq_fragmentation import (
    FRAGMENT_MESSAGE_TYPE,
    FragmentAssembler,
    FragmentSettings,
    encode_fragments,
    parse_fragment,
)
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
fragment_settings = FragmentSettings.from_env()

async def _get_reference_queue(
    channel: AbstractChannel,
    queue_name: str,
):
    """被动获取由后端预先创建的 Reference 队列。"""
    return await channel.declare_queue(queue_name, passive=True)


def _ensure_publish_confirmed(confirmation, queue_name: str) -> None:
    """仅接受明确的布尔成功或 AMQP Basic.Ack。"""
    if confirmation is True or isinstance(confirmation, Basic.Ack):
        return
    raise RuntimeError(f"Reference消息发布未获确认: {queue_name}")


@dataclass
class ReferenceMessageDelivery:
    """封装一条手动确认的 Reference 消息及其所属通道。"""

    channel: AbstractChannel
    message: AbstractIncomingMessage
    owns_channel: bool = True
    physical_messages: tuple[AbstractIncomingMessage, ...] = ()

    def __post_init__(self) -> None:
        if not self.physical_messages:
            self.physical_messages = (self.message,)

    async def ack(self) -> None:
        """确认源消息。"""
        for message in self.physical_messages:
            if not getattr(message, "processed", False):
                await message.ack()

    async def nack(self, *, requeue: bool = True) -> None:
        """拒绝源消息并按需重新入队。"""
        for message in self.physical_messages:
            if not getattr(message, "processed", False):
                await message.nack(requeue=requeue)

    async def close(self) -> None:
        """关闭消息所属通道。"""
        if self.owns_channel and not self.channel.is_closed:
            await self.channel.close()


class _LogicalIncomingMessage:
    """向后端原生节点暴露重组后的完整消息属性。"""

    def __init__(
        self,
        body: bytes,
        message_id: str,
        source: AbstractIncomingMessage,
        physical_messages: tuple[AbstractIncomingMessage, ...],
    ):
        self.body = body
        self.message_id = message_id
        self._source = source
        self._physical_messages = physical_messages
        self.type = None
        self.headers = {
            key: value
            for key, value in dict(source.headers or {}).items()
            if not str(key).startswith("x-csi-fragment-")
            and not str(key).startswith("x-csi-original-")
        }

    @property
    def processed(self) -> bool:
        """仅当全部物理分片均已确认或拒绝时视为已处理。"""
        return all(
            getattr(message, "processed", False)
            for message in self._physical_messages
        )

    def __getattr__(self, name: str) -> Any:
        return getattr(self._source, name)


@dataclass
class ReferenceQueueConsumer:
    """持有一个支持手动确认和可靠关闭的 Reference 长驻消费者。"""

    channel: AbstractChannel
    iterator: AbstractQueueIterator
    _closed: bool = False
    assembler: FragmentAssembler[AbstractIncomingMessage] | None = None

    async def receive(self) -> ReferenceMessageDelivery | None:
        """等待下一条消息，消费者关闭后返回 None。"""
        if self._closed:
            return None
        if self.assembler is None:
            self.assembler = FragmentAssembler(fragment_settings)
        while True:
            try:
                message = await self.iterator.__anext__()
            except StopAsyncIteration:
                return None
            control_kind = get_reference_control_kind(message)
            if control_kind is not None:
                if self.assembler.has_pending and control_kind == "abort":
                    pending = self.assembler.discard_pending()
                    return ReferenceMessageDelivery(
                        channel=self.channel,
                        message=message,
                        owns_channel=False,
                        physical_messages=(*pending, message),
                    )
                return ReferenceMessageDelivery(
                    channel=self.channel,
                    message=message,
                    owns_channel=False,
                )

            fragment = parse_fragment(
                message.body,
                message.type,
                message.headers,
                fragment_settings,
            )
            if fragment is None:
                return ReferenceMessageDelivery(
                    channel=self.channel,
                    message=message,
                    owns_channel=False,
                )
            assembled = self.assembler.add(fragment, message)
            if assembled is None:
                continue
            physical_messages = assembled.tokens
            return ReferenceMessageDelivery(
                channel=self.channel,
                message=_LogicalIncomingMessage(
                    assembled.body,
                    assembled.message_id,
                    physical_messages[0],
                    physical_messages,
                ),
                owns_channel=False,
                physical_messages=physical_messages,
            )

    async def close(self) -> None:
        """关闭消费者和通道，使尚未确认的消息重新入队。"""
        if self._closed:
            return
        self._closed = True
        with suppress(Exception):
            await self.iterator.close()
        if not self.channel.is_closed:
            with suppress(Exception):
                await self.channel.close()

    async def __aenter__(self) -> "ReferenceQueueConsumer":
        return self

    async def __aexit__(self, exc_type, exc, traceback) -> None:
        await self.close()


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


async def provision_reference_queues(
    queue_names: Sequence[str],
    *,
    before_declare: Callable[[], Awaitable[bool]] | None = None,
    declare_timeout_seconds: float | None = None,
) -> list[str]:
    """一次性声明后端拥有的持久 Reference 队列。"""
    if not rabbitmq_connection:
        raise RuntimeError("RabbitMQ连接未初始化")
    channel = await rabbitmq_connection.channel()
    provisioned: list[str] = []
    try:
        for queue_name in dict.fromkeys(queue_names):
            if before_declare is not None and not await before_declare():
                raise RuntimeError("Reference 队列预声明租约已失效")
            declaration = channel.declare_queue(
                queue_name,
                durable=True,
                exclusive=False,
                auto_delete=False,
                arguments={
                    "x-consumer-timeout": (
                        settings.REFERENCE_CONSUMER_ACK_TIMEOUT_SECONDS * 1000
                    )
                },
            )
            if declare_timeout_seconds is None:
                await declaration
            else:
                await asyncio.wait_for(
                    declaration,
                    timeout=declare_timeout_seconds,
                )
            provisioned.append(queue_name)
        return provisioned
    finally:
        if not channel.is_closed:
            await channel.close()


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


async def get_reference_message(
    queue_name: str,
) -> ReferenceMessageDelivery | None:
    """从持久队列获取一条需手动确认的 Reference 消息。"""
    if not rabbitmq_connection:
        raise RuntimeError("RabbitMQ连接未初始化")
    channel = await rabbitmq_connection.channel(
        publisher_confirms=True,
        on_return_raises=True,
    )
    try:
        queue = await _get_reference_queue(
            channel,
            queue_name,
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


async def get_reference_logical_message(
    queue_name: str,
) -> ReferenceMessageDelivery | None:
    """获取一条完整逻辑消息，物理分片由后端在同一通道内重组。"""
    if not rabbitmq_connection:
        raise RuntimeError("RabbitMQ连接未初始化")
    channel = await rabbitmq_connection.channel(
        publisher_confirms=True,
        on_return_raises=True,
    )
    assembler = FragmentAssembler[AbstractIncomingMessage](fragment_settings)
    try:
        queue = await _get_reference_queue(channel, queue_name)
        while True:
            message = await queue.get(fail=False, no_ack=False)
            if message is None:
                await channel.close()
                return None

            control_kind = get_reference_control_kind(message)
            if control_kind is not None:
                if assembler.has_pending and control_kind == "abort":
                    pending = assembler.discard_pending()
                    return ReferenceMessageDelivery(
                        channel=channel,
                        message=message,
                        physical_messages=(*pending, message),
                    )
                return ReferenceMessageDelivery(
                    channel=channel,
                    message=message,
                )

            fragment = parse_fragment(
                message.body,
                message.type,
                message.headers,
                fragment_settings,
            )
            if fragment is None:
                return ReferenceMessageDelivery(
                    channel=channel,
                    message=message,
                )
            assembled = assembler.add(fragment, message)
            if assembled is None:
                continue
            physical_messages = assembled.tokens
            return ReferenceMessageDelivery(
                channel=channel,
                message=_LogicalIncomingMessage(
                    assembled.body,
                    assembled.message_id,
                    physical_messages[0],
                    physical_messages,
                ),
                physical_messages=physical_messages,
            )
    except Exception:
        if not channel.is_closed:
            await channel.close()
        raise


async def open_reference_consumer(
    queue_name: str,
    *,
    prefetch_count: int = 1,
) -> ReferenceQueueConsumer:
    """打开一个阻塞等待、手动确认的 Reference 长驻消费者。"""
    if not rabbitmq_connection:
        raise RuntimeError("RabbitMQ连接未初始化")
    if prefetch_count <= 0:
        raise ValueError("Reference消费者 prefetch_count 必须大于 0")
    channel = await rabbitmq_connection.channel()
    try:
        logical_prefetch = prefetch_count
        if prefetch_count == 1:
            max_fragments = (
                fragment_settings.max_logical_message_bytes
                + fragment_settings.fragment_bytes
                - 1
            ) // fragment_settings.fragment_bytes
            logical_prefetch = max_fragments * 2
        await channel.set_qos(prefetch_count=logical_prefetch)
        queue = await _get_reference_queue(
            channel,
            queue_name,
        )
        iterator = queue.iterator(no_ack=False)
        await iterator.__aenter__()
        return ReferenceQueueConsumer(
            channel=channel,
            iterator=iterator,
            assembler=FragmentAssembler(fragment_settings),
        )
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
        confirmation = await delivery.channel.default_exchange.publish(
            clone_reference_message(delivery.message),
            routing_key=queue_name,
            mandatory=True,
        )
        _ensure_publish_confirmed(confirmation, queue_name)


async def publish_reference_json_delivery(
    delivery: ReferenceMessageDelivery,
    queue_names: Sequence[str],
    payload: dict,
) -> None:
    """确认式发布变换后的 JSON DATA；成功返回前不得确认源消息。"""
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    source = delivery.message
    logical_message_id = str(source.message_id or uuid4().hex)
    fragments = encode_fragments(
        body,
        logical_message_id,
        fragment_settings,
    )
    source_headers = {
        key: value
        for key, value in dict(source.headers or {}).items()
        if not str(key).startswith("x-csi-fragment-")
        and not str(key).startswith("x-csi-original-")
    }
    publication_specs = (
        [
            (
                fragment.body,
                {**source_headers, **fragment.headers},
                fragment.message_id,
                FRAGMENT_MESSAGE_TYPE,
            )
            for fragment in fragments
        ]
        if fragments
        else [(body, source_headers, logical_message_id, None)]
    )
    if fragments:
        logger.info(
            "Reference JSON 消息已分片: message_id={}, bytes={}, fragments={}",
            logical_message_id,
            len(body),
            len(fragments),
        )
    for queue_name in dict.fromkeys(queue_names):
        for (
            publication_body,
            publication_headers,
            publication_message_id,
            publication_type,
        ) in publication_specs:
            confirmation = await delivery.channel.default_exchange.publish(
                aio_pika.Message(
                    body=publication_body,
                    headers=publication_headers,
                    content_type="application/json",
                    content_encoding="utf-8",
                    delivery_mode=source.delivery_mode,
                    priority=source.priority,
                    correlation_id=source.correlation_id,
                    reply_to=source.reply_to,
                    expiration=source.expiration,
                    message_id=publication_message_id,
                    timestamp=source.timestamp,
                    type=publication_type,
                    user_id=source.user_id,
                    app_id=source.app_id,
                ),
                routing_key=queue_name,
                mandatory=True,
            )
            _ensure_publish_confirmed(confirmation, queue_name)


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
            _ensure_publish_confirmed(confirmation, queue_name)
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

