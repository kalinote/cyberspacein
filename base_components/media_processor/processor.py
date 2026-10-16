"""独立处理结构化媒体清单，不解析 HTML 或平台原始数据。"""

from __future__ import annotations

import hashlib
import math
import os
import re
import threading
import time
from concurrent.futures import FIRST_COMPLETED, ThreadPoolExecutor, wait
from copy import deepcopy
from tempfile import SpooledTemporaryFile
from typing import Callable
from urllib.parse import urlsplit

import boto3
import requests
from botocore.config import Config
from botocore.exceptions import BotoCoreError, ClientError


class MediaError(Exception):
    """携带可供下游判断和重试的媒体处理错误。"""

    def __init__(
        self, code: str, message: str, retryable: bool = False, status: str = "failed"
    ):
        """记录错误码、中文说明、可重试性及结果状态。"""
        super().__init__(message)
        self.code = code
        self.retryable = retryable
        self.status = status


def parse_size(value: int | str) -> int:
    """将正整数字节数或带 K、M、G 单位的字符串转换为字节数。"""
    match = re.fullmatch(r"\s*(\d+(?:\.\d+)?)\s*([KMG]?)(?:I?B)?\s*", str(value), re.I)
    if not match:
        raise ValueError("大小限制必须是正数字节数或带 K、M、G 单位的字符串")
    size = int(
        float(match[1]) * 1024 ** {"": 0, "K": 1, "M": 2, "G": 3}[match[2].upper()]
    )
    if not 0 < size <= 5 * 1024**3:
        raise ValueError("大小限制必须大于 0 且不超过 5 GiB")
    return size


