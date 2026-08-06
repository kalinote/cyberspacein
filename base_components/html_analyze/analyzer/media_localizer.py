import os
import re
import base64
import logging
import threading
import time
from typing import Callable
from concurrent.futures import FIRST_COMPLETED, ThreadPoolExecutor, wait
from urllib.parse import urljoin, urlparse
from dotenv import load_dotenv
from analyzer.media_downloader import MediaDownloader
from analyzer.cos_uploader import COSUploader

load_dotenv()

logger = logging.getLogger(__name__)


class MediaLocalizer:

    def __init__(
        self,
        base_url: str | None = None,
        download_size_limit: int | None = None,
        timeout_seconds: float | None = None,
    ):
        self.base_url = base_url
        self.download_size_limit = download_size_limit
        self.max_workers = max(1, min(int(os.getenv("MAX_DOWNLOAD_WORKERS", "4")), 32))
        configured_timeout = (
            timeout_seconds
            if timeout_seconds is not None
            else float(os.getenv("MEDIA_LOCALIZATION_TIMEOUT_SECONDS", "600"))
        )
        self.timeout_seconds = max(float(configured_timeout), 1)
        self.max_urls = max(int(os.getenv("MEDIA_LOCALIZATION_MAX_URLS", "200")), 0)
        self.max_base64_images = max(int(os.getenv("MEDIA_LOCALIZATION_MAX_BASE64_IMAGES", "50")), 0)
        self.max_base64_total_bytes = max(
            int(os.getenv("MEDIA_LOCALIZATION_MAX_BASE64_TOTAL_BYTES", str(100 * 1024 * 1024))),
            0,
        )
        self.max_total_media_bytes = max(
            int(os.getenv("MEDIA_LOCALIZATION_MAX_TOTAL_BYTES", str(200 * 1024 * 1024))),
            0,
        )
        self.download_connect_timeout = max(
            float(os.getenv("MEDIA_DOWNLOAD_CONNECT_TIMEOUT_SECONDS", "10")),
            0.1,
        )
        self.download_read_timeout = max(
            float(os.getenv("MEDIA_DOWNLOAD_READ_TIMEOUT_SECONDS", "30")),
            0.1,
        )
        self.download_max_retries = max(int(os.getenv("MEDIA_DOWNLOAD_MAX_RETRIES", "1")), 0)
        self._localized_bytes = 0
        self._localized_bytes_lock = threading.Lock()
        self.uploader = COSUploader()

    def localize(
        self,
        html_content: str,
        links: list[str],
        heartbeat_callback: Callable[[], None] | None = None,
    ) -> str:
        if not self.uploader.is_configured():
            logger.warning("COS未配置，跳过媒体本地化")
            return html_content

        if not html_content:
            return html_content

        deadline = time.monotonic() + self.timeout_seconds
        self._localized_bytes = 0

        try:
            html_content, links = self._fix_lazy_img_sources(html_content, links)
        except Exception as e:
            logger.warning(f"懒加载图片预处理失败: {e}")

        html_content = self._process_base64_images(
            html_content,
            deadline=deadline,
            heartbeat_callback=heartbeat_callback,
        )

        if not links:
            return html_content

        unique_links = list(dict.fromkeys(links))
        if len(unique_links) > self.max_urls:
            logger.warning(
                f"媒体链接数量 {len(unique_links)} 超过限制 {self.max_urls}，"
                "超出部分保留原链接"
            )
            unique_links = unique_links[:self.max_urls]

        if time.monotonic() >= deadline:
            logger.warning("媒体本地化预算已耗尽，URL资源保留原链接")
            return html_content

        url_mapping = self._download_and_upload(
            unique_links,
            heartbeat_callback,
            deadline=deadline,
        )
        if not url_mapping:
            return html_content
        result = self._replace_links_in_html(html_content, url_mapping)
        logger.info(f"媒体本地化完成: 成功处理 {len(url_mapping)} 个资源")
        return result

    # 懒加载属性按优先级排列：
    # 论坛专有属性（Discuz 等）优先，因为通常是高清原图；
    # 其次是业界主流懒加载库的标准属性；
    # real_src 为老旧论坛兜底
    _LAZY_SRC_ATTRS = (
        "zoomfile",       # Discuz 论坛
        "file",           # Discuz 论坛
        "data-src",       # lazysizes / vanilla-lazyload 等主流库
        "data-original",  # jQuery LazyLoad
        "data-lazy-src",  # WordPress 等
        "data-lazy",      # 各类自定义实现
        "data-url",       # 各类 CMS
        "data-image",     # 各类 CMS
        "data-img",       # 各类自定义实现
        "real_src",       # 部分国内旧论坛
    )

    def _fix_lazy_img_sources(self, html: str, links: list[str]) -> tuple[str, list[str]]:
        """处理懒加载图片：从非标准属性中提取真实图片 URL 并替换 src"""
        extra_links: list[str] = []
        existing_links_set = set(links)

        def replace_src(m: re.Match) -> str:
            img_tag = m.group(0)
            real_url = None
            for attr in self._LAZY_SRC_ATTRS:
                attr_m = re.search(rf"""{re.escape(attr)}=['"]([^'"]+)['"]""", img_tag, re.IGNORECASE)
                if attr_m:
                    url = attr_m.group(1).strip()
                    if MediaDownloader.is_valid_url(url):
                        real_url = url
                        break

            if not real_url:
                return img_tag

            if real_url not in existing_links_set and real_url not in extra_links:
                extra_links.append(real_url)

            new_tag = re.sub(
                r"""src=['"][^'"]*['"]""",
                f'src="{real_url}"',
                img_tag,
                count=1,
                flags=re.IGNORECASE,
            )
            for attr in self._LAZY_SRC_ATTRS:
                new_tag = re.sub(
                    rf"""\s+{re.escape(attr)}=['"][^'"]*['"]""",
                    "",
                    new_tag,
                    flags=re.IGNORECASE,
                )
            return new_tag

        new_html = re.sub(r"<img\b[^>]*>", replace_src, html, flags=re.IGNORECASE)
        if extra_links:
            logger.debug(f"从懒加载图片属性中提取到 {len(extra_links)} 个真实图片 URL")
        return new_html, links + extra_links

    def _normalize_url(self, link: str) -> str | None:
        link = link.strip()
        if not link:
            return None
        try:
            parsed = urlparse(link)
            if parsed.scheme in ("http", "https"):
                return link
            if not parsed.scheme and self.base_url:
                return urljoin(self.base_url, link)
            return None
        except Exception as e:
            logger.debug(f"URL规范化失败: {link} - {e}")
            return None

    def _download_and_upload(
        self,
        links: list[str],
        heartbeat_callback: Callable[[], None] | None,
        deadline: float,
    ) -> dict[str, str]:
        url_mapping: dict[str, str] = {}
        media_limit_reached = threading.Event()

        def download_and_upload_one(original_link: str) -> tuple[str, str | None]:
            if media_limit_reached.is_set():
                return original_link, None
            absolute_url = self._normalize_url(original_link)
            if not absolute_url:
                return original_link, None
            if not MediaDownloader.is_valid_url(absolute_url):
                return original_link, None
            with self._localized_bytes_lock:
                remaining_media_bytes = self.max_total_media_bytes - self._localized_bytes
            if remaining_media_bytes <= 0:
                media_limit_reached.set()
                return original_link, None
            resource_size_limit = remaining_media_bytes
            if self.download_size_limit is not None:
                resource_size_limit = min(resource_size_limit, self.download_size_limit)
            downloader = MediaDownloader(
                connect_timeout=self.download_connect_timeout,
                read_timeout=self.download_read_timeout,
                max_retries=self.download_max_retries,
                referer=self.base_url,
                download_size_limit=resource_size_limit,
            )
            try:
                download_result = downloader.download(absolute_url, deadline=deadline)
                if download_result is None:
                    return original_link, None
                content, file_hash, content_type = download_result
                if time.monotonic() >= deadline:
                    return original_link, None
                with self._localized_bytes_lock:
                    if self._localized_bytes + len(content) > self.max_total_media_bytes:
                        media_limit_reached.set()
                        logger.warning("媒体累计大小达到限制，后续资源保留原链接")
                        return original_link, None
                    self._localized_bytes += len(content)
                    if self._localized_bytes >= self.max_total_media_bytes:
                        media_limit_reached.set()
                cos_url = self.uploader.upload_file(
                    content,
                    file_hash,
                    content_type,
                    deadline=deadline,
                )
                if cos_url:
                    logger.debug(f"资源本地化成功: {original_link} -> {cos_url}")
                    return original_link, cos_url
                return original_link, None
            except Exception as e:
                logger.warning(f"下载上传失败: {original_link} - {e}")
                return original_link, None
            finally:
                downloader.close()

        link_iterator = iter(links)
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            futures = {}
            for _ in range(self.max_workers):
                link = next(link_iterator, None)
                if (
                    link is None
                    or media_limit_reached.is_set()
                    or time.monotonic() >= deadline
                ):
                    break
                futures[executor.submit(download_and_upload_one, link)] = link

            while futures:
                if heartbeat_callback:
                    heartbeat_callback()
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    logger.warning("媒体本地化预算已耗尽，停止提交新资源")
                    for future in futures:
                        future.cancel()
                    break
                done, _ = wait(
                    set(futures),
                    timeout=min(2.0, remaining),
                    return_when=FIRST_COMPLETED,
                )
                for future in done:
                    link = futures.pop(future)
                    try:
                        orig, cos_url = future.result()
                        if cos_url:
                            url_mapping[orig] = cos_url
                    except Exception as e:
                        logger.warning(f"处理下载结果失败: {link} - {e}")

                    next_link = next(link_iterator, None)
                    if (
                        next_link is not None
                        and not media_limit_reached.is_set()
                        and time.monotonic() < deadline
                    ):
                        futures[executor.submit(download_and_upload_one, next_link)] = next_link

        return url_mapping

    def _process_base64_images(
        self,
        html: str,
        deadline: float,
        heartbeat_callback: Callable[[], None] | None,
    ) -> str:
        """处理HTML中所有属性里的base64内联图片，上传至COS并替换为COS链接"""
        # 兼容常见 data URI 变体：
        # - 额外参数：data:image/png;charset=utf-8;base64,...
        # - base64 中夹杂空白/换行（HTML 压缩/换行导致）
        # - URL-safe base64 字符：- _
        pattern = re.compile(
            r"data:image/([^;,]+)(?:;[^,;]+(?:=[^,;]+)?)?;base64,([A-Za-z0-9+/=_\-\s]+)",
            re.IGNORECASE,
        )
        b64_cache: dict[str, str | None] = {}
        base64_count = 0
        base64_total_bytes = 0

        for m in pattern.finditer(html):
            data_uri = m.group(0)
            if data_uri in b64_cache:
                continue
            if heartbeat_callback:
                heartbeat_callback()
            if time.monotonic() >= deadline:
                logger.warning("媒体本地化预算已耗尽，剩余base64图片保留原值")
                break
            if base64_count >= self.max_base64_images:
                logger.warning(
                    f"base64图片数量达到限制 {self.max_base64_images}，剩余图片保留原值"
                )
                break
            base64_count += 1

            mime_subtype = m.group(1).lower()
            b64_data = re.sub(r"\s+", "", m.group(2))
            content_type = f"image/{mime_subtype}"

            estimated_size = len(b64_data) * 3 // 4
            if self.download_size_limit and estimated_size > self.download_size_limit:
                logger.warning(f"base64图片估算大小 {estimated_size / (1024 * 1024):.2f}MB 超过限制，跳过")
                b64_cache[data_uri] = None
                continue
            if base64_total_bytes + estimated_size > self.max_base64_total_bytes:
                logger.warning("base64图片累计大小达到限制，剩余图片保留原值")
                break

            try:
                # validate=False 以兼容 URL-safe 的 '-' '_'（很多站点会混用）
                content = base64.b64decode(b64_data, validate=False)
            except Exception as e:
                logger.warning(f"base64解码失败: {e}")
                b64_cache[data_uri] = None
                continue

            if self.download_size_limit and len(content) > self.download_size_limit:
                logger.warning(f"base64图片大小 {len(content) / (1024 * 1024):.2f}MB 超过限制，跳过")
                b64_cache[data_uri] = None
                continue

            base64_total_bytes += len(content)
            with self._localized_bytes_lock:
                if self._localized_bytes + len(content) > self.max_total_media_bytes:
                    logger.warning("媒体累计大小达到限制，剩余base64图片保留原值")
                    break
                self._localized_bytes += len(content)

            file_hash = MediaDownloader.calculate_sha256(content)
            cos_url = self.uploader.upload_file(
                content,
                file_hash,
                content_type,
                deadline=deadline,
            )
            b64_cache[data_uri] = cos_url
            if cos_url:
                logger.debug(f"base64图片上传成功: {content_type}, {len(content) / 1024:.1f}KB -> {cos_url}")

        success_count = sum(1 for v in b64_cache.values() if v is not None)
        if not success_count:
            return html

        logger.info(f"base64图片处理完成: 成功处理 {success_count} 张图片")

        def replace_match(m: re.Match) -> str:
            cos_url = b64_cache.get(m.group(0))
            return cos_url if cos_url is not None else m.group(0)

        return pattern.sub(replace_match, html)

    def _replace_links_in_html(self, html: str, url_mapping: dict[str, str]) -> str:
        if not url_mapping:
            return html
        sorted_items = sorted(url_mapping.items(), key=lambda x: -len(x[0]))
        for orig, cos_url in sorted_items:
            html = html.replace(orig, cos_url)
        return html
