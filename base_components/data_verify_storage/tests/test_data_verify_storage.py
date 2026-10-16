"""验证贴文字段保留、混合实体路由及消息确认行为。"""

import importlib
import json
import sys
import unittest
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, call, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

main = importlib.import_module("main")
es_client = importlib.import_module("es_client")
BulkFailure = es_client.BulkFailure
BulkStoreResult = es_client.BulkStoreResult
ElasticsearchClient = es_client.ElasticsearchClient
validator = importlib.import_module("validator")
validate_and_transform = validator.validate_and_transform


class DateParsingTests(unittest.TestCase):
    """验证系统标准时间与既有采集器时间格式的兼容性。"""

    def test_iso8601_preserves_timezone_and_microseconds_without_warning(self):
        """标准时区、微秒与 UTC 标识正常解析，不产生误报警。"""
        cases = [
            ("2026-10-16T07:44:38+00:00", "2026-10-16T07:44:38+00:00"),
            ("2026-10-16T07:46:04.935303+00:00", "2026-10-16T07:46:04.935303+00:00"),
            ("2026-10-16T15:44:38+08:00", "2026-10-16T15:44:38+08:00"),
            ("2026-10-16T03:44:38.123456-04:00", "2026-10-16T03:44:38.123456-04:00"),
            ("2026-10-16T07:44:38Z", "2026-10-16T07:44:38+00:00"),
            ("2026-10-16T07:46:04.935303Z", "2026-10-16T07:46:04.935303+00:00"),
            ("2026-10-16T07:44:38+0000", "2026-10-16T07:44:38+00:00"),
        ]
        with self.assertNoLogs(validator.logger, level="WARNING"):
            for value, expected in cases:
                with self.subTest(value=value):
                    self.assertEqual(validator.parse_date(value), expected)

    def test_existing_crawler_date_formats_remain_supported(self):
        """既有采集器的空格、斜杠、短日期及紧凑时间格式保持兼容。"""
        cases = [
            ("2026-10-16 15:46:09", "2026-10-16T15:46:09"),
            ("2026-10-16 15:46:09.123456", "2026-10-16T15:46:09.123456"),
            ("2026-10-16T15:46:09", "2026-10-16T15:46:09"),
            ("2026-10-16T15:46:09.123456", "2026-10-16T15:46:09.123456"),
            ("2026-10-16 15:46", "2026-10-16T15:46:00"),
            ("2026-10-16", "2026-10-16T00:00:00"),
            ("2026/10/16 15:46:09", "2026-10-16T15:46:09"),
            ("2026/10/16 15:46", "2026-10-16T15:46:00"),
            ("2026/10/16", "2026-10-16T00:00:00"),
            ("16/10/2026 15:46:09", "2026-10-16T15:46:09"),
            ("16/10/2026 15:46", "2026-10-16T15:46:00"),
            ("16/10/2026", "2026-10-16T00:00:00"),
            ("16-10-2026 15:46:09", "2026-10-16T15:46:09"),
            ("16-10-2026", "2026-10-16T00:00:00"),
            ("20261016 15:46:09", "2026-10-16T15:46:09"),
            ("20261016 15:46", "2026-10-16T15:46:00"),
            ("20261016", "2026-10-16T00:00:00"),
            ("2026.10.16 15:46:09", "2026-10-16T15:46:09"),
            ("2026.10.16", "2026-10-16T00:00:00"),
        ]
        with self.assertNoLogs(validator.logger, level="WARNING"):
            for value, expected in cases:
                with self.subTest(value=value):
                    self.assertEqual(validator.parse_date(value), expected)

    def test_all_entity_types_preserve_date_fields(self):
        """文章、论坛和贴文统一保留时间，不给无时区时间擅自补时区。"""
        dates = {
            "publish_at": "2026-10-16T15:44:38+08:00",
            "crawled_at": "2026-10-16T07:46:04.935303+00:00",
            "last_edit_at": "2026-10-16 15:45:00",
            "highlighted_at": "2026-10-16T07:46:00Z",
        }
        with self.assertNoLogs(validator.logger, level="WARNING"):
            for entity_type in ("article", "forum", "post"):
                with self.subTest(entity_type=entity_type):
                    result = validate_and_transform({
                        "uuid": "date-verification", "entity_type": entity_type,
                        **dates,
                    })
                    self.assertEqual(result["publish_at"], dates["publish_at"])
                    self.assertEqual(result["crawled_at"], dates["crawled_at"])
                    self.assertEqual(result["last_edit_at"], "2026-10-16T15:45:00")
                    self.assertEqual(result["highlighted_at"], "2026-10-16T07:46:00+00:00")

    def test_empty_and_invalid_dates_are_not_coerced(self):
        """空值与非法时间不会被误转换为当前时间。"""
        for value in (None, "", "   ", 42, False):
            with self.subTest(value=value):
                self.assertIsNone(validator.parse_date(value))
        with self.assertLogs(validator.logger, level="WARNING"):
            self.assertIsNone(validator.parse_date("日期无效"))
            self.assertIsNone(validator.parse_date("2026-02-30T07:46:00+00:00"))


