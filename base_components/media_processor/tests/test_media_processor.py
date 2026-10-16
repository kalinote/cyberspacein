"""使用本地 HTTP 服务和内存对象存储验证媒体处理及 SDK 消息确认规则。"""

import hashlib
import json
import logging
import os
import subprocess
import sys
import threading
import time
import tempfile
import unittest
from collections import Counter
from copy import deepcopy
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from unittest.mock import MagicMock, patch

import boto3
from botocore.exceptions import ClientError
from botocore.stub import ANY, Stubber
from csi_base_component_sdk import (
    ComponentCancelled,
    ComponentContext,
    ComponentFailure,
    ComponentTimedOut,
    ReferenceStreamAborted,
    ReferenceStreamTransportError,
)
from csi_base_component_sdk.context import StructuredLogger

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import main
from processor import MediaProcessor, parse_size


IMAGE = b"\x89PNG\r\n\x1a\n" + b"a" * 32
VIDEO = b"\x00\x00\x00\x18ftypmp42" + b"b" * 64


class MediaHandler(BaseHTTPRequestHandler):
    """提供成功、重试、超限、播放清单和错误响应的本地媒体服务。"""

    counts = Counter()
    headers_seen = {}

    def do_GET(self):
        """按测试路径返回媒体数据或指定的错误响应。"""
        self.counts[self.path] += 1
        self.headers_seen[self.path] = dict(self.headers)
        if self.path == "/slow":
            time.sleep(0.15)
        if self.path == "/retry" and self.counts[self.path] == 1:
            self.send_response(503)
            self.end_headers()
            return
        if self.path == "/redirect":
            self.send_response(302)
            self.send_header("Location", "/list.m3u8")
            self.end_headers()
            return
        payloads = {
            "/image": (IMAGE, "image/png"),
            "/same": (IMAGE, "image/png"),
            "/video": (VIDEO, "video/mp4"),
            "/stream": (IMAGE * 400, "application/octet-stream"),
            "/list.m3u8": (b"#EXTM3U\nfragment.ts", "application/vnd.apple.mpegurl"),
            "/list.dat": (b"#EXTM3U\nfragment.ts", "application/octet-stream"),
            "/dash": (b'<?xml version="1.0"?><MPD></MPD>', "application/octet-stream"),
            "/html": (b"<!doctype html><html>login</html>", "text/html"),
            "/hidden-html": (b"<html>login</html>", "application/octet-stream"),
            "/empty": (b"", "image/png"),
            "/retry": (IMAGE, "image/png"),
            "/slow": (IMAGE, "image/png"),
        }
        if self.path not in payloads:
            self.send_response(404)
            self.end_headers()
            return
        content, content_type = payloads[self.path]
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        if self.path != "/stream":
            self.send_header("Content-Length", str(len(content)))
        self.end_headers()
        try:
            self.wfile.write(content)
        except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError):
            pass

    def log_message(self, format, *args):
        """使用中文日志标记本地测试请求。"""
        logging.getLogger("媒体测试").debug("本地请求：%s", self.path)


class MemoryStorage:
    """模拟 S3 对象存在性与流式写入，检查实际上传的字节。"""

    def __init__(self):
        """初始化对象表、调用记录及可注入的存储故障。"""
        self.objects = {}
        self.puts = []
        self.lock = threading.Lock()
        self.error_status = None
        self.closed = False

    def head_object(self, Bucket, Key):
        """读取已有对象元数据，缺失时返回与 S3 一致的异常。"""
        if self.error_status:
            raise ClientError(
                {
                    "Error": {"Code": "AccessDenied"},
                    "ResponseMetadata": {"HTTPStatusCode": self.error_status},
                },
                "HeadObject",
            )
        with self.lock:
            value = self.objects.get(Key)
        if value is None:
            raise ClientError(
                {"Error": {"Code": "404"}, "ResponseMetadata": {"HTTPStatusCode": 404}},
                "HeadObject",
            )
        return {"ContentLength": len(value[0]), "ContentType": value[1]}

    def put_object(self, Bucket, Key, Body, ContentLength, ContentType):
        """保存上传流并核对声明的长度与内容哈希。"""
        content = Body.read()
        assert len(content) == ContentLength
        assert Key.endswith(hashlib.sha256(content).hexdigest())
        with self.lock:
            self.objects[Key] = (content, ContentType)
            self.puts.append(Key)
        return {}

    def close(self):
        """标记连接已释放并保留对象供测试检查。"""
        self.closed = True


