import os
import hashlib
import logging
from typing import Optional, Tuple
import requests
from urllib.parse import urlparse
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)


class MediaDownloader:
    
    DEFAULT_HEADERS = {
        "accept-language": "zh-CN,zh;q=0.9,en;q=0.8",
        "priority": "u=2, i",
        "sec-ch-ua": "\"Google Chrome\";v=\"143\", \"Chromium\";v=\"143\", \"Not A(Brand\";v=\"24\"",
        "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/143.0.0.0 Safari/537.36"
    }
    
    def __init__(self, timeout: int = 10, max_retries: int = 2, referer: Optional[str] = None):
        self.timeout = timeout
        self.max_retries = max_retries
        self.referer = referer
        self.session = requests.Session()
        self.session.headers.update(self.DEFAULT_HEADERS)
        
        proxy = os.getenv('DOWNLOAD_PROXY')
        if proxy:
            self.session.proxies = {
                'http': proxy,
                'https': proxy
            }
            logger.info(f"使用代理进行下载: {proxy}")
    
    def is_valid_url(self, url: str) -> bool:
        if not url or not isinstance(url, str):
            return False
        
        url_lower = url.lower().strip()
        
        invalid_schemes = ['javascript:', 'data:', 'vbscript:', 'file:', 'blob:', 'about:']
        for scheme in invalid_schemes:
            if url_lower.startswith(scheme):
                return False
        
        try:
            parsed = urlparse(url)
            return parsed.scheme in ['http', 'https'] and bool(parsed.netloc)
        except Exception:
            return False
    
    def download(self, url: str) -> Optional[Tuple[bytes, str, str]]:
        if not self.is_valid_url(url):
            logger.debug(f"无效的URL，跳过下载: {url}")
            return None
        
        headers = {}
        referer = self.referer
        if not referer:
            try:
                parsed = urlparse(url)
                if parsed.scheme and parsed.netloc:
                    referer = f"{parsed.scheme}://{parsed.netloc}/"
            except Exception:
                pass
        
        if referer:
            headers['Referer'] = referer
        
        last_exception = None
        for attempt in range(self.max_retries + 1):
            try:
                response = self.session.get(url, headers=headers, timeout=self.timeout, stream=True)
                response.raise_for_status()
                
                content = response.content
                content_type = response.headers.get('Content-Type', '').split(';')[0].strip()
                
                file_hash = self.calculate_sha256(content)
                
                logger.debug(f"文件下载成功: {url} (SHA256: {file_hash})")
                return content, file_hash, content_type
                
            except requests.exceptions.Timeout:
                last_exception = f"下载超时"
                logger.warning(f"下载超时 (尝试 {attempt + 1}/{self.max_retries + 1}): {url}")
            except requests.exceptions.ConnectionError as e:
                last_exception = f"连接错误: {str(e)}"
                logger.warning(f"连接错误 (尝试 {attempt + 1}/{self.max_retries + 1}): {url}")
            except requests.exceptions.HTTPError as e:
                last_exception = f"HTTP错误: {e.response.status_code}"
                logger.warning(f"HTTP错误 {e.response.status_code} (尝试 {attempt + 1}/{self.max_retries + 1}): {url}")
                if e.response.status_code in [404, 403, 410]:
                    break
            except requests.exceptions.RequestException as e:
                last_exception = f"请求异常: {str(e)}"
                logger.warning(f"请求异常 (尝试 {attempt + 1}/{self.max_retries + 1}): {url} - {e}")
            except Exception as e:
                last_exception = f"未知错误: {str(e)}"
                logger.error(f"下载文件时发生未知错误: {url} - {e}")
                break
        
        logger.warning(f"下载失败，已重试 {self.max_retries} 次: {url} ({last_exception})")
        return None
    
    @staticmethod
    def calculate_sha256(content: bytes) -> str:
        return hashlib.sha256(content).hexdigest()
    
    def close(self):
        self.session.close()
