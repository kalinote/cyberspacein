import json
import logging
from dataclasses import dataclass
from typing import Any, Dict, List, Tuple

from dotenv import load_dotenv

load_dotenv()

from csi_base_component_sdk import ComponentContext, ComponentFailure
from es_client import ElasticsearchClient
from validator import validate_and_transform

logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] [%(levelname)s] [%(name)s] %(message)s",
    datefmt="%H:%M:%S",
)

logger = logging.getLogger(__name__)

DATA_INDEX_MAP = {
    "forum": "forum",
    "article": "article",
}


@dataclass
class BatchStats:
    read: int = 0
    stored: int = 0
    rejected: int = 0
    retryable: int = 0

    def add(self, other: "BatchStats") -> None:
        self.read += other.read
        self.stored += other.stored
        self.rejected += other.rejected
        self.retryable += other.retryable


def _parse_batch_size(value: Any) -> int:
    try:
        batch_size = int(value)
        if batch_size < 1:
            raise ValueError
        return batch_size
    except (TypeError, ValueError):
        logger.warning("batch_size=%r 非法，使用默认值 100", value)
        return 100


def _decode_message_body(body: Any) -> Dict[str, Any]:
    if isinstance(body, dict):
        return body
    if isinstance(body, (str, bytes, bytearray)):
        decoded = json.loads(body)
        if isinstance(decoded, dict):
            return decoded
        raise TypeError("消息体必须是 JSON 对象")
    raise TypeError(f"不支持的消息体类型: {type(body).__name__}")


def _reject_without_requeue(component: ComponentContext, delivery_tag: int) -> None:
    """拒绝永久错误；RabbitMQ 配置了 DLX 时消息会进入死信队列。"""
    if not component.rabbitmq.nack_message(delivery_tag, requeue=False):
        logger.error("拒绝永久错误消息失败: delivery_tag=%s", delivery_tag)


def _process_batch(
    component: ComponentContext,
    es_client: ElasticsearchClient,
    messages: List[Dict[str, Any]],
) -> BatchStats:
    stats = BatchStats(read=len(messages))
    batch_data: Dict[str, List[Tuple[Dict[str, Any], int]]] = {}

    for message in messages:
        delivery_tag = message["delivery_tag"]
        try:
            data = _decode_message_body(message["body"])
            validated_data = validate_and_transform(data)
        except (json.JSONDecodeError, TypeError) as exc:
            logger.error(
                "消息格式错误，拒绝且不重入队列: delivery_tag=%s error=%s",
                delivery_tag,
                exc,
            )
            _reject_without_requeue(component, delivery_tag)
            stats.rejected += 1
            continue

        if not validated_data:
            logger.error(
                "消息校验失败，拒绝且不重入队列: delivery_tag=%s",
                delivery_tag,
            )
            _reject_without_requeue(component, delivery_tag)
            stats.rejected += 1
            continue

        entity_type = validated_data["entity_type"]
        index_name = DATA_INDEX_MAP.get(entity_type)
        if not index_name:
            logger.error(
                "未知实体类型，拒绝且不重入队列: delivery_tag=%s "
                "entity_type=%s uuid=%s",
                delivery_tag,
                entity_type,
                validated_data.get("uuid"),
            )
            _reject_without_requeue(component, delivery_tag)
            stats.rejected += 1
            continue

        batch_data.setdefault(index_name, []).append((validated_data, delivery_tag))

    for index_name, entries in batch_data.items():
        documents = [document for document, _ in entries]
        result = es_client.bulk_store(index_name, documents, id_field="uuid")
        failures_by_position = {
            failure.position: failure for failure in result.failures
        }

        for position, (document, delivery_tag) in enumerate(entries):
            failure = failures_by_position.get(position)
            if failure is None:
                if component.rabbitmq.ack_message(delivery_tag):
                    stats.stored += 1
                else:
                    # 写入已成功但 ack 失败时保留为可重试；按 uuid 写入是幂等的。
                    logger.error(
                        "Elasticsearch 写入成功但 RabbitMQ ack 失败: "
                        "delivery_tag=%s index=%s uuid=%s",
                        delivery_tag,
                        index_name,
                        document.get("uuid"),
                    )
                    stats.retryable += 1
                continue

            if failure.retryable:
                component.rabbitmq.nack_message(delivery_tag, requeue=True)
                stats.retryable += 1
            else:
                _reject_without_requeue(component, delivery_tag)
                stats.rejected += 1

    return stats


def run(component: ComponentContext) -> dict:
    """从 RabbitMQ 消费实体，校验后批量写入 Elasticsearch。"""
    if True:
        queue_names = component.inputs.get("data_in", {}).get("value", [])
        if isinstance(queue_names, str):
            queue_names = [queue_names]
        if not queue_names:
            raise ComponentFailure("未找到数据输入队列名称")

        es_client = ElasticsearchClient()
        if not es_client.test_connection():
            raise ComponentFailure("无法连接到 Elasticsearch，请检查地址、认证和集群状态")

        batch_size = _parse_batch_size(component.config.get("batch_size", 100))
        total = BatchStats()
        stopped_for_retry = False

        try:
            for queue_name in queue_names:
                logger.info("开始消费队列: %s (批量大小: %d)", queue_name, batch_size)
                while True:
                    messages = component.rabbitmq.read_messages(queue_name, batch_size)
                    if not messages:
                        break

                    batch_stats = _process_batch(component, es_client, messages)
                    total.add(batch_stats)
                    logger.info(
                        "批次完成: read=%d stored=%d rejected=%d retryable=%d",
                        batch_stats.read,
                        batch_stats.stored,
                        batch_stats.rejected,
                        batch_stats.retryable,
                    )

                    if batch_stats.retryable:
                        # requeue 后立即继续会形成毫秒级无限重试。停止本轮组件，
                        # 由任务调度稍后重试，给 ES/网络恢复时间。
                        stopped_for_retry = True
                        logger.error(
                            "发现 %d 条可重试错误，已重新入队并停止本轮消费，"
                            "避免形成无限重试热循环",
                            batch_stats.retryable,
                        )
                        break

                logger.info("队列 %s 本轮消费结束", queue_name)
                if stopped_for_retry:
                    break

            result = {
                "total_read": total.read,
                "total_stored": total.stored,
                "total_rejected": total.rejected,
                "total_retryable": total.retryable,
            }
            if total.rejected or total.retryable:
                raise ComponentFailure(
                    "实体存储未完全成功: "
                    f"读取 {total.read} 条，成功 {total.stored} 条，"
                    f"永久失败 {total.rejected} 条，可重试 {total.retryable} 条；"
                    "具体原因见 Bulk item 失败日志"
                )

            return result
        except ComponentFailure:
            raise
        except Exception as exc:
            logger.exception("处理过程中发生未捕获异常")
            raise ComponentFailure(f"处理失败: {exc}") from exc
