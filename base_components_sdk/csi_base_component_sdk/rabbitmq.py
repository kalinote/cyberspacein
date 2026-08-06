from __future__ import annotations

import json
import logging
import os
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional
from uuid import uuid4

import pika
from dotenv import find_dotenv, load_dotenv
from pika.exceptions import AMQPChannelError, AMQPConnectionError

from .fragmentation import (
    FRAGMENT_MESSAGE_TYPE,
    FragmentAssembler,
    FragmentProtocolError,
    FragmentSettings,
    encode_fragments,
    parse_fragment,
)

logger = logging.getLogger("CSI_SDK")

REFERENCE_EOS_TYPE = "csi.reference.eos.v1"
REFERENCE_ABORT_TYPE = "csi.reference.abort.v1"
REFERENCE_CONTROL_CONTENT_TYPE = (
    "application/vnd.cyberspacein.reference-control+json"
)
REFERENCE_PROTOCOL = "eos-v1"
MESSAGE_ID_MAX_BYTES = 255


class ReferenceStreamAborted(RuntimeError):
    """REFERENCE 数据流被生产者中止。"""


class ReferenceStreamTransportError(RuntimeError):
    """后端托管的 REFERENCE 队列传输失败。"""


class _CancellationSignal(Exception):
    """将取消检查异常穿过 RabbitMQ 错误处理层。"""

    def __init__(self, error: Exception):
        super().__init__(str(error))
        self.error = error


@dataclass
class _ReferenceInputState:
    stream_id: str
    expected_producer_ids: set[str] = field(default_factory=set)
    completed_producer_ids: set[str] = field(default_factory=set)
    terminal_by_producer_id: dict[str, str] = field(default_factory=dict)
    aborted: bool = False
    abort_error: str | None = None
    completed: bool = False


@dataclass(frozen=True)
class _ReferenceOutput:
    queue_name: str
    stream_id: str


@dataclass
class _PendingDelivery:
    logical_id: int
    physical_tags: tuple[int, ...]
    queue_name: str
    is_backend_owned: bool
    channel_generation: int
    received_at: float
    deadline_at: float
    state: str = "pending"
    first_transport_error: ReferenceStreamTransportError | None = None


@dataclass(frozen=True)
class _FragmentDeliveryToken:
    method_frame: Any
    properties: Any


@dataclass(frozen=True)
class _LogicalDeliveryFrame:
    delivery_tag: int
    exchange: str
    routing_key: str
    redelivered: bool


