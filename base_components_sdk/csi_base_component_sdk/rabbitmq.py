from __future__ import annotations

import json
import logging
import os
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional

import pika
from pika.exceptions import AMQPChannelError, AMQPConnectionError

logger = logging.getLogger("CSI_SDK")

REFERENCE_EOS_TYPE = "csi.reference.eos.v1"
REFERENCE_ABORT_TYPE = "csi.reference.abort.v1"
REFERENCE_CONTROL_CONTENT_TYPE = (
    "application/vnd.cyberspacein.reference-control+json"
)
REFERENCE_PROTOCOL = "eos-v1"


class ReferenceStreamAborted(RuntimeError):
    """REFERENCE 数据流被生产者中止。"""


class _CancellationSignal(BaseException):
    """将取消检查异常穿过 RabbitMQ 的兼容错误处理层。"""

    def __init__(self, error: Exception):
        super().__init__(str(error))
        self.error = error


@dataclass
class _ReferenceInputState:
    stream_id: str
    expected_producer_ids: set[str] = field(default_factory=set)
    completed_producer_ids: set[str] = field(default_factory=set)
    completed: bool = False


@dataclass(frozen=True)
class _ReferenceOutput:
    queue_name: str
    stream_id: str


class RabbitMQClient:
    """SDK 内置 RabbitMQ 客户端，支持 REFERENCE EOS 协议。"""

    def __init__(
        self,
        host: str = None,
        port: int = None,
        username: str = None,
        password: str = None,
        vhost: str = None,
    ):
        self.host = host or os.getenv("RABBITMQ_HOST", "localhost")
        self.port = port or int(os.getenv("RABBITMQ_PORT", "5672"))
        self.username = username or os.getenv("RABBITMQ_USERNAME", "guest")
        self.password = password or os.getenv("RABBITMQ_PASSWORD", "guest")
        self.vhost = vhost or os.getenv("RABBITMQ_VHOST", "/")

        self.connection: Optional[pika.BlockingConnection] = None
        self.channel: Optional[pika.channel.Channel] = None
        self._reference_inputs: dict[str, _ReferenceInputState] = {}
        self._reference_outputs: list[_ReferenceOutput] = []
        self._published_controls: set[tuple[str, str, str, str]] = set()
        self._cancel_check: Callable[[], None] | None = None
        self._poll_interval = max(
            0.01,
            float(os.getenv("CSI_REFERENCE_POLL_INTERVAL", "0.1")),
        )

    def configure_reference_streams(
        self,
        inputs: dict[str, Any],
        outputs: dict[str, Any],
        cancel_check: Callable[[], None] | None = None,
    ) -> None:
        """注册运行上下文中的 EOS v1 输入输出流。"""
        self._reference_inputs.clear()
        self._reference_outputs.clear()
        self._cancel_check = cancel_check

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
            for stream in io_value.get("streams") or []:
                if not isinstance(stream, dict) or stream.get("protocol") != REFERENCE_PROTOCOL:
                    continue
                queue_name = stream.get("queue_name")
                stream_id = stream.get("stream_id")
                if not isinstance(queue_name, str) or not queue_name:
                    continue
                if not isinstance(stream_id, str) or not stream_id:
                    stream_id = queue_name
                identity = (queue_name, stream_id)
                if identity not in seen_outputs:
                    self._reference_outputs.append(
                        _ReferenceOutput(queue_name=queue_name, stream_id=stream_id)
                    )
                    seen_outputs.add(identity)

    @property
    def has_reference_outputs(self) -> bool:
        """返回当前上下文是否声明了 EOS v1 输出流。"""
        return bool(self._reference_outputs)

    def connect(self) -> bool:
        """建立 RabbitMQ 连接和通道。"""
        try:
            credentials = pika.PlainCredentials(self.username, self.password)
            parameters = pika.ConnectionParameters(
                host=self.host,
                port=self.port,
                virtual_host=self.vhost,
                credentials=credentials,
            )

            self.connection = pika.BlockingConnection(parameters)
            self.channel = self.connection.channel()
            self.channel.confirm_delivery()
            logger.info("RabbitMQ 连接成功: %s:%s", self.host, self.port)
            return True
        except AMQPConnectionError as exc:
            logger.error("RabbitMQ 连接失败: %s", exc)
            return False
        except Exception as exc:
            logger.error("RabbitMQ 连接异常: %s", exc)
            return False

    def _ensure_connection(self) -> bool:
        """确保连接可用，如果断开则重连。"""
        if not self.connection or self.connection.is_closed:
            return self.connect()
        return True

    def _declare_queue(self, queue_name: str) -> None:
        self.channel.queue_declare(
            queue=queue_name,
            durable=True,
            exclusive=False,
            auto_delete=False,
            arguments={},
        )

    def close(self) -> None:
        """关闭 RabbitMQ 连接。"""
        try:
            if self.channel and not self.channel.is_closed:
                self.channel.close()
            if self.connection and not self.connection.is_closed:
                self.connection.close()
            logger.info("RabbitMQ 连接已关闭")
        except Exception as exc:
            logger.error("关闭连接时发生错误: %s", exc)

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
        self.channel.basic_ack(delivery_tag=delivery_tag)

        if stream_id and stream_id != state.stream_id:
            raise ReferenceStreamAborted(
                f"REFERENCE 控制帧流ID不匹配: {stream_id}"
            )
        if control_type == REFERENCE_ABORT_TYPE:
            raise ReferenceStreamAborted(
                f"REFERENCE 数据流 {state.stream_id} 被生产者"
                f" {producer_id or 'unknown'} 中止"
            )

        if producer_id is None and len(state.expected_producer_ids) == 1:
            producer_id = next(iter(state.expected_producer_ids))
        if producer_id:
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
        if state and state.completed:
            return None

        while True:
            if self._cancel_check:
                try:
                    self._cancel_check()
                except Exception as exc:
                    raise _CancellationSignal(exc) from exc
            method_frame, properties, body = self.channel.basic_get(
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

            if state and self._control_type(properties):
                self._handle_control(
                    queue_name,
                    method_frame.delivery_tag,
                    properties,
                )
                if state.completed:
                    return None
                continue
            return method_frame, properties, body

    def get_message(self, queue_name: str) -> Optional[Dict[str, Any]]:
        """从队列获取单条业务消息，没有消息或流结束时返回 None。"""
        if not self._ensure_connection():
            logger.error("无法连接到 RabbitMQ")
            return None
        if not self.channel:
            logger.error("RabbitMQ 通道未创建")
            return None

        try:
            self._declare_queue(queue_name)
            delivery = self._next_delivery(
                queue_name,
                wait_for_data=queue_name in self._reference_inputs,
            )
            if delivery is None:
                return None
            method_frame, _properties, body = delivery
            return {
                "body": body.decode("utf-8"),
                "delivery_tag": method_frame.delivery_tag,
            }
        except _CancellationSignal as signal:
            raise signal.error
        except ReferenceStreamAborted:
            raise
        except Exception as exc:
            logger.error("获取消息失败: %s", exc)
            return None

    def ack_message(self, delivery_tag: int) -> bool:
        """确认消息。"""
        try:
            if self.channel and not self.channel.is_closed:
                self.channel.basic_ack(delivery_tag=delivery_tag)
                return True
            return False
        except Exception as exc:
            logger.error("确认消息失败: %s", exc)
            return False

    def nack_message(self, delivery_tag: int, requeue: bool = True) -> bool:
        """拒绝消息。"""
        try:
            if self.channel and not self.channel.is_closed:
                self.channel.basic_nack(delivery_tag=delivery_tag, requeue=requeue)
                return True
            return False
        except Exception as exc:
            logger.error("拒绝消息失败: %s", exc)
            return False

    def send_message(self, queue_name: str, message: dict) -> bool:
        """发送业务消息到队列。"""
        if not self._ensure_connection():
            logger.error("无法连接到 RabbitMQ")
            return False
        if not self.channel:
            logger.error("RabbitMQ 通道未创建")
            return False

        try:
            self._declare_queue(queue_name)
            self.channel.basic_publish(
                exchange="",
                routing_key=queue_name,
                body=json.dumps(message, ensure_ascii=False),
                properties=pika.BasicProperties(delivery_mode=2),
            )
            return True
        except Exception as exc:
            logger.error("发送消息失败: %s", exc)
            return False

    def send_messages_batch(self, queue_names: List[str], message: dict) -> int:
        """批量发送同一条业务消息到多个队列。"""
        success_count = 0
        for queue_name in queue_names:
            if self.send_message(queue_name, message):
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
        if not self._ensure_connection() or not self.channel:
            return False

        try:
            self._declare_queue(queue_name)
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
            published = self.channel.basic_publish(
                exchange="",
                routing_key=queue_name,
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
                return False
            self._published_controls.add(identity)
            return True
        except Exception as exc:
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
        if not self._ensure_connection():
            logger.error("无法连接到 RabbitMQ")
            return 0
        if not self.channel:
            logger.error("RabbitMQ 通道未创建")
            return 0

        processed_count = 0
        try:
            self._declare_queue(queue_name)
            is_reference = queue_name in self._reference_inputs
            while True:
                batch_messages = []
                delivery_tags: list[int] = []
                stream_ended = False

                for index in range(batch_size):
                    delivery = self._next_delivery(
                        queue_name,
                        wait_for_data=is_reference and index == 0,
                    )
                    if delivery is None:
                        stream_ended = bool(
                            is_reference
                            and self._reference_inputs[queue_name].completed
                        )
                        break
                    method_frame, _properties, body = delivery
                    try:
                        body_str = body.decode("utf-8")
                        props_dict = {
                            "delivery_tag": method_frame.delivery_tag,
                            "exchange": method_frame.exchange,
                            "routing_key": method_frame.routing_key,
                            "redelivered": method_frame.redelivered,
                        }
                        batch_messages.append((body_str, props_dict))
                        delivery_tags.append(method_frame.delivery_tag)
                    except Exception as exc:
                        logger.error("解码消息失败: %s", exc)

                if batch_messages:
                    try:
                        success = callback(batch_messages)
                        if success:
                            for delivery_tag in delivery_tags:
                                self.channel.basic_ack(delivery_tag=delivery_tag)
                            processed_count += len(batch_messages)
                        else:
                            for delivery_tag in delivery_tags:
                                self.channel.basic_nack(
                                    delivery_tag=delivery_tag,
                                    requeue=True,
                                )
                    except Exception as exc:
                        logger.error("批量处理消息时发生错误: %s", exc)
                        for delivery_tag in delivery_tags:
                            self.channel.basic_nack(
                                delivery_tag=delivery_tag,
                                requeue=True,
                            )

                if stream_ended or (not is_reference and not batch_messages):
                    break
            return processed_count
        except _CancellationSignal as signal:
            raise signal.error
        except ReferenceStreamAborted:
            raise
        except AMQPChannelError as exc:
            logger.error("消费消息失败: %s", exc)
            return processed_count
        except Exception as exc:
            logger.error("消费消息异常: %s", exc)
            return processed_count

    def read_messages(
        self,
        queue_name: str,
        batch_size: int = 100,
    ) -> List[Dict[str, Any]]:
        """批量读取业务消息（不自动确认），控制帧由 SDK 自动确认。"""
        if not self._ensure_connection():
            logger.error("无法连接到 RabbitMQ")
            return []
        if not self.channel:
            logger.error("RabbitMQ 通道未创建")
            return []

        messages = []
        try:
            self._declare_queue(queue_name)
            is_reference = queue_name in self._reference_inputs
            while len(messages) < batch_size:
                delivery = self._next_delivery(
                    queue_name,
                    wait_for_data=is_reference and not messages,
                )
                if delivery is None:
                    break
                method_frame, _properties, body = delivery
                try:
                    messages.append(
                        {
                            "body": json.loads(body.decode("utf-8")),
                            "delivery_tag": method_frame.delivery_tag,
                        }
                    )
                except json.JSONDecodeError as exc:
                    logger.error("消息JSON解析失败: %s，跳过该消息", exc)
                    self.channel.basic_ack(delivery_tag=method_frame.delivery_tag)
            return messages
        except _CancellationSignal as signal:
            raise signal.error
        except ReferenceStreamAborted:
            raise
        except Exception as exc:
            logger.error("读取消息失败: %s", exc)
            return []

    def ack_all_message(self, delivery_tags: List[int]) -> bool:
        """批量确认消息。"""
        if not self.channel or self.channel.is_closed:
            return False
        try:
            for tag in delivery_tags:
                self.channel.basic_ack(delivery_tag=tag, multiple=False)
            return True
        except Exception as exc:
            logger.error("确认消息失败: %s", exc)
            return False

    def publish_messages(
        self,
        queue_name: str,
        messages: List[Dict[str, Any]],
    ) -> bool:
        """批量发布业务消息到同一个队列。"""
        if not self._ensure_connection():
            logger.error("无法连接到 RabbitMQ")
            return False
        if not self.channel:
            logger.error("RabbitMQ 通道未创建")
            return False

        try:
            self._declare_queue(queue_name)
            for message in messages:
                self.channel.basic_publish(
                    exchange="",
                    routing_key=queue_name,
                    body=json.dumps(message, ensure_ascii=False),
                    properties=pika.BasicProperties(delivery_mode=2),
                )
            return True
        except Exception as exc:
            logger.error("批量发布消息失败: %s", exc)
            return False

    def process_data_events(self) -> None:
        """处理连接事件（心跳等），需要在长时间操作期间定期调用。"""
        try:
            if self.connection and not self.connection.is_closed:
                self.connection.process_data_events()
        except Exception as exc:
            logger.warning("处理连接事件时发生错误: %s", exc)
