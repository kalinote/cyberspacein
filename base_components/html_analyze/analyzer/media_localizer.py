import logging
import re
from typing import Dict, Optional, Set
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse
from analyzer.media_downloader import MediaDownloader
from analyzer.cos_uploader import COSUploader

logger = logging.getLogger(__name__)


class MediaLocalizer:
    
    MEDIA_TAGS_ATTRS = {
        'img': ['src', 'srcset', 'data-src', 'data-srcset'],
        'video': ['src', 'poster', 'data-src', 'data-poster'],
        'audio': ['src', 'data-src'],
        'source': ['src', 'srcset', 'data-src', 'data-srcset'],
        'image': ['href', 'xlink:href'],
    }
    
    def __init__(self, base_url: Optional[str] = None):
        self.base_url = base_url
        self.downloader = MediaDownloader(referer=base_url)
        self.uploader = COSUploader()
        self.url_mapping: Dict[str, str] = {}
        self.processed_urls: Set[str] = set()
    
    def localize(self, html_content: str) -> str:
        if not self.uploader.is_configured():
            logger.warning("COS未配置，跳过媒体本地化")
            return html_content
        
        if not html_content:
            return html_content
        
        try:
            soup = BeautifulSoup(html_content, 'html.parser')
            
            self._process_html_tags(soup)
            
            self._process_style_attributes(soup)
            
            self._process_style_tags(soup)
            
            result = str(soup)
            
            if self.url_mapping:
                logger.info(f"媒体本地化完成: 成功处理 {len(self.url_mapping)} 个资源")
            
            return result
            
        except Exception as e:
            logger.error(f"媒体本地化失败: {e}", exc_info=True)
            return html_content
        finally:
            self.downloader.close()
    
    def _process_html_tags(self, soup: BeautifulSoup):
        for tag_name, attrs in self.MEDIA_TAGS_ATTRS.items():
            for tag in soup.find_all(tag_name):
                for attr in attrs:
                    if tag.has_attr(attr):
                        original_value = tag[attr]
                        
                        if attr in ['srcset', 'data-srcset']:
                            new_value = self._process_srcset(original_value)
                        else:
                            new_value = self._process_single_url(original_value)
                        
                        if new_value != original_value:
                            tag[attr] = new_value
    
    def _process_style_attributes(self, soup: BeautifulSoup):
        for tag in soup.find_all(style=True):
            original_style = tag['style']
            new_style = self._process_css_urls(original_style)
            if new_style != original_style:
                tag['style'] = new_style
    
    def _process_style_tags(self, soup: BeautifulSoup):
        for style_tag in soup.find_all('style'):
            if style_tag.string:
                original_css = style_tag.string
                new_css = self._process_css_urls(original_css)
                if new_css != original_css:
                    style_tag.string = new_css
    
    def _process_srcset(self, srcset: str) -> str:
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
                new_url = self._process_single_url(url)
                
                tokens[0] = new_url
                parts.append(' '.join(tokens))
        
        return ', '.join(parts)
    
    def _process_css_urls(self, css_content: str) -> str:
        if not css_content:
            return css_content
        
        url_pattern = r'url\s*\(\s*(["\']?)([^"\'()]+)\1\s*\)'
        
        def replace_url(match):
            quote = match.group(1)
            url = match.group(2).strip()
            
            new_url = self._process_single_url(url)
            
            return f'url({quote}{new_url}{quote})'
        
        return re.sub(url_pattern, replace_url, css_content, flags=re.IGNORECASE)
    
    def _process_single_url(self, url: str) -> str:
        if not url or not isinstance(url, str):
            return url
        
        url = url.strip()
        
        if not url:
            return url
        
        if url in self.url_mapping:
            return self.url_mapping[url]
        
        if url in self.processed_urls:
            return url
        
        absolute_url = self._normalize_url(url)
        
        if not absolute_url:
            self.processed_urls.add(url)
            return url
        
        if not self.downloader.is_valid_url(absolute_url):
            self.processed_urls.add(url)
            return url
        
        if absolute_url in self.url_mapping:
            new_url = self.url_mapping[absolute_url]
            self.url_mapping[url] = new_url
            return new_url
        
        download_result = self.downloader.download(absolute_url)
        
        if download_result is None:
            self.processed_urls.add(url)
            self.processed_urls.add(absolute_url)
            return url
        
        content, file_hash, content_type = download_result
        
        cos_url = self.uploader.upload_file(content, file_hash, content_type)
        
        if cos_url:
            self.url_mapping[url] = cos_url
            self.url_mapping[absolute_url] = cos_url
            logger.debug(f"资源本地化成功: {url} -> {cos_url}")
            return cos_url
        else:
            self.processed_urls.add(url)
            self.processed_urls.add(absolute_url)
            return url
    
    def _normalize_url(self, url: str) -> Optional[str]:
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
