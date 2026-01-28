import os
import logging
import re
from typing import Set, Callable
from concurrent.futures import ThreadPoolExecutor, wait
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse
from dotenv import load_dotenv
from analyzer.media_downloader import MediaDownloader
from analyzer.cos_uploader import COSUploader

load_dotenv()

logger = logging.getLogger(__name__)


class MediaLocalizer:
    
    MEDIA_TAGS_ATTRS = {
        'img': ['src', 'srcset', 'data-src', 'data-srcset'],
        'video': ['src', 'poster', 'data-src', 'data-poster'],
        'audio': ['src', 'data-src'],
        'source': ['src', 'srcset', 'data-src', 'data-srcset'],
        'image': ['href', 'xlink:href'],
    }
    
    def __init__(self, base_url: str | None = None, download_size_limit: int | None = None):
        self.base_url = base_url
        self.download_size_limit = download_size_limit
        self.max_workers = int(os.getenv('MAX_DOWNLOAD_WORKERS', '4'))
        self.uploader = COSUploader()
        self.url_mapping: dict[str, str] = {}
        self.processed_urls: Set[str] = set()
    
    def localize(self, html_content: str, heartbeat_callback: Callable[[], None] | None = None) -> str:
        if not self.uploader.is_configured():
            logger.warning("COS未配置，跳过媒体本地化")
            return html_content
        
        if not html_content:
            return html_content
        
        try:
            soup = BeautifulSoup(html_content, 'html.parser')
            
            urls_to_download = self._collect_urls(soup)
            
            if urls_to_download:
                self._download_urls_parallel(urls_to_download, heartbeat_callback)
            
            self._apply_url_mapping(soup)
            
            result = str(soup)
            
            if self.url_mapping:
                logger.info(f"媒体本地化完成: 成功处理 {len(self.url_mapping)} 个资源")
            
            return result
            
        except Exception as e:
            logger.error(f"媒体本地化失败: {e}", exc_info=True)
            return html_content
    
    def _collect_urls(self, soup: BeautifulSoup) -> Set[str]:
        urls = set()
        
        for tag_name, attrs in self.MEDIA_TAGS_ATTRS.items():
            for tag in soup.find_all(tag_name):
                for attr in attrs:
                    if tag.has_attr(attr):
                        original_value = tag[attr]
                        if attr in ['srcset', 'data-srcset']:
                            urls.update(self._extract_srcset_urls(original_value))
                        else:
                            url = self._normalize_and_validate(original_value)
                            if url:
                                urls.add(url)
        
        for tag in soup.find_all(style=True):
            urls.update(self._extract_css_urls(tag['style']))
        
        for style_tag in soup.find_all('style'):
            if style_tag.string:
                urls.update(self._extract_css_urls(style_tag.string))
        
        return urls
    
    def _extract_srcset_urls(self, srcset: str) -> Set[str]:
        urls = set()
        if not srcset:
            return urls
        
        for item in srcset.split(','):
            item = item.strip()
            if not item:
                continue
            tokens = item.split()
            if tokens:
                url = self._normalize_and_validate(tokens[0])
                if url:
                    urls.add(url)
        
        return urls
    
    def _extract_css_urls(self, css_content: str) -> Set[str]:
        urls = set()
        if not css_content:
            return urls
        
        url_pattern = r'url\s*\(\s*(["\']?)([^"\'()]+)\1\s*\)'
        for match in re.finditer(url_pattern, css_content, flags=re.IGNORECASE):
            url = self._normalize_and_validate(match.group(2).strip())
            if url:
                urls.add(url)
        
        return urls
    
    def _normalize_and_validate(self, url: str) -> str | None:
        if not url or not isinstance(url, str):
            return None
        
        url = url.strip()
        if not url:
            return None
        
        if url in self.url_mapping or url in self.processed_urls:
            return None
        
        absolute_url = self._normalize_url(url)
        if not absolute_url:
            self.processed_urls.add(url)
            return None
        
        if not MediaDownloader.is_valid_url(absolute_url):
            self.processed_urls.add(url)
            return None
        
        return absolute_url
    
    def _download_urls_parallel(self, urls: Set[str], heartbeat_callback: Callable[[], None] | None = None):
        if not urls:
            return
        
        def download_and_upload(url: str) -> tuple[str, str | None]:
            downloader = MediaDownloader(referer=self.base_url, download_size_limit=self.download_size_limit)
            try:
                download_result = downloader.download(url)
                
                if download_result is None:
                    return url, None
                
                content, file_hash, content_type = download_result
                cos_url = self.uploader.upload_file(content, file_hash, content_type)
                
                if cos_url:
                    logger.debug(f"资源本地化成功: {url} -> {cos_url}")
                    return url, cos_url
                else:
                    return url, None
            except Exception as e:
                logger.warning(f"下载上传失败: {url} - {e}")
                return url, None
            finally:
                downloader.close()
        
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            futures = {executor.submit(download_and_upload, url): url for url in urls}
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
                        original_url, cos_url = future.result()
                        if cos_url:
                            self.url_mapping[original_url] = cos_url
                        else:
                            self.processed_urls.add(original_url)
                    except Exception as e:
                        url = futures[future]
                        logger.warning(f"处理下载结果失败: {url} - {e}")
                        self.processed_urls.add(url)
    
    def _apply_url_mapping(self, soup: BeautifulSoup):
        for tag_name, attrs in self.MEDIA_TAGS_ATTRS.items():
            for tag in soup.find_all(tag_name):
                for attr in attrs:
                    if tag.has_attr(attr):
                        original_value = tag[attr]
                        
                        if attr in ['srcset', 'data-srcset']:
                            new_value = self._replace_srcset_urls(original_value)
                        else:
                            new_value = self._replace_single_url(original_value)
                        
                        if new_value != original_value:
                            tag[attr] = new_value
        
        for tag in soup.find_all(style=True):
            original_style = tag['style']
            new_style = self._replace_css_urls(original_style)
            if new_style != original_style:
                tag['style'] = new_style
        
        for style_tag in soup.find_all('style'):
            if style_tag.string:
                original_css = style_tag.string
                new_css = self._replace_css_urls(original_css)
                if new_css != original_css:
                    style_tag.string = new_css
    
    def _replace_single_url(self, url: str) -> str:
        if not url or not isinstance(url, str):
            return url
        
        url = url.strip()
        if not url:
            return url
        
        if url in self.url_mapping:
            return self.url_mapping[url]
        
        absolute_url = self._normalize_url(url)
        if absolute_url and absolute_url in self.url_mapping:
            return self.url_mapping[absolute_url]
        
        return url
    
    def _replace_srcset_urls(self, srcset: str) -> str:
        if not srcset:
            return srcset
        
        parts = []
        for item in srcset.split(','):
            item = item.strip()
            if not item:
                continue
            
            tokens = item.split()
            if tokens:
                url = tokens[0]
                new_url = self._replace_single_url(url)
                tokens[0] = new_url
                parts.append(' '.join(tokens))
        
        return ', '.join(parts)
    
    def _replace_css_urls(self, css_content: str) -> str:
        if not css_content:
            return css_content
        
        url_pattern = r'url\s*\(\s*(["\']?)([^"\'()]+)\1\s*\)'
        
        def replace_url(match):
            quote = match.group(1)
            url = match.group(2).strip()
            new_url = self._replace_single_url(url)
            return f'url({quote}{new_url}{quote})'
        
        return re.sub(url_pattern, replace_url, css_content, flags=re.IGNORECASE)
    
    def _normalize_url(self, url: str) -> str | None:
        url = url.strip()
        
        if not url:
            return None
        
        try:
            parsed = urlparse(url)
            if parsed.scheme in ['http', 'https']:
                return url
            
            if not parsed.scheme:
                if self.base_url:
                    return urljoin(self.base_url, url)
                else:
                    logger.debug(f"相对URL但未提供base_url，跳过: {url}")
                    return None
            
            return None
        except Exception as e:
            logger.debug(f"URL规范化失败: {url} - {e}")
            return None
