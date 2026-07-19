import logging
import os
from collections import Counter
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from dotenv import load_dotenv
from elasticsearch import Elasticsearch
from elasticsearch.exceptions import ApiError

load_dotenv()

logger = logging.getLogger(__name__)


RETRYABLE_STATUSES = {408, 429, 500, 502, 503, 504}
RETRYABLE_ERROR_TYPES = {
    "cluster_block_exception",
    "es_rejected_execution_exception",
    "master_not_discovered_exception",
    "node_not_connected_exception",
    "receive_timeout_transport_exception",
    "unavailable_shards_exception",
}


@dataclass(frozen=True)
class BulkFailure:
    """一条 Bulk item 的失败信息，不携带可能很大的原始文档。"""

    position: int
    doc_id: Optional[str]
    status: int
    error_type: str
    reason: str
    retryable: bool


@dataclass
class BulkStoreResult:
    total: int
    success_count: int = 0
    failures: List[BulkFailure] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.failures

    @property
    def failed_count(self) -> int:
        return len(self.failures)


def _error_details(error: Any) -> tuple[str, str]:
    """从 Elasticsearch error 对象中提取稳定、紧凑的类型和原因。"""
    if isinstance(error, dict):
        error_type = str(error.get("type") or "unknown_error")
        reason = str(error.get("reason") or error_type)
        caused_by = error.get("caused_by")
        if isinstance(caused_by, dict):
            cause_type = caused_by.get("type")
            cause_reason = caused_by.get("reason")
            if cause_type or cause_reason:
                reason = f"{reason}; caused_by={cause_type}: {cause_reason}"
        return error_type, reason
    if error:
        return "unknown_error", str(error)
    return "unknown_error", "Elasticsearch 未返回错误原因"


