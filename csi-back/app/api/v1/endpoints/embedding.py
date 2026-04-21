from fastapi import APIRouter, Body
from loguru import logger

from app.schemas.embedding import (
    BatchEmbeddingRequestSchema,
    BatchEmbeddingResponseSchema,
    BatchEmbeddingItemResponseSchema,
    EmbeddingResponseSchema,
)
from app.schemas.response import ApiResponseSchema
import app.utils.status_codes as status_codes
from app.utils.embedding import normalize_whitespace, get_embeddings_client

logger = logger.bind(name=__name__)

router = APIRouter(
    prefix="/embedding",
    tags=["嵌入词向量"],
)


@router.post("", response_model=ApiResponseSchema[EmbeddingResponseSchema], summary="获取文本向量")
async def embed_text(text: str = Body(embed=True)):
    text = normalize_whitespace(text)
    try:
        embeddings = get_embeddings_client()
        vector = await embeddings.aembed_query(text)
        return ApiResponseSchema.success(data=EmbeddingResponseSchema(
            vector=vector
        ))
    except Exception as e:
        logger.exception(f"嵌入服务调用失败: {e!s}")
        if "未初始化" in str(e):
            return ApiResponseSchema.error(code=status_codes.EMBEDDING_NOT_READY, message=f"嵌入服务调用失败: {e!s}")
        return ApiResponseSchema.error(code=status_codes.EMBEDDING_CALL_FAILED, message=f"嵌入服务调用失败: {e!s}")


@router.post("/batch", response_model=ApiResponseSchema[BatchEmbeddingResponseSchema], summary="批量获取文本向量")
async def embed_batch(body: BatchEmbeddingRequestSchema):
    if not body.datas:
        return ApiResponseSchema.success(data=BatchEmbeddingResponseSchema(datas=[]))
    try:
        embeddings = get_embeddings_client()
        texts = [normalize_whitespace(item.text) for item in body.datas]
        uuids = [item.uuid for item in body.datas]
        vectors = await embeddings.aembed_documents(texts)
        result_datas = [
            BatchEmbeddingItemResponseSchema(uuid=uid, vector=vec)
            for uid, vec in zip(uuids, vectors)
        ]
        return ApiResponseSchema.success(data=BatchEmbeddingResponseSchema(datas=result_datas))
    except Exception as e:
        logger.exception(f"批量嵌入服务调用失败: {e!s}")
        if "未初始化" in str(e):
            return ApiResponseSchema.error(code=status_codes.EMBEDDING_NOT_READY, message=f"嵌入服务调用失败: {e!s}")
        return ApiResponseSchema.error(code=status_codes.EMBEDDING_CALL_FAILED, message=f"嵌入服务调用失败: {e!s}")