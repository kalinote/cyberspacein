import os
import logging
from typing import Callable
from concurrent.futures import ThreadPoolExecutor, wait
from urllib.parse import urljoin, urlparse
from dotenv import load_dotenv
from analyzer.media_downloader import MediaDownloader
from analyzer.cos_uploader import COSUploader

load_dotenv()

logger = logging.getLogger(__name__)


class MediaLocalizer:

    def __init__(self, base_url: str | None = None, download_size_limit: int | None = None):
        self.base_url = base_url
        self.download_size_limit = download_size_limit
        self.max_workers = int(os.getenv("MAX_DOWNLOAD_WORKERS", "4"))
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

        if not links:
            return html_content

        try:
            url_mapping = self._download_and_upload(links, heartbeat_callback)
            if not url_mapping:
                return html_content
            result = self._replace_links_in_html(html_content, url_mapping)
            logger.info(f"媒体本地化完成: 成功处理 {len(url_mapping)} 个资源")
            return result
        except Exception as e:
            logger.error(f"媒体本地化失败: {e}", exc_info=True)
            return html_content

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
    ) -> dict[str, str]:
        url_mapping: dict[str, str] = {}

        def download_and_upload_one(original_link: str) -> tuple[str, str | None]:
            absolute_url = self._normalize_url(original_link)
            if not absolute_url:
                return original_link, None
            if not MediaDownloader.is_valid_url(absolute_url):
                return original_link, None
            downloader = MediaDownloader(
                referer=self.base_url,
                download_size_limit=self.download_size_limit,
            )
            try:
                download_result = downloader.download(absolute_url)
                if download_result is None:
                    return original_link, None
                content, file_hash, content_type = download_result
                cos_url = self.uploader.upload_file(content, file_hash, content_type)
                if cos_url:
                    logger.debug(f"资源本地化成功: {original_link} -> {cos_url}")
                    return original_link, cos_url
                return original_link, None
            except Exception as e:
                logger.warning(f"下载上传失败: {original_link} - {e}")
                return original_link, None
            finally:
                downloader.close()

        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            futures = {executor.submit(download_and_upload_one, link): link for link in links}
            pending = set(futures.keys())

            while pending:
                if heartbeat_callback:
                    try:
                        heartbeat_callback()
                    except Exception as e:
                        logger.warning(f"心跳回调执行失败: {e}")
                done, pending = wait(pending, timeout=2.0)
                for future in done:
                    try:
                        orig, cos_url = future.result()
                        if cos_url:
                            url_mapping[orig] = cos_url
                    except Exception as e:
                        link = futures[future]
                        logger.warning(f"处理下载结果失败: {link} - {e}")

        return url_mapping

    def _replace_links_in_html(self, html: str, url_mapping: dict[str, str]) -> str:
        if not url_mapping:
            return html
        sorted_items = sorted(url_mapping.items(), key=lambda x: -len(x[0]))
        for orig, cos_url in sorted_items:
            html = html.replace(orig, cos_url)
        return html