class MediaProcessorTests(unittest.TestCase):
    """验证下载、存储、失败状态、取消和队列传输行为。"""

    @classmethod
    def setUpClass(cls):
        """启动仅监听回环地址的本地 HTTP 服务。"""
        cls.server = ThreadingHTTPServer(("127.0.0.1", 0), MediaHandler)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        cls.base = f"http://127.0.0.1:{cls.server.server_port}"

    @classmethod
    def tearDownClass(cls):
        """停止服务并关闭监听套接字。"""
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join(timeout=2)

    def setUp(self):
        """隔离存储配置、下载统计和存储客户端。"""
        MediaHandler.counts.clear()
        MediaHandler.headers_seen.clear()
        self.storage = MemoryStorage()
        self.environment = patch.dict(
            os.environ,
            {
                "COS_ENDPOINT": "http://127.0.0.1:9000",
                "COS_ACCESS_KEY": "test",
                "COS_SECRET_KEY": "test",
                "COS_BUCKET": "media",
                "COS_REGION": "us-east-1",
                "COS_BASE_URL": "https://media.example.com",
                "NO_PROXY": "127.0.0.1,localhost",
                "DOWNLOAD_PROXY": "",
            },
        )
        self.environment.start()
        self.addCleanup(self.environment.stop)
        self.client_patch = patch("processor.boto3.client", return_value=self.storage)
        self.client_patch.start()
        self.addCleanup(self.client_patch.stop)
        self.heartbeat = MagicMock()

    def processor(self, **config):
        """创建自动释放资源的处理器并默认关闭重试以加快测试。"""
        config.setdefault("max_retries", 0)
        instance = MediaProcessor(config)
        self.addCleanup(instance.close)
        return instance

    def context(self, inputs, outputs=None, config=None):
        """构造真实 SDK 上下文并注入内存消息客户端。"""
        context = ComponentContext(
            action_id="test",
            node_instance_id="test",
            component_run_id="test",
            component_id="test",
            attempt=1,
            config=config or {"max_retries": 0},
            inputs=inputs,
            outputs=outputs or {},
            logger=StructuredLogger(logging.getLogger("媒体测试")),
        )
        context._rabbitmq = MagicMock()
        context._rabbitmq.ack_message.return_value = True
        return context

    def test_archive_preserves_content_metadata_order_and_deduplicates_urls(self):
        """归档图片和视频，保持业务字段且同一地址只下载一次。"""
        data = {
            "clean_content": "纯文本",
            "raw_content": '{"text":"原始数据"}',
            "url": "https://example.com/post/1",
            "media_resources": [
                {"source_url": self.base + "/image", "role": "content", "width": 100},
                {"source_url": self.base + "/video", "type": "video"},
                {"source_url": self.base + "/image", "role": "poster"},
            ],
        }
        original = deepcopy(data)
        processor = self.processor(download_headers={"X-Media-Test": "ok"})
        result = processor.process(data, self.heartbeat)
        self.assertEqual(data, original)
        self.assertEqual(result["raw_content"], original["raw_content"])
        self.assertEqual(result["clean_content"], original["clean_content"])
        self.assertEqual(
            result["media_summary"],
            {"status": "complete", "total": 3, "stored": 3, "failed": 0, "skipped": 0},
        )
        self.assertEqual(result["media_resources"][2]["role"], "poster")
        self.assertEqual(
            result["media_resources"][0]["sha256"], hashlib.sha256(IMAGE).hexdigest()
        )
        self.assertEqual(len(result["files_urls"]), 2)
        self.assertEqual(MediaHandler.counts["/image"], 1)
        self.assertEqual(MediaHandler.headers_seen["/image"]["X-Media-Test"], "ok")
        self.assertEqual(MediaHandler.headers_seen["/image"]["Referer"], data["url"])
        again = processor.process(result, self.heartbeat)
        self.assertEqual(again["files_urls"], result["files_urls"])
        self.assertEqual(MediaHandler.counts["/image"], 1)
        self.assertEqual(MediaHandler.counts["/video"], 1)

    def test_same_content_uses_one_storage_object(self):
        """不同 URL 的相同内容使用同一哈希对象。"""
        result = self.processor(max_workers=1).process(
            {"files_urls": [self.base + "/image", self.base + "/same"]}, self.heartbeat
        )
        self.assertEqual(len(self.storage.objects), 1)
        self.assertEqual(len(self.storage.puts), 1)
        self.assertEqual(len(result["files_urls"]), 1)

    def test_partial_failure_and_unsupported_stream_keep_sources(self):
        """失败和播放清单不得回填为归档成功。"""
        urls = [
            self.base + path
            for path in (
                "/image",
                "/missing",
                "/html",
                "/list.m3u8",
                "/list.dat",
                "/dash",
                "/hidden-html",
            )
        ]
        result = self.processor().process({"files_urls": urls}, self.heartbeat)
        self.assertEqual(
            result["media_summary"],
            {"status": "partial", "total": 7, "stored": 1, "failed": 3, "skipped": 3},
        )
        self.assertEqual(result["files_urls"][1:], urls[1:])
        self.assertEqual(result["media_resources"][1]["error"]["code"], "http_error")
        self.assertFalse(result["media_resources"][1]["error"]["retryable"])
        self.assertEqual(MediaHandler.counts["/list.m3u8"], 0)

    def test_size_limits_cover_declared_length_and_streamed_bytes(self):
        """同时拦截预告超限和不带长度头的超限响应。"""
        result = self.processor(download_size_limit=16).process(
            {"files_urls": [self.base + "/image", self.base + "/stream"]},
            self.heartbeat,
        )
        self.assertEqual(
            [item["error"]["code"] for item in result["media_resources"]],
            ["size_limit", "size_limit"],
        )
        self.assertEqual(self.storage.puts, [])

    def test_total_budget_and_resource_limit(self):
        """累计下载和媒体数量上限都必须输出明确状态。"""
        data = {"files_urls": [self.base + "/image", self.base + "/video"]}
        limited = self.processor(total_size_limit=len(IMAGE), max_workers=1).process(
            data, self.heartbeat
        )
        self.assertEqual(
            limited["media_resources"][1]["error"]["code"], "total_size_limit"
        )
        capped = self.processor(max_resources=1).process(data, self.heartbeat)
        self.assertEqual(
            capped["media_resources"][1]["error"]["code"], "resource_limit"
        )

    def test_retry_is_bounded_and_recovers_transient_http_failure(self):
        """临时服务器错误可在限定次数内恢复。"""
        result = self.processor(max_retries=1).process(
            {"files_urls": [self.base + "/retry", self.base + "/missing"]},
            self.heartbeat,
        )
        self.assertEqual(result["media_resources"][0]["attempts"], 2)
        self.assertEqual(result["media_resources"][0]["status"], "stored")
        self.assertEqual(MediaHandler.counts["/retry"], 2)
        self.assertEqual(MediaHandler.counts["/missing"], 1)

    def test_read_timeout_and_record_deadline(self):
        """读取超时与整条数据预算耗尽均保留可重试错误。"""
        timed = self.processor(read_timeout_seconds=0.02).process(
            {"files_urls": [self.base + "/slow"]}, self.heartbeat
        )
        self.assertEqual(
            timed["media_resources"][0]["error"]["code"], "download_timeout"
        )
        expired = self.processor(media_timeout_seconds=0.00000001).process(
            {"files_urls": [self.base + "/video"]}, self.heartbeat
        )
        self.assertEqual(expired["media_resources"][0]["error"]["code"], "timeout")

    def test_storage_denial_never_reports_success(self):
        """对象存储拒绝访问时必须保留源地址和失败状态。"""
        self.storage.error_status = 403
        result = self.processor(max_retries=1).process(
            {"files_urls": [self.base + "/image"]}, self.heartbeat
        )
        resource = result["media_resources"][0]
        self.assertEqual(resource["error"]["code"], "storage_error")
        self.assertIsNone(resource["stored_url"])
        self.assertEqual(resource["attempts"], 1)
        self.assertEqual(result["files_urls"], [self.base + "/image"])

    def test_actual_boto_client_parameters(self):
        """使用 botocore 校验真实客户端的 HEAD 和上传参数。"""
        self.client_patch.stop()
        client = boto3.client(
            "s3",
            region_name="us-east-1",
            aws_access_key_id="test",
            aws_secret_access_key="test",
        )
        processor = self.processor()
        processor.client = client
        processor.bucket = "media"
        processor.base_url = "https://media.example.com"
        digest = hashlib.sha256(IMAGE).hexdigest()
        key = f"media_resource/{digest[:2]}/{digest}"
        with Stubber(client) as stubber:
            stubber.add_client_error(
                "head_object",
                "404",
                http_status_code=404,
                expected_params={"Bucket": "media", "Key": key},
            )
            stubber.add_response(
                "put_object",
                {},
                {
                    "Bucket": "media",
                    "Key": key,
                    "Body": ANY,
                    "ContentLength": len(IMAGE),
                    "ContentType": "image/png",
                },
            )
            result = processor.process(
                {"files_urls": [self.base + "/image"]}, self.heartbeat
            )
            stubber.assert_no_pending_responses()
        self.assertEqual(result["media_summary"]["stored"], 1)

    def test_empty_media_does_not_need_storage_and_rich_list_is_authoritative(self):
        """纯文本对象和显式空媒体清单不需要对象存储。"""
        with patch.dict(os.environ, {"COS_ENDPOINT": ""}):
            result = self.processor().process(
                {"media_resources": [], "files_urls": [self.base + "/image"]},
                self.heartbeat,
            )
            self.assertEqual(result["media_summary"]["status"], "empty")
            self.assertEqual(result["files_urls"], [])
            with self.assertRaisesRegex(ValueError, "COS_ENDPOINT"):
                self.processor().process(
                    {"files_urls": [self.base + "/image"]}, self.heartbeat
                )

    def test_invalid_input_and_config_fail_explicitly(self):
        """契约或配置错误不能被当成空数据成功处理。"""
        for data in (
            [],
            {"files_urls": "url"},
            {"files_urls": {}},
            {"media_resources": [42]},
            {"media_resources": [{}]},
        ):
            with self.subTest(data=data), self.assertRaises(ValueError):
                self.processor().process(data, self.heartbeat)
        for config in (
            {"max_workers": 0},
            {"max_workers": True},
            {"max_retries": -1},
            {"read_timeout_seconds": "nan"},
            {"download_headers": "{}"},
            {"failure_policy": "ignore"},
        ):
            with self.subTest(config=config), self.assertRaises(ValueError):
                self.processor(**config)
        self.assertEqual(parse_size("1.5 MB"), 1572864)
        for size in (True, 0, "bad", "9G"):
            with self.subTest(size=size), self.assertRaises(ValueError):
                parse_size(size)

    def test_bad_urls_empty_body_redirects_and_strict_mode(self):
        """非法地址、空文件和重定向清单应留下明确失败原因。"""
        result = self.processor().process(
            {
                "files_urls": [
                    "file:///tmp/example",
                    self.base + "/empty",
                    self.base + "/redirect",
                ]
            },
            self.heartbeat,
        )
        self.assertEqual(
            [item["error"]["code"] for item in result["media_resources"]],
            ["invalid_url", "empty_file", "unsupported_stream"],
        )
        with self.assertRaisesRegex(ValueError, "未全部完成"):
            self.processor(failure_policy="fail").process(
                {"files_urls": [self.base + "/missing"]}, self.heartbeat
            )

    def test_queue_publish_before_ack_preserves_message_identity(self):
        """向全部下游发送后才确认输入，并保留消息去重标识。"""
        context = self.context(
            {"data_in": {"type": "reference", "value": ["in-a", "in-b"]}},
            {"data_out": {"type": "reference", "value": ["out-a", "out-b", "out-a"]}},
        )
        rabbitmq = context._rabbitmq
        rabbitmq.get_message.side_effect = [
            {
                "body": json.dumps({"files_urls": [self.base + "/image"]}),
                "delivery_tag": 7,
                "message_id": "original-id",
            },
            None,
            None,
        ]
        rabbitmq.send_messages_batch.return_value = 2
        result = main.run(context)
        self.assertEqual(result["processed"], 1)
        args, kwargs = rabbitmq.send_messages_batch.call_args
        self.assertEqual(args[0], ["out-a", "out-b"])
        self.assertEqual(kwargs["message_id"], "original-id")
        self.assertEqual(args[1]["media_summary"]["stored"], 1)
        operations = [call[0] for call in rabbitmq.method_calls]
        self.assertLess(
            operations.index("send_messages_batch"), operations.index("ack_message")
        )
        rabbitmq.ack_message.assert_called_once_with(7)
        self.assertTrue(context.has_successful_result)
        self.assertTrue(self.storage.closed)

    def test_queue_failure_does_not_ack_or_loop(self):
        """格式错误、发布失败和确认失败都必须终止处理。"""
        for mode in (
            "invalid_json",
            "partial_publish",
            "ack_failure",
            "strict_failure",
        ):
            with self.subTest(mode=mode):
                context = self.context(
                    {"data_in": {"type": "reference", "value": "in"}},
                    {"data_out": {"type": "reference", "value": ["out"]}},
                    {"max_retries": 0, "failure_policy": "fail"},
                )
                rabbitmq = context._rabbitmq
                body = (
                    "bad-json"
                    if mode == "invalid_json"
                    else json.dumps(
                        {"files_urls": [self.base + "/missing"]}
                        if mode == "strict_failure"
                        else {}
                    )
                )
                rabbitmq.get_message.return_value = {
                    "body": body,
                    "delivery_tag": 9,
                    "message_id": "id",
                }
                rabbitmq.send_messages_batch.return_value = (
                    0 if mode == "partial_publish" else 1
                )
                rabbitmq.ack_message.return_value = mode != "ack_failure"
                with self.assertRaises(
                    (ComponentFailure, ReferenceStreamTransportError)
                ):
                    main.run(context)
                rabbitmq.get_message.assert_called_once()
                if mode != "ack_failure":
                    rabbitmq.ack_message.assert_not_called()
                self.assertFalse(context.has_successful_result)

    def test_empty_reference_stream_and_empty_dict_are_valid(self):
        """零结果队列和空对象均为有效输入，不误报运行失败。"""
        context = self.context(
            {"data_in": {"type": "reference", "value": "in"}},
            {"data_out": {"type": "reference", "value": "out"}},
        )
        context._rabbitmq.get_message.return_value = None
        self.assertEqual(main.run(context)["processed"], 0)
        value_context = self.context({"dict_in": {"type": "value", "value": {}}})
        result = main.run(value_context)
        self.assertEqual(result["dict_out"]["media_summary"]["status"], "empty")
        value_context._rabbitmq.process_data_events.assert_not_called()

    def test_control_errors_propagate_without_conversion(self):
        """SDK 取消、运行超时、上游 ABORT 和传输错误保持原语义。"""
        for error in (
            ComponentCancelled("取消"),
            ComponentTimedOut("超时"),
            ReferenceStreamAborted("终止"),
            ReferenceStreamTransportError("传输失败"),
        ):
            with self.subTest(error=type(error).__name__):
                context = self.context(
                    {"data_in": {"type": "reference", "value": "in"}},
                    {"data_out": {"type": "reference", "value": "out"}},
                )
                context._rabbitmq.get_message.side_effect = error
                with self.assertRaises(type(error)):
                    main.run(context)
                context._rabbitmq.ack_message.assert_not_called()

    def test_cancellation_during_processing_stops_pending_work(self):
        """下载期间的取消信号不被转换成普通媒体失败。"""
        processor = self.processor(read_timeout_seconds=0.1)
        self.heartbeat.side_effect = [None, ComponentCancelled("取消")]
        with self.assertRaises(ComponentCancelled):
            processor.process({"files_urls": [self.base + "/slow"]}, self.heartbeat)
        self.assertTrue(processor.stop.is_set())

    def test_interface_types_and_required_output_are_validated(self):
        """错误接口或缺失下游必须在消费消息前失败。"""
        for inputs, outputs in (
            ({}, {}),
            ({"dict_in": {"type": "reference", "value": {}}}, {}),
            ({"data_in": {"type": "value", "value": "in"}}, {}),
            ({"data_in": {"type": "reference", "value": "in"}}, {}),
        ):
            with self.subTest(inputs=inputs), self.assertRaises(ComponentFailure):
                main.run(self.context(inputs, outputs))

    def test_sdk_runner_loads_standalone_entrypoint(self):
        """通过真实 SDK 本地入口加载独立组件并完成一次媒体处理。"""
        component_directory = Path(__file__).resolve().parents[1]
        config = json.loads(
            (component_directory / "test_config.json").read_text(encoding="utf-8")
        )
        config["inputs"]["dict_in"]["value"]["media_resources"] = [self.base + "/image"]
        environment = os.environ.copy()
        environment["PYTHONPATH"] = os.pathsep.join(
            str(Path(path).resolve()) for path in sys.path if path
        )
        environment["PYTHONIOENCODING"] = "utf-8"
        environment["PYTHONUTF8"] = "1"
        script = """
import json
import sys
from types import SimpleNamespace
from unittest.mock import patch
from csi_base_component_sdk import runner
from test_media_processor import MemoryStorage
with patch('processor.boto3.client', return_value=MemoryStorage()), patch.object(runner, 'save_item'), patch.object(runner._LocalClient, 'submit_result') as submit:
    code = runner.run_component(SimpleNamespace(entrypoint='main:run', local_config=sys.argv[1]))
    print(json.dumps(submit.call_args.args[0], ensure_ascii=False))
    raise SystemExit(code)
"""
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "input.json"
            path.write_text(json.dumps(config, ensure_ascii=False), encoding="utf-8")
            completed = subprocess.run(
                [sys.executable, "-c", script, str(path)],
                cwd=component_directory,
                env=environment,
                text=True,
                encoding="utf-8",
                capture_output=True,
                timeout=30,
            )
        self.assertEqual(completed.returncode, 0, completed.stderr)
        result = json.loads(completed.stdout.strip().splitlines()[-1])
        self.assertEqual(result["status"], "success")
        self.assertEqual(result["outputs"]["dict_out"]["media_summary"]["stored"], 1)


if __name__ == "__main__":
    unittest.main()
