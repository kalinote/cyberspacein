import logging
import aiohttp
from typing import Optional, Dict
from app.core.config import settings

logger = logging.getLogger(__name__)


def unwrap_response(resp):
    """外部服务统一包裹 { code, message, data }，返回 data；无 data 时返回原 resp 兼容。"""
    if not isinstance(resp, dict) or "data" not in resp:
        return resp
    return resp["data"]


async def async_get(url: str, params: dict = None, **kwargs):
    async with aiohttp.ClientSession() as session:
        async with session.get(url, params=params, **kwargs) as response:
            return await response.json()
        
async def async_post(url: str, data: dict = None, **kwargs):
    async with aiohttp.ClientSession() as session:
        async with session.post(url, json=data, **kwargs) as response:
            return await response.json()


async def async_download_file(
    url: str,
    timeout: int = 30,
    headers: Dict[str, str] | None = None,
    use_proxy: bool | None = None
) -> bytes:
    """
    异步下载文件并返回字节数据
    
    Args:
        url: 文件URL
        timeout: 超时时间（秒）
        headers: 自定义请求头
        use_proxy: 是否使用代理，None时使用配置
    
    Returns:
        文件字节数据
    """
    should_use_proxy = use_proxy if use_proxy is not None else settings.USE_PROXY
    proxy = settings.OUT_SERVICE_PROXY if should_use_proxy else None
    
    
    
    default_headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
        
    }
    if headers:
        default_headers.update(headers)
    
    timeout_obj = aiohttp.ClientTimeout(total=timeout)
    
    try:
        async with aiohttp.ClientSession(timeout=timeout_obj) as session:
            async with session.get(url, headers=default_headers, proxy=proxy) as response:
                response.raise_for_status()
                content = await response.read()
                logger.info(f"文件下载成功: {url}, 大小: {len(content)} 字节")
                return content
    except aiohttp.ClientError as e:
        logger.error(f"下载文件失败 {url}: {e}")
        raise
    except Exception as e:
        logger.error(f"下载文件时发生未知错误 {url}: {e}")
        raise
        