class EntityStorageTests(unittest.TestCase):
    """在不连接真实队列和存储的情况下验证实体处理。"""

    def setUp(self):
        """准备通用贴文和可追踪消息确认的客户端。"""
        self.post = {
            "uuid": "post-1",
            "source_id": "source-1",
            "data_version": 1,
            "entity_type": "post",
            "platform": "social-platform",
            "url": "https://example.com/posts/source-1",
            "raw_content": '{"text": "原始内容"}',
            "clean_content": "贴文正文",
            "translation_content": "译文",
            "crawled_at": "2026-10-16T07:30:00Z",
            "publish_at": "2026-10-16 15:00:00",
            "last_edit_at": None,
            "post_type": "reply",
            "parent_id": "parent-1",
            "mentions": ["user-1"],
            "metrics": {"likes": 3, "comments": 2, "shares": -1},
            "geo_location": {"lat": 31.2, "lon": 121.5},
            "ip_location": "上海",
            "files_urls": ["https://storage.example/media/image.jpg"],
            "media_resources": [{
                "source_url": "https://example.com/image.jpg",
                "stored_url": "https://storage.example/media/image.jpg",
                "status": "stored",
            }],
            "media_summary": {"status": "complete", "total": 1, "stored": 1},
            "unrelated_field": "应被过滤",
        }
        self.component = SimpleNamespace(
            rabbitmq=MagicMock(),
            mark_successful_result=MagicMock(),
            config={},
            inputs={"data_in": {"value": ["input-queue"]}},
        )
        self.component.rabbitmq.ack_message.return_value = True
        self.component.rabbitmq.nack_message.return_value = True
        self.es_client = MagicMock(spec=ElasticsearchClient)
        self.es_client.bulk_store.return_value = BulkStoreResult(
            total=1, success_count=1
        )

    def test_post_preserves_content_relationships_and_media(self):
        """保留贴文结构及媒体结果，沿用日期和译文字段归一化。"""
        original = deepcopy(self.post)

        result = validate_and_transform(self.post)

        self.assertIsNotNone(result)
        for key in (
            "source_id", "platform", "raw_content", "clean_content", "post_type",
            "parent_id", "mentions", "metrics", "geo_location", "ip_location",
            "files_urls", "media_resources", "media_summary",
        ):
            self.assertEqual(result[key], self.post[key], key)
        self.assertEqual(result["entity_type"], "post")
        self.assertEqual(result["translate_content"], "译文")
        self.assertEqual(result["crawled_at"], "2026-10-16T07:30:00+00:00")
        self.assertEqual(result["publish_at"], "2026-10-16T15:00:00")
        self.assertIn("update_at", result)
        self.assertNotIn("unrelated_field", result)
        self.assertEqual(self.post, original)

    def test_post_preserves_valid_vector(self):
        """贴文复用已有向量维度与数值校验。"""
        with patch.dict("os.environ", {"ELASTICSEARCH_VECTOR_DIMS": "3"}):
            result = validate_and_transform({
                **self.post, "clean_content_vector": [0.1, 0.2, 0.3],
                "vector_status": True,
            })

        self.assertEqual(result["clean_content_vector"], [0.1, 0.2, 0.3])
        self.assertTrue(result["vector_status"])

    def test_post_invalid_vector_does_not_reject_content(self):
        """错误向量不阻断贴文入库，并保留重新向量化标记。"""
        with patch.dict("os.environ", {"ELASTICSEARCH_VECTOR_DIMS": "3"}):
            for vector in ([0.1], [0.1, True, 0.3], [0.1, float("nan"), 0.3]):
                with self.subTest(vector=vector):
                    result = validate_and_transform({
                        **self.post, "clean_content_vector": vector,
                        "vector_status": True,
                    })
                    self.assertNotIn("clean_content_vector", result)
                    self.assertFalse(result["vector_status"])
                    self.assertEqual(result["clean_content"], "贴文正文")

    def test_existing_entity_schemas_are_unchanged(self):
        """文章和论坛继续使用原有字段集合。"""
        for entity_type in ("article", "forum"):
            with self.subTest(entity_type=entity_type):
                result = validate_and_transform({
                    **self.post, "entity_type": entity_type, "topic_id": "topic-1",
                })
                self.assertEqual(result["entity_type"], entity_type)
                self.assertEqual(result["clean_content"], "贴文正文")
                self.assertNotIn("post_type", result)
                self.assertNotIn("metrics", result)
                self.assertEqual("topic_id" in result, entity_type == "forum")

    def test_mixed_batch_routes_each_type_and_confirms_success(self):
        """混合批次分别进入对应索引，成功写入后才确认消息。"""
        article = {**self.post, "uuid": "article-1", "entity_type": "article"}
        forum = {**self.post, "uuid": "forum-1", "entity_type": "forum"}
        messages = [
            {"delivery_tag": 1, "body": json.dumps(self.post)},
            {"delivery_tag": 2, "body": json.dumps(article).encode()},
            {"delivery_tag": 3, "body": forum},
        ]

        stats = main._process_batch(self.component, self.es_client, messages)

        self.assertEqual((stats.read, stats.stored, stats.rejected, stats.retryable),
                         (3, 3, 0, 0))
        calls = self.es_client.bulk_store.call_args_list
        self.assertEqual([args.args[0] for args in calls], ["post", "article", "forum"])
        self.assertEqual(calls[0].args[1][0]["media_resources"], self.post["media_resources"])
        self.assertTrue(all(args.kwargs["id_field"] == "uuid" for args in calls))
        self.assertEqual(self.component.rabbitmq.ack_message.call_args_list,
                         [call(1), call(2), call(3)])
        self.component.rabbitmq.nack_message.assert_not_called()
        self.assertEqual(self.component.mark_successful_result.call_count, 3)

    def test_post_bulk_failures_preserve_retry_policy(self):
        """贴文逐条沿用成功确认、临时错误重试及永久错误拒绝策略。"""
        self.es_client.bulk_store.return_value = BulkStoreResult(
            total=3,
            success_count=1,
            failures=[
                BulkFailure(1, "post-2", 429, "es_rejected_execution_exception",
                            "请求限流", True),
                BulkFailure(2, "post-3", 400, "mapper_parsing_exception",
                            "字段映射错误", False),
            ],
        )
        messages = [
            {"delivery_tag": i, "body": {**self.post, "uuid": f"post-{i}"}}
            for i in (1, 2, 3)
        ]

        stats = main._process_batch(self.component, self.es_client, messages)

        self.assertEqual((stats.stored, stats.rejected, stats.retryable), (1, 1, 1))
        self.component.rabbitmq.ack_message.assert_called_once_with(1)
        self.assertEqual(self.component.rabbitmq.nack_message.call_args_list,
                         [call(2, requeue=True), call(3, requeue=False)])

    def test_invalid_entities_are_still_rejected(self):
        """新增贴文支持不放开未知实体或缺失标识的数据。"""
        messages = [
            {"delivery_tag": 1, "body": {**self.post, "entity_type": "unknown"}},
            {"delivery_tag": 2, "body": {**self.post, "uuid": ""}},
        ]

        stats = main._process_batch(self.component, self.es_client, messages)

        self.assertEqual(stats.rejected, 2)
        self.es_client.bulk_store.assert_not_called()
        self.component.rabbitmq.ack_message.assert_not_called()

    def test_run_reports_post_storage_success(self):
        """完整消费入口将贴文存储成功计入运行结果。"""
        self.component.rabbitmq.read_messages.side_effect = [
            [{"delivery_tag": 1, "body": self.post}], [],
        ]
        self.es_client.test_connection.return_value = True

        with patch.object(main, "ElasticsearchClient", return_value=self.es_client):
            result = main.run(self.component)

        self.assertEqual(result, {
            "total_read": 1, "total_stored": 1,
            "total_rejected": 0, "total_retryable": 0,
        })
        self.component.rabbitmq.ack_message.assert_called_once_with(1)


if __name__ == "__main__":
    unittest.main()