class RabbitMQClient:
    """SDK 内置 RabbitMQ 客户端，支持 REFERENCE EOS 协议。"""

    def __init__(
        self,
        host: str = None,
        port: int = None,
        username: str = None,
        password: str = None,
        vhost: str = None,
        reference_consumer_ack_timeout_seconds: float | None = None,
        reference_consumer_ack_safety_margin_seconds: float | None = None,
    ):
        dotenv_path = find_dotenv(usecwd=True)
        if dotenv_path:
            load_dotenv(dotenv_path, override=False)

        self.host = host or os.getenv("RABBITMQ_HOST", "localhost")
        self.port = port or int(os.getenv("RABBITMQ_PORT", "5672"))
        self.username = username or os.getenv("RABBITMQ_USERNAME", "guest")
        self.password = password or os.getenv("RABBITMQ_PASSWORD", "guest")
        self.vhost = vhost or os.getenv("RABBITMQ_VHOST", "/")

        self.connection: Optional[pika.BlockingConnection] = None
        self.consumer_channel: Optional[pika.channel.Channel] = None
        self.publisher_channel: Optional[pika.channel.Channel] = None
        self._reference_inputs: dict[str, _ReferenceInputState] = {}
        self._reference_outputs: list[_ReferenceOutput] = []
        self._reference_result_queues: set[str] = set()
        self._backend_owned_reference_queues: set[str] = set()
        self._pending_deliveries: dict[int, _PendingDelivery] = {}
        self._next_logical_delivery_id = 1
        self._consumer_channel_generation = 0
        self._consumer_transport_error: ReferenceStreamTransportError | None = None
        self._publisher_close_reason: Exception | None = None
        self._fragment_assemblers: dict[
            str,
            FragmentAssembler[_FragmentDeliveryToken],
        ] = {}
        self._fragment_settings = FragmentSettings.from_env()
        self._published_controls: set[tuple[str, str, str, str]] = set()
        self._cancel_check: Callable[[], None] | None = None
        self._successful_result_callback: Callable[[], None] | None = None
        self._poll_interval = max(
            0.01,
            float(os.getenv("CSI_REFERENCE_POLL_INTERVAL", "0.1")),
        )
        timeout_seconds = (
            reference_consumer_ack_timeout_seconds
            if reference_consumer_ack_timeout_seconds is not None
            else float(
                os.getenv("CSI_REFERENCE_CONSUMER_ACK_TIMEOUT_SECONDS", "21600")
            )
        )
        safety_margin_seconds = (
            reference_consumer_ack_safety_margin_seconds
            if reference_consumer_ack_safety_margin_seconds is not None
            else float(
                os.getenv(
                    "CSI_REFERENCE_CONSUMER_ACK_SAFETY_MARGIN_SECONDS",
                    "300",
                )
            )
        )
        if timeout_seconds <= 0:
            raise ValueError("REFERENCE 消费确认超时必须大于 0 秒")
        if not 0 <= safety_margin_seconds < timeout_seconds:
            raise ValueError("REFERENCE ACK 安全余量必须大于等于 0 且小于确认超时")
        self.reference_consumer_ack_timeout_seconds = float(timeout_seconds)
        self.reference_consumer_ack_safety_margin_seconds = float(
            safety_margin_seconds
        )

    @property
    def channel(self) -> Optional[pika.channel.Channel]:
        """返回消费通道，业务发布始终使用独立发布通道。"""
        return self.consumer_channel

    @channel.setter
    def channel(self, value: Optional[pika.channel.Channel]) -> None:
        """便于调试和测试显式注入通道。"""
        self.consumer_channel = value
        self.publisher_channel = value

    def _register_reference_queue(
        self,
        queue_name: str,
    ) -> None:
        """登记由后端拥有的 Reference 队列。"""
        self._backend_owned_reference_queues.add(queue_name)

    def configure_reference_streams(
        self,
        inputs: dict[str, Any],
        outputs: dict[str, Any],
        cancel_check: Callable[[], None] | None = None,
        successful_result_callback: Callable[[], None] | None = None,
    ) -> None:
        """注册运行上下文中的 EOS v1 输入输出流。"""
        self._reference_inputs.clear()
        self._reference_outputs.clear()
        self._reference_result_queues.clear()
        self._backend_owned_reference_queues.clear()
        self._fragment_assemblers.clear()
        self._cancel_check = cancel_check
        self._successful_result_callback = successful_result_callback

        for io_value in inputs.values():
            if not isinstance(io_value, dict) or io_value.get("type") != "reference":
                continue
            for stream in io_value.get("streams") or []:
                if not isinstance(stream, dict) or stream.get("protocol") != REFERENCE_PROTOCOL:
                    continue
                queue_name = stream.get("queue_name")
                stream_id = stream.get("stream_id")
                if not isinstance(queue_name, str) or not queue_name:
                    continue
                if not isinstance(stream_id, str) or not stream_id:
                    stream_id = queue_name
                self._register_reference_queue(queue_name)
                expected = {
                    str(item)
                    for item in stream.get("expected_producer_ids") or []
                    if item is not None and str(item)
                }
                self._reference_inputs[queue_name] = _ReferenceInputState(
                    stream_id=stream_id,
                    expected_producer_ids=expected,
                )

        seen_outputs: set[tuple[str, str]] = set()
        for io_value in outputs.values():
            if not isinstance(io_value, dict) or io_value.get("type") != "reference":
                continue
            value_queues = io_value.get("value") or []
            if isinstance(value_queues, str):
                value_queues = [value_queues]
            elif not isinstance(value_queues, (list, tuple, set, frozenset)):
                value_queues = []
            self._reference_result_queues.update(
                queue_name
                for queue_name in value_queues
                if isinstance(queue_name, str) and queue_name
            )
            for stream in io_value.get("streams") or []:
                if not isinstance(stream, dict) or stream.get("protocol") != REFERENCE_PROTOCOL:
                    continue
                queue_name = stream.get("queue_name")
                stream_id = stream.get("stream_id")
                if not isinstance(queue_name, str) or not queue_name:
                    continue
                self._reference_result_queues.add(queue_name)
                if not isinstance(stream_id, str) or not stream_id:
                    stream_id = queue_name
                self._register_reference_queue(queue_name)
                identity = (queue_name, stream_id)
                if identity not in seen_outputs:
                    self._reference_outputs.append(
                        _ReferenceOutput(
                            queue_name=queue_name,
                            stream_id=stream_id,
                        )
                    )
                    seen_outputs.add(identity)

    @property
    def has_reference_outputs(self) -> bool:
        """返回当前上下文是否声明了 EOS v1 输出流。"""
        return bool(self._reference_outputs)

    def _notify_successful_result(self) -> None:
        """通知运行上下文已经成功发布至少一条业务数据。"""
        if self._successful_result_callback is None:
            return
        try:
            self._successful_result_callback()
        except Exception as exc:
            logger.warning("业务结果状态回调失败: %s", exc)

    def connect(self) -> bool:
        """建立 RabbitMQ 连接、消费通道和独立发布通道。"""
        self._raise_for_managed_pending_reconnect()
        self._pending_deliveries.clear()
        self._fragment_assemblers.clear()
        connection = None
        consumer_channel = None
        publisher_channel = None
        try:
            credentials = pika.PlainCredentials(self.username, self.password)
            parameters = pika.ConnectionParameters(
                host=self.host,
                port=self.port,
                virtual_host=self.vhost,
                credentials=credentials,
            )

            connection = pika.BlockingConnection(parameters)
            self.connection = connection
            consumer_channel = self._open_consumer_channel()
            publisher_channel = self._open_publisher_channel()
            self.consumer_channel = consumer_channel
            self.publisher_channel = publisher_channel
            self._consumer_transport_error = None
            self._publisher_close_reason = None
            logger.info("RabbitMQ 连接成功: %s:%s", self.host, self.port)
            return True
        except AMQPConnectionError as exc:
            logger.error("RabbitMQ 连接失败: %s", exc)
        except Exception as exc:
            logger.error("RabbitMQ 连接异常: %s", exc)
        try:
            if publisher_channel and not publisher_channel.is_closed:
                publisher_channel.close()
            if consumer_channel and not consumer_channel.is_closed:
                consumer_channel.close()
            if connection and not connection.is_closed:
                connection.close()
        except Exception:
            pass
        self.connection = None
        self.consumer_channel = None
        self.publisher_channel = None
        return False

    def _open_consumer_channel(self) -> pika.channel.Channel:
        """创建消费通道并绑定当前通道代次的关闭回调。"""
        if self.connection is None:
            raise RuntimeError("RabbitMQ 连接尚未建立")
        channel = self.connection.channel()
        self._consumer_channel_generation += 1
        generation = self._consumer_channel_generation
        channel_impl = getattr(channel, "_impl", None)
        add_close_callback = getattr(
            channel_impl,
            "add_on_close_callback",
            None,
        )
        if callable(add_close_callback):
            add_close_callback(
                lambda closed_channel, reason: self._on_consumer_channel_closed(
                    closed_channel,
                    reason,
                    generation,
                )
            )
        return channel

    def _open_publisher_channel(self) -> pika.channel.Channel:
        """创建带 publisher confirm 的独立发布通道。"""
        if self.connection is None:
            raise RuntimeError("RabbitMQ 连接尚未建立")
        channel = self.connection.channel()
        channel_impl = getattr(channel, "_impl", None)
        add_close_callback = getattr(
            channel_impl,
            "add_on_close_callback",
            None,
        )
        if callable(add_close_callback):
            add_close_callback(self._on_publisher_channel_closed)
        channel.confirm_delivery()
        return channel

    @staticmethod
    def _describe_transport_reason(reason: Any) -> str:
        """优先输出 Broker reply code 和 reply text。"""
        reply_code = getattr(reason, "reply_code", None)
        reply_text = getattr(reason, "reply_text", None)
        if isinstance(reply_code, int) and isinstance(reply_text, str):
            return f"Channel.Close ({reply_code}): {reply_text}"
        return str(reason) if reason else "通道已关闭，Broker 未返回原因"

    def _lock_consumer_transport_error(
        self,
        reason: Any,
        generation: int | None = None,
    ) -> ReferenceStreamTransportError | None:
        """锁存消费通道的首个传输错误并使对应交付失效。"""
        target_generation = (
            self._consumer_channel_generation
            if generation is None
            else generation
        )
        managed_pending = next(
            (
                pending
                for pending in self._pending_deliveries.values()
                if pending.state == "pending"
                and pending.is_backend_owned
                and pending.channel_generation == target_generation
            ),
            None,
        )
        if managed_pending is None:
            return None
        if self._consumer_transport_error is None:
            self._consumer_transport_error = ReferenceStreamTransportError(
                "后端托管 REFERENCE 队列 "
                f"{managed_pending.queue_name} 消费通道失效: "
                f"{self._describe_transport_reason(reason)}"
            )
        for pending in self._pending_deliveries.values():
            if (
                pending.state == "pending"
                and pending.is_backend_owned
                and pending.channel_generation == target_generation
            ):
                pending.state = "invalidated"
                if pending.first_transport_error is None:
                    pending.first_transport_error = self._consumer_transport_error
        return self._consumer_transport_error

    def _on_consumer_channel_closed(
        self,
        channel: pika.channel.Channel,
        reason: Any,
        generation: int,
    ) -> None:
        """消费通道关闭时保留首个 Broker 根因。"""
        consumer_impl = getattr(self.consumer_channel, "_impl", None)
        if channel is not self.consumer_channel and channel is not consumer_impl:
            return
        error = self._lock_consumer_transport_error(reason, generation)
        if error is not None:
            logger.error("%s", error)

    def _on_publisher_channel_closed(
        self,
        channel: pika.channel.Channel,
        reason: Any,
    ) -> None:
        """记录发布通道关闭原因，后续发布可独立重建通道。"""
        publisher_impl = getattr(self.publisher_channel, "_impl", None)
        if (
            channel is self.publisher_channel or channel is publisher_impl
        ) and isinstance(reason, Exception):
            self._publisher_close_reason = reason

    def _consumer_channel_close_reason(self) -> Any:
        """返回当前消费通道已知的关闭原因。"""
        if self.connection is None or self.connection.is_closed:
            return "RabbitMQ 连接已关闭"
        channel = self.consumer_channel
        if channel is None:
            return "消费通道未创建"
        reason = getattr(channel, "closing_reason", None)
        if not isinstance(reason, Exception):
            channel_impl = getattr(channel, "_impl", None)
            reason = getattr(channel_impl, "_closing_reason", None)
        return reason if isinstance(reason, Exception) else "消费通道已关闭"

    def _expire_overdue_deliveries(self, now: float) -> None:
        """安全截止点到达时主动重入队，禁止晚到确认。"""
        overdue = [
            pending
            for pending in self._pending_deliveries.values()
            if pending.state == "pending"
            and pending.is_backend_owned
            and now >= pending.deadline_at
        ]
        if not overdue:
            return
        if not self._is_transport_open():
            self._lock_consumer_transport_error(
                self._consumer_channel_close_reason()
            )
            return
        if self.consumer_channel is None:
            return

        first = overdue[0]
        deadline_error = ReferenceStreamTransportError(
            "后端托管 REFERENCE 队列 "
            f"{first.queue_name} 消息处理超过 SDK 安全截止点 "
            f"({self.reference_consumer_ack_timeout_seconds:g}s - "
            f"{self.reference_consumer_ack_safety_margin_seconds:g}s 余量)"
        )
        self._consumer_transport_error = deadline_error
        try:
            self.consumer_channel.basic_nack(
                delivery_tag=0,
                multiple=True,
                requeue=True,
            )
        except Exception as exc:
            self._lock_consumer_transport_error(exc)
            logger.error(
                "%s，主动 NACK 失败: %s",
                deadline_error,
                self._describe_transport_reason(exc),
            )
            return
        for pending in self._pending_deliveries.values():
            if (
                pending.state == "pending"
                and pending.channel_generation == self._consumer_channel_generation
            ):
                pending.state = "invalidated"
                if pending.is_backend_owned:
                    pending.first_transport_error = deadline_error

    def raise_if_transport_failed(self, *, check_deadline: bool = True) -> None:
        """显式检查托管 REFERENCE 消费传输是否已不可恢复。"""
        if self._consumer_transport_error is not None:
            raise self._consumer_transport_error
        if self._first_managed_pending_delivery() is None:
            return
        if not self._is_transport_open():
            self._lock_consumer_transport_error(
                self._consumer_channel_close_reason()
            )
        elif check_deadline:
            self._expire_overdue_deliveries(time.monotonic())
        if self._consumer_transport_error is not None:
            raise self._consumer_transport_error

    def _ensure_consumer_channel(self) -> bool:
        """确保消费连接和原通道可用。"""
        self.raise_if_transport_failed()
        if not self.connection or self.connection.is_closed:
            return self.connect()
        if not self.consumer_channel or self.consumer_channel.is_closed:
            self._raise_for_managed_pending_reconnect()
            self._pending_deliveries.clear()
            self._fragment_assemblers.clear()
            try:
                self.consumer_channel = self._open_consumer_channel()
            except Exception as exc:
                self.consumer_channel = None
                logger.error("RabbitMQ 消费通道重建失败: %s", exc)
                return False
        return True

    def _ensure_publisher_channel(
        self,
        *,
        allow_consumer_failure: bool = False,
    ) -> bool:
        """确保发布连接和通道可用，不切换消费通道。"""
        if not allow_consumer_failure:
            self.raise_if_transport_failed()
        if not self.connection or self.connection.is_closed:
            return self.connect()
        if not self.publisher_channel or self.publisher_channel.is_closed:
            try:
                self.publisher_channel = self._open_publisher_channel()
                self._publisher_close_reason = None
            except Exception as exc:
                self.publisher_channel = None
                self._publisher_close_reason = exc
                logger.error("RabbitMQ 发布通道重建失败: %s", exc)
                return False
        return True

    def _ensure_connection(self) -> bool:
        """确保发布通道可用。"""
        return self._ensure_publisher_channel()

    def _is_backend_owned_reference_queue(self, queue_name: str) -> bool:
        """判断队列是否采用后端托管拓扑。"""
        return queue_name in self._backend_owned_reference_queues

    def _is_transport_open(self) -> bool:
        """判断当前 RabbitMQ 连接和消费通道是否同时可用。"""
        return bool(
            self.connection
            and not self.connection.is_closed
            and self.consumer_channel
            and not self.consumer_channel.is_closed
        )

    def _first_managed_pending_delivery(
        self,
        delivery_tags: List[int] | None = None,
    ) -> _PendingDelivery | None:
        """返回指定范围内首个后端托管的未确认消息。"""
        pending_deliveries = (
            self._pending_deliveries.values()
            if delivery_tags is None
            else (
                self._pending_deliveries.get(tag)
                for tag in delivery_tags
            )
        )
        return next(
            (
                pending
                for pending in pending_deliveries
                if pending is not None
                and pending.is_backend_owned
            ),
            None,
        )

    def _raise_for_managed_pending_reconnect(self) -> None:
        """存在托管未确认消息时禁止切换 RabbitMQ 通道。"""
        if self._consumer_transport_error is not None:
            raise self._consumer_transport_error
        managed_pending = self._first_managed_pending_delivery()
        if managed_pending:
            raise ReferenceStreamTransportError(
                "后端托管 REFERENCE 队列 "
                f"{managed_pending.queue_name} 存在未确认消息，拒绝重建连接或通道"
            )

    def _declare_queue(
        self,
        queue_name: str,
        channel: pika.channel.Channel,
    ) -> None:
        channel.queue_declare(
            queue=queue_name,
            durable=True,
            exclusive=False,
            auto_delete=False,
            arguments={},
        )

    def _prepare_queue(
        self,
        queue_name: str,
        channel: pika.channel.Channel,
    ) -> None:
        """仅为未注册为 Reference 流的普通外部队列主动声明队列。"""
        if not self._is_backend_owned_reference_queue(queue_name):
            self._declare_queue(queue_name, channel)

    def _publish_to_queue(
        self,
        queue_name: str,
        body: bytes | str,
        properties: pika.BasicProperties,
        *,
        prepare: bool = True,
    ) -> Any:
        """按队列拓扑声明并发布消息。"""
        if self.publisher_channel is None:
            raise RuntimeError("RabbitMQ 发布通道未创建")
        if prepare:
            self._prepare_queue(queue_name, self.publisher_channel)
        publish_kwargs: dict[str, Any] = {
            "exchange": "",
            "routing_key": queue_name,
            "body": body,
            "properties": properties,
        }
        if self._is_backend_owned_reference_queue(queue_name):
            publish_kwargs["mandatory"] = True
        return self.publisher_channel.basic_publish(**publish_kwargs)

    def _ack_delivery(self, logical_id: int) -> None:
        """确认逻辑消息对应的所有物理交付。"""
        pending = self._pending_deliveries[logical_id]
        if self.consumer_channel is None:
            raise RuntimeError("RabbitMQ 消费通道未创建")
        for physical_tag in pending.physical_tags:
            self.consumer_channel.basic_ack(delivery_tag=physical_tag)
        pending.state = "settled"
        self._pending_deliveries.pop(logical_id, None)

    def _nack_delivery(self, logical_id: int, requeue: bool) -> None:
        """拒绝逻辑消息对应的所有物理交付。"""
        pending = self._pending_deliveries[logical_id]
        if self.consumer_channel is None:
            raise RuntimeError("RabbitMQ 消费通道未创建")
        for physical_tag in pending.physical_tags:
            self.consumer_channel.basic_nack(
                delivery_tag=physical_tag,
                requeue=requeue,
            )
        pending.state = "settled"
        self._pending_deliveries.pop(logical_id, None)

    def close(self) -> None:
        """关闭 RabbitMQ 连接。"""
        try:
            if self.publisher_channel and not self.publisher_channel.is_closed:
                self.publisher_channel.close()
            if (
                self.consumer_channel
                and self.consumer_channel is not self.publisher_channel
                and not self.consumer_channel.is_closed
            ):
                self.consumer_channel.close()
            if self.connection and not self.connection.is_closed:
                self.connection.close()
            logger.info("RabbitMQ 连接已关闭")
        except Exception as exc:
            logger.error("关闭连接时发生错误: %s", exc)
        finally:
            self._pending_deliveries.clear()
            self._fragment_assemblers.clear()
            self.consumer_channel = None
            self.publisher_channel = None
            self.connection = None

    @staticmethod
    def _control_type(properties: Any) -> str | None:
        message_type = getattr(properties, "type", None)
        if message_type in {REFERENCE_EOS_TYPE, REFERENCE_ABORT_TYPE}:
            return message_type
        return None

    @staticmethod
    def _producer_id(properties: Any) -> str | None:
        headers = getattr(properties, "headers", None) or {}
        producer_id = headers.get("x-csi-producer-id")
        if isinstance(producer_id, bytes):
            producer_id = producer_id.decode("utf-8", errors="replace")
        return str(producer_id) if producer_id else None

    @staticmethod
    def _stream_id(properties: Any) -> str | None:
        headers = getattr(properties, "headers", None) or {}
        stream_id = headers.get("x-csi-stream-id")
        if isinstance(stream_id, bytes):
            stream_id = stream_id.decode("utf-8", errors="replace")
        return str(stream_id) if stream_id else None

    @staticmethod
    def _message_id(properties: Any) -> str | None:
        """读取业务消息的 AMQP message_id。"""
        message_id = getattr(properties, "message_id", None)
        if isinstance(message_id, bytes):
            message_id = message_id.decode("utf-8", errors="replace")
        return str(message_id) if message_id is not None else None

    @staticmethod
    def _resolve_message_id(message_id: str | None) -> str:
        """生成或校验 AMQP message_id。"""
        if message_id is None:
            return uuid4().hex
        if not isinstance(message_id, str):
            raise TypeError("message_id 必须是字符串或 None")
        if not message_id:
            raise ValueError("message_id 不能为空")
        if len(message_id.encode("utf-8")) > MESSAGE_ID_MAX_BYTES:
            raise ValueError(
                f"message_id 的 UTF-8 长度不能超过 {MESSAGE_ID_MAX_BYTES} 字节"
            )
        return message_id

    def _build_business_publications(
        self,
        message: dict,
        message_id: str,
    ) -> list[tuple[bytes, pika.BasicProperties]]:
        """将业务对象编码为一个普通消息或多个协议分片。"""
        body = json.dumps(message, ensure_ascii=False).encode("utf-8")
        fragments = encode_fragments(body, message_id, self._fragment_settings)
        if not fragments:
            return [
                (
                    body,
                    pika.BasicProperties(
                        delivery_mode=2,
                        message_id=message_id,
                        content_type="application/json",
                        content_encoding="utf-8",
                    ),
                )
            ]

        logger.info(
            "RabbitMQ 业务消息已分片: message_id=%s, bytes=%s, fragments=%s",
            message_id,
            len(body),
            len(fragments),
        )
        return [
            (
                fragment.body,
                pika.BasicProperties(
                    delivery_mode=2,
                    message_id=fragment.message_id,
                    content_type="application/json",
                    content_encoding="utf-8",
                    type=FRAGMENT_MESSAGE_TYPE,
                    headers=fragment.headers,
                ),
            )
            for fragment in fragments
        ]

    def _handle_control(
        self,
        queue_name: str,
        delivery_tag: int,
        properties: Any,
    ) -> None:
        state = self._reference_inputs[queue_name]
        control_type = self._control_type(properties)
        producer_id = self._producer_id(properties)
        stream_id = self._stream_id(properties)
        self._ack_delivery(delivery_tag)

        if stream_id and stream_id != state.stream_id:
            raise ReferenceStreamAborted(
                f"REFERENCE 控制帧流ID不匹配: {stream_id}"
            )
        if producer_id is None and len(state.expected_producer_ids) == 1:
            producer_id = next(iter(state.expected_producer_ids))
        previous_terminal = (
            state.terminal_by_producer_id.get(producer_id)
            if producer_id
            else None
        )
        if previous_terminal is not None:
            if previous_terminal == REFERENCE_ABORT_TYPE:
                raise ReferenceStreamAborted(
                    state.abort_error
                    or f"REFERENCE 数据流 {state.stream_id} 已中止"
                )
            return

        if control_type == REFERENCE_ABORT_TYPE:
            if producer_id:
                state.terminal_by_producer_id[producer_id] = control_type
            state.aborted = True
            state.abort_error = (
                f"REFERENCE 数据流 {state.stream_id} 被生产者"
                f" {producer_id or 'unknown'} 中止"
            )
            raise ReferenceStreamAborted(state.abort_error)

        if producer_id:
            state.terminal_by_producer_id[producer_id] = str(control_type)
            state.completed_producer_ids.add(producer_id)

        if state.expected_producer_ids:
            state.completed = state.expected_producer_ids.issubset(
                state.completed_producer_ids
            )
        else:
            state.completed = True

    def _next_delivery(
        self,
        queue_name: str,
        *,
        wait_for_data: bool,
    ) -> tuple[Any, Any, bytes] | None:
        state = self._reference_inputs.get(queue_name)
        if state and state.aborted:
            raise ReferenceStreamAborted(
                state.abort_error
                or f"REFERENCE 数据流 {state.stream_id} 已中止"
            )
        if state and state.completed:
            return None

        while True:
            self.raise_if_transport_failed()
            if self._cancel_check:
                try:
                    self._cancel_check()
                except Exception as exc:
                    raise _CancellationSignal(exc) from exc
            if self.consumer_channel is None:
                raise RuntimeError("RabbitMQ 消费通道未创建")
            method_frame, properties, body = self.consumer_channel.basic_get(
                queue=queue_name,
                auto_ack=False,
            )
            if method_frame is None:
                if state is None or not wait_for_data:
                    return None
                self.process_data_events()
                if self._cancel_check:
                    try:
                        self._cancel_check()
                    except Exception as exc:
                        raise _CancellationSignal(exc) from exc
                time.sleep(self._poll_interval)
                continue

            logical_id = self._next_logical_delivery_id
            self._next_logical_delivery_id += 1
            received_at = time.monotonic()
            logical_frame = _LogicalDeliveryFrame(
                delivery_tag=logical_id,
                exchange=method_frame.exchange,
                routing_key=method_frame.routing_key,
                redelivered=method_frame.redelivered,
            )
            self._pending_deliveries[logical_id] = _PendingDelivery(
                logical_id=logical_id,
                physical_tags=(method_frame.delivery_tag,),
                queue_name=queue_name,
                is_backend_owned=self._is_backend_owned_reference_queue(queue_name),
                channel_generation=self._consumer_channel_generation,
                received_at=received_at,
                deadline_at=(
                    received_at
                    + self.reference_consumer_ack_timeout_seconds
                    - self.reference_consumer_ack_safety_margin_seconds
                ),
            )

            if state and self._control_type(properties):
                assembler = self._fragment_assemblers.get(queue_name)
                if (
                    assembler
                    and assembler.has_pending
                    and self._control_type(properties) == REFERENCE_ABORT_TYPE
                ):
                    for token in assembler.discard_pending():
                        self._ack_delivery(token.method_frame.delivery_tag)
                self._handle_control(
                    queue_name,
                    logical_id,
                    properties,
                )
                if assembler and assembler.has_pending and state.completed:
                    for token in assembler.discard_pending():
                        self._ack_delivery(token.method_frame.delivery_tag)
                    raise FragmentProtocolError(
                        f"REFERENCE 数据流 {state.stream_id} 结束时存在未完整消息分片"
                    )
                if state.completed:
                    return None
                continue
            return logical_frame, properties, body

    def _next_business_delivery(
        self,
        queue_name: str,
        *,
        wait_for_data: bool,
    ) -> tuple[Any, Any, bytes] | None:
        """读取下一条完整业务消息，并在内部透明重组物理分片。"""
        while True:
            delivery = self._next_delivery(
                queue_name,
                wait_for_data=wait_for_data,
            )
            if delivery is None:
                return None
            method_frame, properties, body = delivery
            fragment = parse_fragment(
                body,
                getattr(properties, "type", None),
                getattr(properties, "headers", None),
                self._fragment_settings,
            )
            if fragment is None:
                return delivery

            assembler = self._fragment_assemblers.setdefault(
                queue_name,
                FragmentAssembler(self._fragment_settings),
            )
            assembled = assembler.add(
                fragment,
                _FragmentDeliveryToken(method_frame, properties),
            )
            if assembled is None:
                continue

            primary = assembled.tokens[0]
            primary_logical_id = primary.method_frame.delivery_tag
            primary_pending = self._pending_deliveries[primary_logical_id]
            merged_pending = [
                self._pending_deliveries[token.method_frame.delivery_tag]
                for token in assembled.tokens
            ]
            primary_pending.physical_tags = tuple(
                physical_tag
                for pending in merged_pending
                for physical_tag in pending.physical_tags
            )
            primary_pending.received_at = min(
                pending.received_at for pending in merged_pending
            )
            primary_pending.deadline_at = min(
                pending.deadline_at for pending in merged_pending
            )
            for pending in merged_pending[1:]:
                self._pending_deliveries.pop(pending.logical_id, None)
            logical_properties = pika.BasicProperties(
                content_type=getattr(primary.properties, "content_type", None),
                content_encoding=getattr(
                    primary.properties,
                    "content_encoding",
                    None,
                ),
                delivery_mode=getattr(primary.properties, "delivery_mode", None),
                priority=getattr(primary.properties, "priority", None),
                correlation_id=getattr(
                    primary.properties,
                    "correlation_id",
                    None,
                ),
                reply_to=getattr(primary.properties, "reply_to", None),
                expiration=getattr(primary.properties, "expiration", None),
                message_id=assembled.message_id,
                timestamp=getattr(primary.properties, "timestamp", None),
                type=None,
                user_id=getattr(primary.properties, "user_id", None),
                app_id=getattr(primary.properties, "app_id", None),
            )
            return primary.method_frame, logical_properties, assembled.body

    def get_message(self, queue_name: str) -> Optional[Dict[str, Any]]:
        """从队列获取单条业务消息，没有消息或流结束时返回 None。"""
        if not self._ensure_consumer_channel():
            if self._is_backend_owned_reference_queue(queue_name):
                raise ReferenceStreamTransportError(
                    f"后端托管 REFERENCE 队列 {queue_name} 连接不可用"
                )
            logger.error("无法连接到 RabbitMQ")
            return None
        if not self.consumer_channel:
            if self._is_backend_owned_reference_queue(queue_name):
                raise ReferenceStreamTransportError(
                    f"后端托管 REFERENCE 队列 {queue_name} 通道不可用"
                )
            logger.error("RabbitMQ 通道未创建")
            return None

        try:
            self._prepare_queue(queue_name, self.consumer_channel)
            delivery = self._next_business_delivery(
                queue_name,
                wait_for_data=queue_name in self._reference_inputs,
            )
            if delivery is None:
                return None
            method_frame, properties, body = delivery
            return {
                "body": body.decode("utf-8"),
                "delivery_tag": method_frame.delivery_tag,
                "message_id": self._message_id(properties),
            }
        except _CancellationSignal as signal:
            raise signal.error
        except ReferenceStreamTransportError:
            raise
        except ReferenceStreamAborted:
            raise
        except Exception as exc:
            if self._is_backend_owned_reference_queue(queue_name):
                error = self._consumer_transport_error
                if error is None:
                    error = self._lock_consumer_transport_error(exc)
                if error is not None:
                    raise error from exc
                raise ReferenceStreamTransportError(
                    f"后端托管 REFERENCE 队列 {queue_name} 读取失败: {exc}"
                ) from exc
            logger.error("获取消息失败: %s", exc)
            return None

    def ack_message(self, delivery_tag: int) -> bool:
        """确认消息。"""
        pending = self._pending_deliveries.get(delivery_tag)
        if pending is None:
            return False
        if pending.first_transport_error is not None:
            raise pending.first_transport_error
        if pending.is_backend_owned:
            self.raise_if_transport_failed()
        if pending.state != "pending":
            return False
        if pending.channel_generation != self._consumer_channel_generation:
            if pending.is_backend_owned:
                error = self._lock_consumer_transport_error(
                    "消费通道代次已变更",
                    pending.channel_generation,
                )
                if error is not None:
                    raise error
            self._pending_deliveries.pop(delivery_tag, None)
            return False
        if not self._is_transport_open():
            if pending.is_backend_owned:
                error = self._lock_consumer_transport_error(
                    self._consumer_channel_close_reason(),
                    pending.channel_generation,
                )
                if error is not None:
                    raise error
            self._pending_deliveries.pop(delivery_tag, None)
            return False
        try:
            self._ack_delivery(delivery_tag)
            return True
        except Exception as exc:
            if pending.is_backend_owned:
                error = self._lock_consumer_transport_error(
                    exc,
                    pending.channel_generation,
                )
                if error is not None:
                    raise error from exc
            if not self._is_transport_open():
                self._pending_deliveries.pop(delivery_tag, None)
            logger.error("确认消息失败: %s", exc)
            return False

    def nack_message(self, delivery_tag: int, requeue: bool = True) -> bool:
        """拒绝消息。"""
        pending = self._pending_deliveries.get(delivery_tag)
        if pending is None:
            return False
        if pending.first_transport_error is not None:
            raise pending.first_transport_error
        if pending.is_backend_owned:
            self.raise_if_transport_failed()
        if pending.state != "pending":
            return False
        if pending.channel_generation != self._consumer_channel_generation:
            if pending.is_backend_owned:
                error = self._lock_consumer_transport_error(
                    "消费通道代次已变更",
                    pending.channel_generation,
                )
                if error is not None:
                    raise error
            self._pending_deliveries.pop(delivery_tag, None)
            return False
        if not self._is_transport_open():
            if pending.is_backend_owned:
                error = self._lock_consumer_transport_error(
                    self._consumer_channel_close_reason(),
                    pending.channel_generation,
                )
                if error is not None:
                    raise error
            self._pending_deliveries.pop(delivery_tag, None)
            return False
        try:
            self._nack_delivery(delivery_tag, requeue)
            return True
        except Exception as exc:
            if pending.is_backend_owned:
                error = self._lock_consumer_transport_error(
                    exc,
                    pending.channel_generation,
                )
                if error is not None:
                    raise error from exc
            if not self._is_transport_open():
                self._pending_deliveries.pop(delivery_tag, None)
            logger.error("拒绝消息失败: %s", exc)
            return False

    def send_message(
        self,
        queue_name: str,
        message: dict,
        message_id: str | None = None,
    ) -> bool:
        """发送业务消息到队列。"""
        resolved_message_id = self._resolve_message_id(message_id)
        if not self._ensure_connection():
            if self._is_backend_owned_reference_queue(queue_name):
                raise ReferenceStreamTransportError(
                    f"后端托管 REFERENCE 队列 {queue_name} 连接不可用"
                )
            logger.error("无法连接到 RabbitMQ")
            return False
        if not self.publisher_channel:
            if self._is_backend_owned_reference_queue(queue_name):
                raise ReferenceStreamTransportError(
                    f"后端托管 REFERENCE 队列 {queue_name} 通道不可用"
                )
            logger.error("RabbitMQ 通道未创建")
            return False

        try:
            publications = self._build_business_publications(
                message,
                resolved_message_id,
            )
            self._prepare_queue(queue_name, self.publisher_channel)
            for body, properties in publications:
                published = self._publish_to_queue(
                    queue_name,
                    body=body,
                    properties=properties,
                    prepare=False,
                )
                if published is False:
                    if self._is_backend_owned_reference_queue(queue_name):
                        raise ReferenceStreamTransportError(
                            f"后端托管 REFERENCE 队列 {queue_name} 发布未获确认"
                        )
                    logger.error("RabbitMQ 拒绝确认业务消息: %s", queue_name)
                    return False
            if message and queue_name in self._reference_result_queues:
                self._notify_successful_result()
            return True
        except ReferenceStreamTransportError:
            raise
        except Exception as exc:
            if self._is_backend_owned_reference_queue(queue_name):
                raise ReferenceStreamTransportError(
                    f"后端托管 REFERENCE 队列 {queue_name} 发布失败: {exc}"
                ) from exc
            logger.error("发送消息失败: %s", exc)
            return False

    def send_messages_batch(
        self,
        queue_names: List[str],
        message: dict,
        message_id: str | None = None,
    ) -> int:
        """批量发送同一条业务消息到多个队列。"""
        resolved_message_id = self._resolve_message_id(message_id)
        success_count = 0
        for queue_name in queue_names:
            if self.send_message(queue_name, message, resolved_message_id):
                success_count += 1
        return success_count

    def _publish_control(
        self,
        queue_name: str,
        stream_id: str,
        producer_id: str,
        action_id: str,
        control_type: str,
    ) -> bool:
        identity = (control_type, queue_name, stream_id, producer_id)
        if identity in self._published_controls:
            return True
        if not self._ensure_publisher_channel(
            allow_consumer_failure=control_type == REFERENCE_ABORT_TYPE,
        ) or not self.publisher_channel:
            if self._is_backend_owned_reference_queue(queue_name):
                raise ReferenceStreamTransportError(
                    f"后端托管 REFERENCE 队列 {queue_name} 连接或通道不可用"
                )
            return False

        try:
            body = json.dumps(
                {
                    "stream_id": stream_id,
                    "producer_id": producer_id,
                    "action_id": action_id,
                    "status": (
                        "success"
                        if control_type == REFERENCE_EOS_TYPE
                        else "aborted"
                    ),
                },
                ensure_ascii=False,
            )
            published = self._publish_to_queue(
                queue_name,
                body=body,
                properties=pika.BasicProperties(
                    delivery_mode=2,
                    type=control_type,
                    content_type=REFERENCE_CONTROL_CONTENT_TYPE,
                    message_id=(
                        f"eos:{stream_id}:{producer_id}"
                        if control_type == REFERENCE_EOS_TYPE
                        else f"abort:{stream_id}:{producer_id}"
                    ),
                    correlation_id=action_id,
                    headers={
                        "x-csi-producer-id": producer_id,
                        "x-csi-stream-id": stream_id,
                    },
                ),
            )
            if published is False:
                if self._is_backend_owned_reference_queue(queue_name):
                    raise ReferenceStreamTransportError(
                        f"后端托管 REFERENCE 队列 {queue_name} 控制帧未获确认"
                    )
                return False
            self._published_controls.add(identity)
            return True
        except ReferenceStreamTransportError:
            raise
        except Exception as exc:
            if self._is_backend_owned_reference_queue(queue_name):
                raise ReferenceStreamTransportError(
                    f"后端托管 REFERENCE 队列 {queue_name} 控制帧发布失败: {exc}"
                ) from exc
            logger.error("发送 REFERENCE 控制帧失败: %s", exc)
            return False

    def close_reference_outputs(
        self,
        *,
        action_id: str,
        producer_id: str,
        status: str,
    ) -> bool:
        """向当前组件的全部 EOS v1 输出流发送终止控制帧。"""
        if status == "success":
            self.raise_if_transport_failed()
        control_type = (
            REFERENCE_EOS_TYPE if status == "success" else REFERENCE_ABORT_TYPE
        )
        succeeded = True
        for output in self._reference_outputs:
            if not self._publish_control(
                output.queue_name,
                output.stream_id,
                producer_id,
                action_id,
                control_type,
            ):
                succeeded = False
        return succeeded

    def consume_all(
        self,
        queue_name: str,
        callback: Callable[[list], bool],
        batch_size: int = 100,
    ) -> int:
        """消费当前队列的全部业务消息，EOS v1 流等待生产者结束。"""
        if not self._ensure_consumer_channel():
            if self._is_backend_owned_reference_queue(queue_name):
                raise ReferenceStreamTransportError(
                    f"后端托管 REFERENCE 队列 {queue_name} 连接不可用"
                )
            logger.error("无法连接到 RabbitMQ")
            return 0
        if not self.consumer_channel:
            if self._is_backend_owned_reference_queue(queue_name):
                raise ReferenceStreamTransportError(
                    f"后端托管 REFERENCE 队列 {queue_name} 通道不可用"
                )
            logger.error("RabbitMQ 通道未创建")
            return 0

        processed_count = 0
        try:
            self._prepare_queue(queue_name, self.consumer_channel)
            is_reference = queue_name in self._reference_inputs
            while True:
                batch_messages = []
                delivery_tags: list[int] = []
                stream_ended = False

                for index in range(batch_size):
                    delivery = self._next_business_delivery(
                        queue_name,
                        wait_for_data=is_reference and index == 0,
                    )
                    if delivery is None:
                        stream_ended = bool(
                            is_reference
                            and self._reference_inputs[queue_name].completed
                        )
                        break
                    method_frame, properties, body = delivery
                    try:
                        body_str = body.decode("utf-8")
                        props_dict = {
                            "delivery_tag": method_frame.delivery_tag,
                            "exchange": method_frame.exchange,
                            "routing_key": method_frame.routing_key,
                            "redelivered": method_frame.redelivered,
                            "message_id": self._message_id(properties),
                        }
                        batch_messages.append((body_str, props_dict))
                        delivery_tags.append(method_frame.delivery_tag)
                    except Exception as exc:
                        logger.error("解码消息失败: %s", exc)

                if batch_messages:
                    try:
                        success = callback(batch_messages)
                    except Exception as exc:
                        logger.error("批量处理消息时发生错误: %s", exc)
                        for delivery_tag in delivery_tags:
                            self.nack_message(delivery_tag, True)
                    else:
                        if success:
                            self.ack_all_message(delivery_tags)
                            processed_count += len(batch_messages)
                        else:
                            for delivery_tag in delivery_tags:
                                self.nack_message(delivery_tag, True)

                if stream_ended or (not is_reference and not batch_messages):
                    break
            return processed_count
        except _CancellationSignal as signal:
            raise signal.error
        except ReferenceStreamTransportError:
            raise
        except ReferenceStreamAborted:
            raise
        except AMQPChannelError as exc:
            if self._is_backend_owned_reference_queue(queue_name):
                error = self._consumer_transport_error
                if error is None:
                    error = self._lock_consumer_transport_error(exc)
                if error is not None:
                    raise error from exc
                raise ReferenceStreamTransportError(
                    f"后端托管 REFERENCE 队列 {queue_name} 消费失败: {exc}"
                ) from exc
            logger.error("消费消息失败: %s", exc)
            return processed_count
        except Exception as exc:
            if self._is_backend_owned_reference_queue(queue_name):
                error = self._consumer_transport_error
                if error is None:
                    error = self._lock_consumer_transport_error(exc)
                if error is not None:
                    raise error from exc
                raise ReferenceStreamTransportError(
                    f"后端托管 REFERENCE 队列 {queue_name} 消费失败: {exc}"
                ) from exc
            logger.error("消费消息异常: %s", exc)
            return processed_count

    def read_messages(
        self,
        queue_name: str,
        batch_size: int = 100,
    ) -> List[Dict[str, Any]]:
        """批量读取业务消息（不自动确认），控制帧由 SDK 自动确认。"""
        if not self._ensure_consumer_channel():
            if self._is_backend_owned_reference_queue(queue_name):
                raise ReferenceStreamTransportError(
                    f"后端托管 REFERENCE 队列 {queue_name} 连接不可用"
                )
            logger.error("无法连接到 RabbitMQ")
            return []
        if not self.consumer_channel:
            if self._is_backend_owned_reference_queue(queue_name):
                raise ReferenceStreamTransportError(
                    f"后端托管 REFERENCE 队列 {queue_name} 通道不可用"
                )
            logger.error("RabbitMQ 通道未创建")
            return []

        messages = []
        try:
            self._prepare_queue(queue_name, self.consumer_channel)
            is_reference = queue_name in self._reference_inputs
            while len(messages) < batch_size:
                delivery = self._next_business_delivery(
                    queue_name,
                    wait_for_data=is_reference and not messages,
                )
                if delivery is None:
                    break
                method_frame, properties, body = delivery
                try:
                    messages.append(
                        {
                            "body": json.loads(body.decode("utf-8")),
                            "delivery_tag": method_frame.delivery_tag,
                            "message_id": self._message_id(properties),
                        }
                    )
                except json.JSONDecodeError as exc:
                    logger.error("消息JSON解析失败: %s，跳过该消息", exc)
                    self.ack_message(method_frame.delivery_tag)
            return messages
        except _CancellationSignal as signal:
            raise signal.error
        except ReferenceStreamTransportError:
            raise
        except ReferenceStreamAborted:
            raise
        except Exception as exc:
            if self._is_backend_owned_reference_queue(queue_name):
                error = self._consumer_transport_error
                if error is None:
                    error = self._lock_consumer_transport_error(exc)
                if error is not None:
                    raise error from exc
                raise ReferenceStreamTransportError(
                    f"后端托管 REFERENCE 队列 {queue_name} 读取失败: {exc}"
                ) from exc
            logger.error("读取消息失败: %s", exc)
            return []

    def ack_all_message(self, delivery_tags: List[int]) -> bool:
        """批量确认消息。"""
        logical_tags = list(dict.fromkeys(delivery_tags))
        if any(tag not in self._pending_deliveries for tag in logical_tags):
            return False
        for logical_tag in logical_tags:
            if not self.ack_message(logical_tag):
                return False
        return True

    def publish_messages(
        self,
        queue_name: str | List[str],
        messages: List[Dict[str, Any]],
        message_ids: List[str | None] | None = None,
    ) -> bool:
        """逐条生成消息ID，并将一批业务消息发布到一个或多个队列。"""
        queue_names = [queue_name] if isinstance(queue_name, str) else queue_name
        if not queue_names or any(
            not isinstance(item, str) or not item for item in queue_names
        ):
            raise ValueError("queue_name 必须包含至少一个有效队列名")
        if message_ids is not None and len(message_ids) != len(messages):
            raise ValueError("message_ids 数量必须与 messages 一致")
        resolved_message_ids = [
            self._resolve_message_id(
                message_ids[index] if message_ids is not None else None
            )
            for index in range(len(messages))
        ]
        if not self._ensure_connection():
            managed_queue = next(
                (
                    item
                    for item in queue_names
                    if self._is_backend_owned_reference_queue(item)
                ),
                None,
            )
            if managed_queue:
                raise ReferenceStreamTransportError(
                    f"后端托管 REFERENCE 队列 {managed_queue} 连接不可用"
                )
            logger.error("无法连接到 RabbitMQ")
            return False
        if not self.publisher_channel:
            managed_queue = next(
                (
                    item
                    for item in queue_names
                    if self._is_backend_owned_reference_queue(item)
                ),
                None,
            )
            if managed_queue:
                raise ReferenceStreamTransportError(
                    f"后端托管 REFERENCE 队列 {managed_queue} 通道不可用"
                )
            logger.error("RabbitMQ 通道未创建")
            return False

        active_queue: str | None = None
        try:
            for target_queue in dict.fromkeys(queue_names):
                active_queue = target_queue
                self._prepare_queue(target_queue, self.publisher_channel)
            for message, resolved_message_id in zip(
                messages,
                resolved_message_ids,
            ):
                publications = self._build_business_publications(
                    message,
                    resolved_message_id,
                )
                completed_publications = {
                    target_queue: 0 for target_queue in dict.fromkeys(queue_names)
                }
                result_reported = False
                for body, properties in publications:
                    for target_queue in dict.fromkeys(queue_names):
                        active_queue = target_queue
                        published = self._publish_to_queue(
                            target_queue,
                            body=body,
                            properties=properties,
                            prepare=False,
                        )
                        if published is False:
                            if self._is_backend_owned_reference_queue(target_queue):
                                raise ReferenceStreamTransportError(
                                    "后端托管 REFERENCE 队列 "
                                    f"{target_queue} 批量发布未获确认"
                                )
                            logger.error(
                                "RabbitMQ 拒绝确认批量业务消息: %s",
                                target_queue,
                            )
                            return False
                        completed_publications[target_queue] += 1
                        if (
                            message
                            and not result_reported
                            and target_queue in self._reference_result_queues
                            and completed_publications[target_queue]
                            == len(publications)
                        ):
                            self._notify_successful_result()
                            result_reported = True
            return True
        except ReferenceStreamTransportError:
            raise
        except Exception as exc:
            if active_queue and self._is_backend_owned_reference_queue(
                active_queue
            ):
                raise ReferenceStreamTransportError(
                    "后端托管 REFERENCE 队列 "
                    f"{active_queue} 批量发布失败: {exc}"
                ) from exc
            logger.error("批量发布消息失败: %s", exc)
            return False

    def process_data_events(self) -> None:
        """处理心跳并立即传播托管消费通道的失效根因。"""
        self.raise_if_transport_failed()
        try:
            if self.connection and not self.connection.is_closed:
                self.connection.process_data_events()
        except Exception as exc:
            error = self._consumer_transport_error
            if error is None:
                error = self._lock_consumer_transport_error(exc)
            if error is not None:
                raise error from exc
            logger.warning("处理连接事件时发生错误: %s", exc)
        self.raise_if_transport_failed()
