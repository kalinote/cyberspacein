import logging
from fastapi import APIRouter, Body, HTTPException

from app.schemas.embedding import (
    BatchEmbeddingRequestSchema,
    BatchEmbeddingResponseSchema,
    BatchEmbeddingItemResponseSchema,
    EmbeddingResponseSchema,
)
from app.schemas.response import ApiResponseSchema
from app.utils.embedding import normalize_whitespace, get_embeddings_client

logger = logging.getLogger(__name__)
logging.getLogger("httpx").setLevel(logging.DEBUG)

router = APIRouter(
    prefix="/embedding",
    tags=["嵌入词向量"],
)


@router.post("", response_model=ApiResponseSchema[EmbeddingResponseSchema], summary="获取文本向量")
async def embed_text(text: str = Body(embed=True)):
    text = normalize_whitespace(text)
    embeddings = get_embeddings_client()
    try:
        vector = await embeddings.aembed_query(text)
        return ApiResponseSchema.success(data=EmbeddingResponseSchema(
            vector=vector
        ))
    except Exception as e:
        logger.error(f"嵌入服务调用失败: {e!s}", exc_info=True)
        raise HTTPException(status_code=502, detail=f"嵌入服务调用失败: {e!s}")


@router.post("/batch", response_model=ApiResponseSchema[BatchEmbeddingResponseSchema], summary="批量获取文本向量")
async def embed_batch(body: BatchEmbeddingRequestSchema):
    if not body.datas:
        return ApiResponseSchema.success(data=BatchEmbeddingResponseSchema(datas=[]))
    embeddings = get_embeddings_client()
    texts = [normalize_whitespace(item.text) for item in body.datas]
    uuids = [item.uuid for item in body.datas]
    try:
        vectors = await embeddings.aembed_documents(texts)
        result_datas = [
            BatchEmbeddingItemResponseSchema(uuid=uid, vector=vec)
            for uid, vec in zip(uuids, vectors)
        ]
        return ApiResponseSchema.success(data=BatchEmbeddingResponseSchema(datas=result_datas))
    except Exception as e:
        logger.error(f"批量嵌入服务调用失败: {e!s}", exc_info=True)
        raise HTTPException(status_code=502, detail=f"嵌入服务调用失败: {e!s}")