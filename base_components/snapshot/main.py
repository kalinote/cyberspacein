from __future__ import annotations

import json
import logging
from typing import TYPE_CHECKING, Callable

from dotenv import load_dotenv

load_dotenv()

from csi_base_component_sdk import ComponentContext, ComponentFailure
from web_snapshot import build_service
from web_snapshot.processor import QueueMessageItem, process_message_batch

if TYPE_CHECKING:
    from csi_base_component_sdk import RabbitMQClient

logger = logging.getLogger("snapshot")


def create_heartbeat_callback(
    rabbitmq: RabbitMQClient | None,
) -> Callable[[], None] | None:
    if rabbitmq is None:
        return None

    def heartbeat_callback() -> None:
        rabbitmq.process_data_events()

    return heartbeat_callback


def _normalize_queue_names(value: object) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str) and value:
        return [value]
    if isinstance(value, list):
        return [q for q in value if isinstance(q, str) and q]
    return []


def _resolve_output_queues(component: ComponentContext) -> list[str]:
    outputs = component.outputs.get("data_out")
    if not outputs or outputs.get("type") != "reference":
        raise ComponentFailure("输出数据类型错误")
    output_queue_names = _normalize_queue_names(outputs.get("value"))
    if not output_queue_names:
        raise ComponentFailure("未找到输出队列配置")
    return output_queue_names


def _coerce_int_config(value: object, name: str, *, default: int, minimum: int) -> int:
    if value is None:
        return default
    try:
        parsed = int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"config.{name} 必须是整数，当前值: {value!r}") from exc
    if parsed < minimum:
        raise ValueError(f"config.{name} 必须 >= {minimum}，当前值: {parsed}")
    return parsed


def _publish_to_data_out(
    component: ComponentContext,
    output_queue_names: list[str],
    data: dict,
) -> bool:
    if component.rabbitmq is None:
        raise ComponentFailure("RabbitMQ 未初始化")
    success_count = component.rabbitmq.send_messages_batch(output_queue_names, data)
    if success_count == len(output_queue_names):
        return True
    logger.error(
        f"发送到输出队列失败，成功: {success_count}/{len(output_queue_names)}"
    )
    return False


def _process_queue_batch(
    component: ComponentContext,
    input_queue: str,
    output_queue_names: list[str],
    service,
    url_field: str,
    batch_size: int,
    heartbeat_callback: Callable[[], None] | None,
) -> tuple[int, int]:
    processed_count = 0
    failed_count = 0

    while True:
        messages = component.rabbitmq.read_messages(input_queue, batch_size)
        if not messages:
            break

        logger.info(f"本批读取 {len(messages)} 条消息，开始批量抓取")
        batch_items: list[QueueMessageItem] = []
        invalid_tags: list[int] = []

        for message in messages:
            try:
                body = message["body"]
                if isinstance(body, str):
                    data = json.loads(body)
                elif isinstance(body, dict):
                    data = body
                else:
                    raise TypeError(f"不支持的消息类型: {type(body)}")
                if not isinstance(data, dict):
                    raise TypeError("消息体必须是 JSON 对象")
                batch_items.append(
                    QueueMessageItem(
                        data=data,
                        delivery_tag=message["delivery_tag"],
                    )
                )
            except (json.JSONDecodeError, TypeError) as exc:
                logger.error(f"消息解析失败: {exc}")
                invalid_tags.append(message["delivery_tag"])

        if invalid_tags:
            component.rabbitmq.ack_all_message(invalid_tags)
            failed_count += len(invalid_tags)

        if not batch_items:
            continue

        try:
            enriched_list = process_message_batch(
                batch_items,
                service,
                url_field,
                heartbeat_callback=heartbeat_callback,
            )
        except Exception as exc:
            logger.error(f"批量抓取失败: {exc}")
            for item in batch_items:
                component.rabbitmq.nack_message(item.delivery_tag, requeue=True)
            failed_count += len(batch_items)
            continue

        ack_tags: list[int] = []
        for item, result in zip(batch_items, enriched_list):
            if _publish_to_data_out(component, output_queue_names, result):
                ack_tags.append(item.delivery_tag)
                processed_count += 1
            else:
                component.rabbitmq.nack_message(item.delivery_tag, requeue=True)
                failed_count += 1

        if ack_tags:
            component.rabbitmq.ack_all_message(ack_tags)
            if processed_count % 10 == 0:
                logger.info(f"已累计处理 {processed_count} 条消息")

    return processed_count, failed_count


def run(component: ComponentContext) -> dict:
    if True:
        max_concurrency = _coerce_int_config(
            component.get_config("max_concurrency", 4),
            "max_concurrency",
            default=4,
            minimum=1,
        )
        service = build_service(
            headed=True,
            max_concurrency=max_concurrency,
            max_retries=_coerce_int_config(
                component.get_config("max_retries", 3),
                "max_retries",
                default=3,
                minimum=0,
            ),
        )
        url_field = component.get_config("url_field", "url")
        batch_size = _coerce_int_config(
            component.get_config("batch_size", max_concurrency),
            "batch_size",
            default=max_concurrency,
            minimum=1,
        )
        input_queues = _normalize_queue_names(
            component.inputs.get("data_in", {}).get("value")
        )
        if not input_queues:
            raise ComponentFailure("未配置 data_in 输入队列")

        output_queue_names = _resolve_output_queues(component)
        heartbeat_callback = create_heartbeat_callback(component.rabbitmq)

        processed_count = 0
        failed_count = 0

        try:
            for input_queue in input_queues:
                logger.info(
                    f"开始处理队列: {input_queue}（批量大小: {batch_size}）"
                )
                batch_processed, batch_failed = _process_queue_batch(
                    component,
                    input_queue,
                    output_queue_names,
                    service,
                    url_field,
                    batch_size,
                    heartbeat_callback,
                )
                processed_count += batch_processed
                failed_count += batch_failed

            logger.info(
                f"队列处理完成，成功: {processed_count}，失败: {failed_count}"
            )

            if processed_count == 0:
                raise ComponentFailure(
                    f"处理失败: 成功 0 条，失败 {failed_count} 条"
                )

            return {
                "processed": processed_count,
                "failed": failed_count,
                "output_queues": output_queue_names,
                "batch_size": batch_size,
            }

        except ComponentFailure:
            raise
        except Exception as exc:
            logger.error(f"处理过程发生错误: {exc}")
            raise ComponentFailure(f"处理过程发生错误: {str(exc)}") from exc
