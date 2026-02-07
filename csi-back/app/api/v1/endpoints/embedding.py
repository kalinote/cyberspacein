import asyncio
import logging
from fastapi import APIRouter, Body, HTTPException

from langchain_openai import OpenAIEmbeddings

from app.core.config import settings
from app.schemas.embedding import (
    BatchEmbeddingRequestSchema,
    BatchEmbeddingResponseSchema,
    BatchEmbeddingItemResponseSchema,
    EmbeddingResponseSchema,
)
from app.schemas.response import ApiResponseSchema

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/embedding",
    tags=["嵌入词向量"],
)


@router.post("", response_model=ApiResponseSchema[EmbeddingResponseSchema], summary="获取文本向量")
async def embed_text(text: str = Body(embed=True)):
    embeddings = _get_embeddings_client()
    try:
        vector = await asyncio.to_thread(embeddings.embed_query, text)
        return ApiResponseSchema.success(data=EmbeddingResponseSchema(
            vector=vector
        ))
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"嵌入服务调用失败: {e!s}")


def _get_embeddings_client():
    url = (settings.EMBEDDING_MODEL_URL or "").rstrip("/")
    base_url = url[: -len("/embeddings")].rstrip("/") if url.endswith("/embeddings") else url
    if not base_url or not settings.EMBEDDING_MODEL_API_KEY:
        raise HTTPException(status_code=503, detail="嵌入服务未配置")
    return OpenAIEmbeddings(
        model=settings.EMBEDDING_MODEL,
        openai_api_key=settings.EMBEDDING_MODEL_API_KEY,
        openai_api_base=base_url,
        max_retries=3,
        request_timeout=90
    )


@router.post("/batch", response_model=ApiResponseSchema[BatchEmbeddingResponseSchema], summary="批量获取文本向量")
async def embed_batch(body: BatchEmbeddingRequestSchema):
    if not body.datas:
        return ApiResponseSchema.success(data=BatchEmbeddingResponseSchema(datas=[]))
    embeddings = _get_embeddings_client()
    texts = [item.text for item in body.datas]
    uuids = [item.uuid for item in body.datas]
    try:
        vectors = await asyncio.to_thread(embeddings.embed_documents, texts)
        result_datas = [
            BatchEmbeddingItemResponseSchema(uuid=uid, vector=vec)
            for uid, vec in zip(uuids, vectors)
        ]
        return ApiResponseSchema.success(data=BatchEmbeddingResponseSchema(datas=result_datas))
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"嵌入服务调用失败: {e!s}")