class MediaProcessor:
    """下载媒体直链并归档到 S3 兼容存储，保留逐项处理结果。"""

    def __init__(self, config: dict):
        """校验处理配置并准备线程池，存储客户端在遇到媒体时初始化。

        Args:
            config: 下载限制、并发数、失败策略及可选请求头和代理。

        Raises:
            ValueError: 配置类型或取值无效。
        """
        self.max_workers = config.get("max_workers", 4)
        self.max_resources = config.get("max_resources", 100)
        self.max_retries = config.get("max_retries", 1)
        for name, value, lower, upper in (
            ("max_workers", self.max_workers, 1, 16),
            ("max_resources", self.max_resources, 1, 1000),
            ("max_retries", self.max_retries, 0, 5),
        ):
            if (
                isinstance(value, bool)
                or not isinstance(value, int)
                or not lower <= value <= upper
            ):
                raise ValueError(f"{name} 必须是 {lower} 到 {upper} 之间的整数")
        self.size_limit = parse_size(config.get("download_size_limit", "50M"))
        self.total_size_limit = parse_size(config.get("total_size_limit", "200M"))
        self.timeout = float(config.get("media_timeout_seconds", 600))
        self.connect_timeout = float(config.get("connect_timeout_seconds", 10))
        self.read_timeout = float(config.get("read_timeout_seconds", 15))
        if any(
            not math.isfinite(value) or value <= 0
            for value in (self.timeout, self.connect_timeout, self.read_timeout)
        ):
            raise ValueError("处理预算及连接、读取超时必须是有限正数")
        self.failure_policy = config.get("failure_policy", "continue")
        if self.failure_policy not in ("continue", "fail"):
            raise ValueError("failure_policy 只支持 continue 或 fail")
        self.headers = config.get("download_headers") or {}
        if not isinstance(self.headers, dict) or any(
            not isinstance(key, str) or not isinstance(value, str)
            for key, value in self.headers.items()
        ):
            raise ValueError("download_headers 必须是字符串键值对象")
        self.headers = requests.structures.CaseInsensitiveDict(self.headers)
        self.headers.setdefault("User-Agent", "CSI-MediaProcessor/1.0")
        self.proxy = config.get("proxy_url") or os.getenv("DOWNLOAD_PROXY")
        if self.proxy and not isinstance(self.proxy, str):
            raise ValueError("proxy_url 必须是字符串")
        self.prefix = config.get("object_prefix", "media_resource")
        if not isinstance(self.prefix, str) or not re.fullmatch(
            r"[\w-]+(?:/[\w-]+)*", self.prefix
        ):
            raise ValueError(
                "object_prefix 只能包含字母、数字、下划线、短横线和路径分隔符"
            )
        self.client = None
        self.bucket = ""
        self.base_url = ""
        self.stop = threading.Event()
        self.executor = ThreadPoolExecutor(
            max_workers=self.max_workers, thread_name_prefix="媒体处理"
        )

    def _check_budget(self, budget: dict) -> float:
        """检查取消标记和软时间预算，返回当前剩余秒数。"""
        if self.stop.is_set():
            raise MediaError("cancelled", "媒体处理已取消", True)
        remaining = budget["deadline"] - time.monotonic()
        if remaining <= 0:
            raise MediaError("timeout", "单条数据的媒体处理时间预算已耗尽", True)
        return remaining

    def _archive(
        self, source_url: str, previous: dict, referer: str | None, budget: dict
    ) -> dict:
        """处理一个源地址，执行有限重试并返回不含平台元数据的结果。

        Args:
            source_url: 原始媒体直链。
            previous: 上次处理结果，用于验证已归档对象并跳过重新下载。
            referer: 可选的来源页面地址。
            budget: 同一条数据共享的时间、累计下载大小与锁。

        Returns:
            包含状态、归档信息或结构化错误的字典。
        """
        attempts = 0
        try:
            parsed = urlsplit(source_url)
            if (
                parsed.scheme not in ("http", "https")
                or not parsed.hostname
                or parsed.username
                or parsed.password
            ):
                raise ValueError
            parsed.port
        except ValueError:
            error = MediaError(
                "invalid_url", "媒体地址必须是无内嵌凭据的 HTTP 或 HTTPS 地址"
            )
        else:
            error = None
            for attempts in range(1, self.max_retries + 2):
                try:
                    self._check_budget(budget)
                    if parsed.path.lower().endswith((".m3u8", ".m3u", ".mpd")):
                        raise MediaError(
                            "unsupported_stream",
                            "暂不支持 HLS/DASH 分片媒体，请提供媒体文件直链",
                            status="skipped",
                        )
                    digest = previous.get("sha256", "")
                    existing_key = (
                        f"{self.prefix}/{digest[:2]}/{digest}"
                        if isinstance(digest, str)
                        else ""
                    )
                    if (
                        previous.get("status") == "stored"
                        and isinstance(digest, str)
                        and re.fullmatch(r"[0-9a-f]{64}", digest)
                        and previous.get("storage_key") == existing_key
                        and previous.get("stored_url")
                        == f"{self.base_url}/{existing_key}"
                    ):
                        try:
                            metadata = self.client.head_object(
                                Bucket=self.bucket, Key=existing_key
                            )
                        except ClientError as exc:
                            if str(exc.response.get("Error", {}).get("Code")) not in (
                                "404",
                                "NoSuchKey",
                                "NotFound",
                            ):
                                raise
                        else:
                            return {
                                "status": "stored",
                                "stored_url": previous["stored_url"],
                                "sha256": digest,
                                "storage_key": existing_key,
                                "size": metadata["ContentLength"],
                                "content_type": metadata.get(
                                    "ContentType", "application/octet-stream"
                                ),
                                "attempts": attempts,
                                "error": None,
                            }
                    result = self._download_and_upload(source_url, referer, budget)
                    result.update(status="stored", attempts=attempts, error=None)
                    return result
                except MediaError as exc:
                    error = exc
                except requests.Timeout:
                    error = MediaError(
                        "download_timeout", "媒体下载连接或读取超时", True
                    )
                except requests.RequestException:
                    error = MediaError("download_error", "媒体下载请求失败", True)
                except ClientError as exc:
                    status = exc.response.get("ResponseMetadata", {}).get(
                        "HTTPStatusCode", 0
                    )
                    error = MediaError(
                        "storage_error",
                        "对象存储请求失败",
                        status in (408, 429) or status >= 500,
                    )
                except BotoCoreError:
                    error = MediaError("storage_error", "对象存储连接或上传失败", True)
                except OSError:
                    error = MediaError("local_io_error", "媒体临时文件读写失败")
                if not error.retryable or attempts > self.max_retries:
                    break
                self.stop.wait(
                    min(0.5 * attempts, max(0, budget["deadline"] - time.monotonic()))
                )
        return {
            "status": error.status,
            "stored_url": None,
            "storage_key": None,
            "sha256": None,
            "size": None,
            "content_type": None,
            "attempts": attempts,
            "error": {
                "code": error.code,
                "message": str(error),
                "retryable": error.retryable,
            },
        }

    def _download_and_upload(
        self, source_url: str, referer: str | None, budget: dict
    ) -> dict:
        """流式下载并计算哈希，检查对象存在性后按需上传。

        Args:
            source_url: 需要下载的媒体直链。
            referer: 可选的来源页面地址。
            budget: 当前数据的共享处理预算。

        Returns:
            归档地址、对象键、哈希、大小和实际响应类型。

        Raises:
            MediaError: 下载结果无效、超过限制或格式暂不支持。
            requests.RequestException: 请求失败，交由上层有限重试。
            BotoCoreError: 对象存储请求失败。
            ClientError: 对象存储返回错误。
        """
        remaining = self._check_budget(budget)
        with (
            requests.Session() as session,
            SpooledTemporaryFile(max_size=1024 * 1024, mode="w+b") as content,
        ):
            session.max_redirects = 5
            session.headers.update(self.headers)
            if referer:
                session.headers.setdefault("Referer", referer)
            if self.proxy:
                session.proxies.update(http=self.proxy, https=self.proxy)
            with session.get(
                source_url,
                stream=True,
                timeout=(
                    min(self.connect_timeout, remaining),
                    min(self.read_timeout, remaining),
                ),
            ) as response:
                if response.status_code != 200:
                    status = response.status_code
                    raise MediaError(
                        "http_error",
                        f"媒体服务器返回 HTTP {status}",
                        status in (408, 425, 429) or status >= 500,
                    )
                content_type = (
                    response.headers.get("Content-Type", "application/octet-stream")
                    .split(";", 1)[0]
                    .strip()
                    .lower()
                )
                if (
                    "mpegurl" in content_type
                    or content_type == "application/dash+xml"
                    or urlsplit(response.url)
                    .path.lower()
                    .endswith((".m3u8", ".m3u", ".mpd"))
                ):
                    raise MediaError(
                        "unsupported_stream",
                        "暂不支持 HLS/DASH 分片媒体，请提供媒体文件直链",
                        status="skipped",
                    )
                if content_type in ("text/html", "application/xhtml+xml"):
                    raise MediaError("html_response", "媒体地址返回了 HTML 页面")
                length = response.headers.get("Content-Length", "")
                if length.isdigit() and int(length) > self.size_limit:
                    raise MediaError("size_limit", "媒体大小超过单文件下载限制")
                digest = hashlib.sha256()
                size = 0
                prefix = b""
                for chunk in response.iter_content(chunk_size=8192):
                    self._check_budget(budget)
                    if not chunk:
                        continue
                    size += len(chunk)
                    if size > self.size_limit:
                        raise MediaError("size_limit", "媒体大小超过单文件下载限制")
                    with budget["lock"]:
                        budget["downloaded"] += len(chunk)
                        if budget["downloaded"] > self.total_size_limit:
                            raise MediaError(
                                "total_size_limit", "媒体累计下载量超过单条数据的限制"
                            )
                    prefix = (prefix + chunk)[:1024]
                    content.write(chunk)
                    digest.update(chunk)
            if size == 0:
                raise MediaError("empty_file", "媒体服务器返回了空文件")
            sniff = prefix.lstrip(b"\xef\xbb\xbf \t\r\n").lower()
            if sniff.startswith(b"#extm3u") or (
                sniff.startswith(b"<") and b"<mpd" in sniff
            ):
                raise MediaError(
                    "unsupported_stream",
                    "响应内容为 HLS/DASH 播放清单",
                    status="skipped",
                )
            if sniff.startswith((b"<!doctype html", b"<html", b"<head", b"<body")):
                raise MediaError("html_response", "媒体地址返回了 HTML 页面")
            file_hash = digest.hexdigest()
            key = f"{self.prefix}/{file_hash[:2]}/{file_hash}"
            self._check_budget(budget)
            try:
                self.client.head_object(Bucket=self.bucket, Key=key)
            except ClientError as exc:
                if str(exc.response.get("Error", {}).get("Code")) not in (
                    "404",
                    "NoSuchKey",
                    "NotFound",
                ):
                    raise
                self._check_budget(budget)
                content.seek(0)
                self.client.put_object(
                    Bucket=self.bucket,
                    Key=key,
                    Body=content,
                    ContentLength=size,
                    ContentType=content_type or "application/octet-stream",
                )
            return {
                "stored_url": f"{self.base_url}/{key}",
                "storage_key": key,
                "sha256": file_hash,
                "size": size,
                "content_type": content_type or "application/octet-stream",
            }

    def process(self, data: dict, heartbeat: Callable[[], None]) -> dict:
        """处理一条业务数据，仅更新媒体清单、文件地址及媒体统计。

        Args:
            data: 业务对象；优先读取 media_resources，否则读取 files_urls。
            heartbeat: 在主线程维持 SDK 心跳并检查取消的回调。

        Returns:
            保留原业务字段并附带媒体处理结果的新对象。

        Raises:
            ValueError: 输入契约或存储配置无效，或严格模式下存在未归档媒体。
        """
        heartbeat()
        if not isinstance(data, dict):
            raise ValueError("输入数据必须是 JSON 对象")
        resources = data.get("media_resources")
        if resources is None:
            resources = data.get("files_urls")
        if resources is None:
            resources = []
        if not isinstance(resources, list):
            raise ValueError("media_resources 或 files_urls 必须是数组")
        entries = []
        unique = {}
        for resource in resources:
            entry = (
                {"source_url": resource}
                if isinstance(resource, str)
                else deepcopy(resource)
            )
            if (
                not isinstance(entry, dict)
                or not isinstance(entry.get("source_url"), str)
                or not entry["source_url"].strip()
            ):
                raise ValueError("媒体项必须是地址字符串或带非空 source_url 的对象")
            entry["source_url"] = entry["source_url"].strip()
            entries.append(entry)
            if entry["source_url"] not in unique or entry.get("status") == "stored":
                unique[entry["source_url"]] = entry
        if entries and self.client is None:
            settings = {
                name: os.getenv(name)
                for name in (
                    "COS_ENDPOINT",
                    "COS_ACCESS_KEY",
                    "COS_SECRET_KEY",
                    "COS_BUCKET",
                )
            }
            missing = [name for name, value in settings.items() if not value]
            if missing:
                raise ValueError(f"缺少对象存储环境变量：{', '.join(missing)}")
            self.bucket = settings["COS_BUCKET"]
            self.base_url = (
                os.getenv("COS_BASE_URL")
                or f"{settings['COS_ENDPOINT'].rstrip('/')}/{self.bucket}"
            ).rstrip("/")
            self.client = boto3.client(
                "s3",
                endpoint_url=settings["COS_ENDPOINT"],
                aws_access_key_id=settings["COS_ACCESS_KEY"],
                aws_secret_access_key=settings["COS_SECRET_KEY"],
                region_name=os.getenv("COS_REGION", "us-east-1"),
                config=Config(
                    connect_timeout=self.connect_timeout,
                    read_timeout=self.read_timeout,
                    retries={"total_max_attempts": 1},
                    max_pool_connections=self.max_workers,
                    s3={"addressing_style": "path"},
                ),
            )
        budget = {
            "deadline": time.monotonic() + self.timeout,
            "downloaded": 0,
            "lock": threading.Lock(),
        }
        referer = data.get("url")
        if not isinstance(referer, str) or not referer.startswith(
            ("http://", "https://")
        ):
            referer = None
        results = {}
        pending = {}
        try:
            for index, (source_url, previous) in enumerate(unique.items()):
                if index >= self.max_resources:
                    results[source_url] = {
                        "status": "skipped",
                        "stored_url": None,
                        "storage_key": None,
                        "sha256": None,
                        "size": None,
                        "content_type": None,
                        "attempts": 0,
                        "error": {
                            "code": "resource_limit",
                            "message": "媒体数量超过单条数据的处理限制",
                            "retryable": False,
                        },
                    }
                    continue
                pending[
                    self.executor.submit(
                        self._archive, source_url, previous, referer, budget
                    )
                ] = source_url
            while pending:
                heartbeat()
                done, _ = wait(pending, timeout=0.2, return_when=FIRST_COMPLETED)
                for future in done:
                    results[pending.pop(future)] = future.result()
            heartbeat()
        except BaseException:
            self.stop.set()
            for future in pending:
                future.cancel()
            raise
        processed = [{**entry, **results[entry["source_url"]]} for entry in entries]
        counts = {
            state: sum(item["status"] == state for item in processed)
            for state in ("stored", "failed", "skipped")
        }
        status = (
            "empty"
            if not processed
            else "complete"
            if counts["stored"] == len(processed)
            else "partial"
            if counts["stored"]
            else "failed"
        )
        if self.failure_policy == "fail" and (counts["failed"] or counts["skipped"]):
            raise ValueError(
                f"媒体归档未全部完成：成功 {counts['stored']}，失败 {counts['failed']}，跳过 {counts['skipped']}"
            )
        return {
            **data,
            "media_resources": processed,
            "files_urls": list(
                dict.fromkeys(
                    item["stored_url"] or item["source_url"] for item in processed
                )
            ),
            "media_summary": {"status": status, "total": len(processed), **counts},
        }

    def close(self) -> None:
        """停止待执行任务并释放本组件持有的线程和存储连接。"""
        self.stop.set()
        self.executor.shutdown(wait=True, cancel_futures=True)
        if self.client is not None:
            self.client.close()
