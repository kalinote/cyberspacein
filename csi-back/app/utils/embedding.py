import re
import httpx
from fastapi import HTTPException
from typing import Optional

from langchain_openai import OpenAIEmbeddings

from app.core.config import settings
from app.utils.network import log_http_error_response_async

_async_http_client: Optional[httpx.AsyncClient] = None
_embeddings_client: Optional[OpenAIEmbeddings] = None


async def init_embedding_client():
    global _async_http_client, _embeddings_client
    
    url = (settings.EMBEDDING_MODEL_URL or "").rstrip("/")
    base_url = url[: -len("/embeddings")].rstrip("/") if url.endswith("/embeddings") else url
    
    if not base_url or not settings.EMBEDDING_MODEL_API_KEY:
        raise ValueError("嵌入服务未配置：缺少 EMBEDDING_MODEL_URL 或 EMBEDDING_MODEL_API_KEY")
    
    _async_http_client = httpx.AsyncClient(
        event_hooks={"response": [log_http_error_response_async]},
        timeout=90.0,
        limits=httpx.Limits(max_keepalive_connections=20, max_connections=100)
    )
    
    _embeddings_client = OpenAIEmbeddings(
        model=settings.EMBEDDING_MODEL,
        openai_api_key=settings.EMBEDDING_MODEL_API_KEY,
        openai_api_base=base_url,
        max_retries=3,
        request_timeout=90,
        http_async_client=_async_http_client
    )


async def close_embedding_client():
    global _async_http_client, _embeddings_client
    if _async_http_client:
        await _async_http_client.aclose()
        _async_http_client = None
    _embeddings_client = None


def normalize_whitespace(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "").strip())


async def embed_query_async(text: str, instruct: str = "") -> list[float]:
    text = normalize_whitespace(text)
    embeddings = get_embeddings_client()
    query_text = f"Instruct: {instruct}\nQuery:{text}" if instruct else text
    return await embeddings.aembed_query(query_text)


def get_embeddings_client() -> OpenAIEmbeddings:
    if _embeddings_client is None:
        raise HTTPException(status_code=503, detail="嵌入服务未初始化")
    return _embeddings_client
