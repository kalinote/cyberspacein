import os
import hashlib
import logging
import time
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
    
    def __init__(
        self,
        connect_timeout: float = 10,
        read_timeout: float = 30,
        max_retries: int = 1,
        referer: str | None = None,
        download_size_limit: int | None = None,
    ):
        self.connect_timeout = max(float(connect_timeout), 0.1)
        self.read_timeout = max(float(read_timeout), 0.1)
        self.max_retries = max(int(max_retries), 0)
        self.referer = referer
        self.download_size_limit = download_size_limit
        self.session = requests.Session()
        self.session.headers.update(self.DEFAULT_HEADERS)
        
        proxy = os.getenv('DOWNLOAD_PROXY')
        if proxy:
            self.session.proxies = {
                'http': proxy,
                'https': proxy
            }
            logger.info(f"使用代理进行下载: {proxy}")
    
    @staticmethod
    def is_valid_url(url: str) -> bool:
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
    
    def _request_timeout(self, deadline: float | None) -> tuple[float, float] | None:
        """根据绝对截止时间计算本次请求可使用的连接和读取超时。"""
        if deadline is None:
            return self.connect_timeout, self.read_timeout
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            return None
        return min(self.connect_timeout, remaining), min(self.read_timeout, remaining)

    def check_file_size(self, url: str, deadline: float | None = None) -> int | None:
        """通过HEAD请求检查文件大小，返回文件大小（字节），如果无法获取则返回None"""
        if not self.is_valid_url(url):
            return None

        request_timeout = self._request_timeout(deadline)
        if request_timeout is None:
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
        
        response = None
        try:
            response = self.session.head(
                url,
                headers=headers,
                timeout=request_timeout,
                allow_redirects=True,
            )
            response.raise_for_status()
            
            content_length = response.headers.get('Content-Length')
            if content_length:
                try:
                    size = int(content_length)
                    return size
                except (ValueError, TypeError):
                    logger.debug(f"无法解析Content-Length: {content_length}")
                    return None
            else:
                logger.debug(f"响应头中未包含Content-Length: {url}")
                return None
                
        except requests.exceptions.RequestException as e:
            logger.debug(f"HEAD请求失败，无法获取文件大小: {url} - {e}")
            return None
        except Exception as e:
            logger.debug(f"检查文件大小时发生错误: {url} - {e}")
            return None
        finally:
            if response is not None:
                response.close()
    
    def download(self, url: str, deadline: float | None = None) -> tuple[bytes, str, str] | None:
        if not self.is_valid_url(url):
            logger.debug(f"无效的URL，跳过下载: {url}")
            return None

        if deadline is not None and time.monotonic() >= deadline:
            logger.info(f"媒体处理预算已耗尽，跳过下载: {url}")
            return None
        
        if self.download_size_limit is not None:
            file_size = self.check_file_size(url, deadline=deadline)
            if file_size is not None and file_size > self.download_size_limit:
                logger.warning(f"文件大小 {file_size / (1024 * 1024):.2f}MB 超过限制 {self.download_size_limit / (1024 * 1024):.2f}MB，跳过下载: {url}")
                return None
            elif file_size is None:
                logger.debug(f"无法获取文件大小，继续尝试下载: {url}")
        
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
            request_timeout = self._request_timeout(deadline)
            if request_timeout is None:
                logger.info(f"媒体处理预算已耗尽，停止重试: {url}")
                break

            response = None
            try:
                response = self.session.get(
                    url,
                    headers=headers,
                    timeout=request_timeout,
                    stream=True,
                )
                response.raise_for_status()

                content_length = response.headers.get('Content-Length')
                if self.download_size_limit is not None and content_length:
                    try:
                        if int(content_length) > self.download_size_limit:
                            logger.warning(f"文件大小超过限制，跳过下载: {url}")
                            return None
                    except (ValueError, TypeError):
                        logger.debug(f"无法解析Content-Length: {content_length}")
                
                content_type = response.headers.get('Content-Type', '').split(';')[0].strip()
                
                chunks = []
                downloaded_size = 0
                chunk_size = 8192
                
                for chunk in response.iter_content(chunk_size=chunk_size):
                    if deadline is not None and time.monotonic() >= deadline:
                        logger.info(f"媒体处理预算已耗尽，中止下载: {url}")
                        return None
                    if chunk:
                        chunks.append(chunk)
                        downloaded_size += len(chunk)
                        if self.download_size_limit is not None and downloaded_size > self.download_size_limit:
                            logger.warning(f"下载大小 {downloaded_size / (1024 * 1024):.2f}MB 超过限制，中止下载: {url}")
                            response.close()
                            return None
                
                content = b''.join(chunks)
                file_hash = self.calculate_sha256(content)
                
                logger.debug(f"文件下载成功: {url} (大小: {len(content) / 1024:.1f}KB, SHA256: {file_hash})")
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
            finally:
                if response is not None:
                    response.close()
        
        logger.warning(f"下载失败，已重试 {self.max_retries} 次: {url} ({last_exception})")
        return None
    
    @staticmethod
    def calculate_sha256(content: bytes) -> str:
        return hashlib.sha256(content).hexdigest()
    
    def close(self):
        self.session.close()
