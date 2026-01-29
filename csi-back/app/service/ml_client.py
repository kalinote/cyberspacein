import logging
import asyncio
from typing import Any, Awaitable, Callable, Optional

from app.core.config import settings
from app.utils.async_fetch import async_get, async_post, unwrap_response

logger = logging.getLogger(__name__)


def _base_url() -> str:
    url = (settings.ML_SERVICE_BASE_URL or "").rstrip("/")
    if not url:
        raise ValueError("ML_SERVICE_BASE_URL 未配置")
    return url


async def extract_text(html: str) -> str:
    resp = await async_post(f"{_base_url()}/api/v1/html-analyze/extract-text", data={"html": html})
    data = unwrap_response(resp) or {}
    return data.get("text") or ""


async def clean_html(html: str) -> str:
    resp = await async_post(f"{_base_url()}/api/v1/html-analyze/clean", data={"html": html})
    data = unwrap_response(resp) or {}
    return data.get("html") or ""


async def detect_language(text: str) -> Optional[str]:
    resp = await async_post(f"{_base_url()}/api/v1/language/detect", data={"text": text})
    data = unwrap_response(resp) or {}
    result = data.get("result")
    if result is None:
        return None
    return result.get("iso_code_639_3")


async def translate_async(text: str, target_lang: str = "中文") -> str:
    resp = await async_post(
        f"{_base_url()}/api/v1/translate/async",
        data={"text": text, "target_lang": target_lang},
    )
    data = unwrap_response(resp) or {}
    return data.get("token") or ""


async def translate_status(token: str) -> dict:
    resp = await async_get(f"{_base_url()}/api/v1/translate/status/{token}")
    data = unwrap_response(resp)
    return data if isinstance(data, dict) else {}


async def keywords_async(text: str) -> str:
    resp = await async_post(f"{_base_url()}/api/v1/keywords/async", data={"text": text})
    data = unwrap_response(resp) or {}
    return data.get("token") or ""


async def keywords_status(token: str) -> dict:
    resp = await async_get(f"{_base_url()}/api/v1/keywords/status/{token}")
    data = unwrap_response(resp)
    return data if isinstance(data, dict) else {}


async def entities_async(text: str) -> str:
    resp = await async_post(f"{_base_url()}/api/v1/entities/async", data={"text": text})
    data = unwrap_response(resp) or {}
    return data.get("token") or ""


async def entities_status(token: str) -> dict:
    resp = await async_get(f"{_base_url()}/api/v1/entities/status/{token}")
    data = unwrap_response(resp)
    return data if isinstance(data, dict) else {}


async def poll_until_done(
    fetch_status: Callable[[], Awaitable[dict]],
    poll_interval: Optional[int] = None,
    poll_timeout: Optional[int] = None,
    on_status: Optional[Callable[[str], Any]] = None,
) -> tuple[str, Optional[dict]]:
    interval = poll_interval if poll_interval is not None else getattr(
        settings, "ML_ASYNC_POLL_INTERVAL", 3
    )
    timeout = poll_timeout if poll_timeout is not None else getattr(
        settings, "ML_ASYNC_POLL_TIMEOUT", 1800
    )
    elapsed = 0
    while elapsed < timeout:
        data = await fetch_status()
        status = (data or {}).get("status", "")
        if on_status:
            try:
                res = on_status(status)
                if asyncio.iscoroutine(res):
                    await res
            except Exception as e:
                logger.warning("轮询回调 on_status 执行失败: %s", e)
        if status == "completed":
            return "completed", data
        if status == "failed":
            return "failed", data
        await asyncio.sleep(interval)
        elapsed += interval
    return "timeout", None