class ElasticsearchClient:
    """Elasticsearch 客户端封装类。"""

    def __init__(self):
        self.host = os.getenv("ELASTICSEARCH_HOST", "localhost")
        self.port = int(os.getenv("ELASTICSEARCH_PORT", "9200"))
        self.username = os.getenv("ELASTICSEARCH_USERNAME", "")
        self.password = os.getenv("ELASTICSEARCH_PASSWORD", "")
        self.use_ssl = os.getenv("ELASTICSEARCH_USE_SSL", "false").lower() == "true"
        self.verify_certs = os.getenv("ELASTICSEARCH_VERIFY_CERTS", "true").lower() == "true"
        self.ca_certs = os.getenv("ELASTICSEARCH_CA_CERTS", "")
        self.request_timeout = float(os.getenv("ELASTICSEARCH_REQUEST_TIMEOUT", "120"))
        self.error_sample_limit = max(
            0, int(os.getenv("ELASTICSEARCH_BULK_ERROR_SAMPLES", "5"))
        )

        self.client = self._create_client()

    def _create_client(self) -> Elasticsearch:
        scheme = "https" if self.use_ssl else "http"
        configured_url = os.getenv("ELASTICSEARCH_URL")
        client_config: Dict[str, Any] = {
            "hosts": [configured_url or f"{scheme}://{self.host}:{self.port}"],
            "verify_certs": self.verify_certs,
            "request_timeout": self.request_timeout,
        }

        if self.username and self.password:
            client_config["basic_auth"] = (self.username, self.password)
        if self.ca_certs:
            client_config["ca_certs"] = self.ca_certs

        return Elasticsearch(**client_config)

    def test_connection(self) -> bool:
        try:
            connected = self.client.ping()
            if not connected:
                logger.error("Elasticsearch ping 返回 false")
            return connected
        except Exception:
            logger.exception("Elasticsearch 连接测试失败")
            return False

    def create_index(
        self, index_name: str, mappings: Optional[Dict[str, Any]] = None
    ) -> bool:
        try:
            if not self.client.indices.exists(index=index_name):
                body = {"mappings": mappings} if mappings else {}
                self.client.indices.create(index=index_name, body=body)
                logger.info("索引 %s 创建成功", index_name)
            else:
                logger.info("索引 %s 已存在", index_name)
            return True
        except ApiError as exc:
            logger.error(
                "创建索引失败: index=%s status=%s error=%s",
                index_name,
                getattr(exc, "status_code", None),
                getattr(exc, "message", str(exc)),
            )
            return False

    def store_data(
        self,
        index_name: str,
        document: Dict[str, Any],
        doc_id: Optional[str] = None,
    ) -> bool:
        try:
            response = self.client.index(
                index=index_name, id=doc_id, document=document
            )
            if response.get("result") in {"created", "updated"}:
                return True
            logger.warning("数据存储返回非成功结果: %s", response)
            return False
        except ApiError as exc:
            logger.error(
                "存储数据失败: index=%s id=%s status=%s error=%s",
                index_name,
                doc_id,
                getattr(exc, "status_code", None),
                getattr(exc, "message", str(exc)),
            )
            return False

    def _log_bulk_failures(
        self, index_name: str, result: BulkStoreResult
    ) -> None:
        summary = Counter(
            (failure.status, failure.error_type, failure.retryable)
            for failure in result.failures
        )
        summary_text = ", ".join(
            f"status={status} type={error_type} retryable={retryable}: {count}条"
            for (status, error_type, retryable), count in summary.most_common()
        )
        logger.warning(
            "批量存储部分失败: index=%s total=%d success=%d failed=%d; %s",
            index_name,
            result.total,
            result.success_count,
            result.failed_count,
            summary_text,
        )

        for failure in result.failures[: self.error_sample_limit]:
            logger.error(
                "Bulk item 失败: index=%s position=%d id=%s status=%d "
                "type=%s retryable=%s reason=%s",
                index_name,
                failure.position,
                failure.doc_id,
                failure.status,
                failure.error_type,
                failure.retryable,
                failure.reason,
            )
        omitted = result.failed_count - self.error_sample_limit
        if omitted > 0:
            logger.warning(
                "其余 %d 条 Bulk 错误已省略；可通过 "
                "ELASTICSEARCH_BULK_ERROR_SAMPLES 调整样本数",
                omitted,
            )

    def bulk_store(
        self,
        index_name: str,
        documents: List[Dict[str, Any]],
        id_field: str = "uuid",
    ) -> BulkStoreResult:
        """批量写入并返回逐条结果，便于调用方精确 ack/nack。"""
        from elasticsearch.helpers import streaming_bulk

        result = BulkStoreResult(total=len(documents))
        if not documents:
            return result

        actions = []
        for document in documents:
            action: Dict[str, Any] = {
                "_index": index_name,
                "_source": document,
            }
            if id_field and document.get(id_field) is not None:
                action["_id"] = str(document[id_field])
            actions.append(action)

        try:
            outcomes = streaming_bulk(
                self.client,
                actions,
                raise_on_error=False,
                raise_on_exception=False,
                yield_ok=True,
            )
            outcome_count = 0
            for position, (ok, info) in enumerate(outcomes):
                outcome_count += 1
                _operation, detail = next(iter(info.items()))
                if ok:
                    result.success_count += 1
                    continue

                status = int(detail.get("status") or 0)
                error_type, reason = _error_details(detail.get("error"))
                result.failures.append(
                    BulkFailure(
                        position=position,
                        doc_id=str(detail.get("_id")) if detail.get("_id") else None,
                        status=status,
                        error_type=error_type,
                        reason=reason,
                        retryable=(
                            status in RETRYABLE_STATUSES
                            or error_type in RETRYABLE_ERROR_TYPES
                        ),
                    )
                )

            # 防御 helper/连接异常导致生成器静默少返回结果；未知结果绝不能 ack。
            for position in range(outcome_count, len(documents)):
                document = documents[position]
                result.failures.append(
                    BulkFailure(
                        position=position,
                        doc_id=(
                            str(document.get(id_field))
                            if id_field and document.get(id_field) is not None
                            else None
                        ),
                        status=0,
                        error_type="missing_bulk_response",
                        reason="Elasticsearch Bulk 未返回该文档的处理结果",
                        retryable=True,
                    )
                )

            if result.failures:
                self._log_bulk_failures(index_name, result)
            logger.info(
                "批量存储完成: index=%s total=%d success=%d failed=%d",
                index_name,
                result.total,
                result.success_count,
                result.failed_count,
            )
            return result
        except Exception as exc:
            logger.exception(
                "Bulk 请求异常: index=%s documents=%d", index_name, len(documents)
            )
            reason = str(exc) or exc.__class__.__name__
            # 连接中断后无法可靠判断已发送 item 是否落库，按 uuid 重试是幂等的。
            result.success_count = 0
            result.failures = [
                BulkFailure(
                    position=position,
                    doc_id=(
                        str(document.get(id_field))
                        if id_field and document.get(id_field) is not None
                        else None
                    ),
                    status=0,
                    error_type=exc.__class__.__name__,
                    reason=reason,
                    retryable=True,
                )
                for position, document in enumerate(documents)
            ]
            return result
