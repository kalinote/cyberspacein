import logging
from fastapi import APIRouter
from app.schemas.embedding import (
    EmbeddingRequest,
    EmbeddingResponse,
    EmbeddingBatchRequest,
    EmbeddingBatchResponse
)
from app.service.ml.embedding import embedding_service
from app.core.exceptions import InternalServerException

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/embedding",
    tags=["嵌入向量"],
)


@router.post("", response_model=EmbeddingResponse, summary="计算文本嵌入向量")
async def compute_embedding(request: EmbeddingRequest):
    """
    计算文本的嵌入向量（同步接口）
    
    - **text**: 待计算嵌入向量的文本内容（无字数限制）
    - 返回文本的嵌入向量列表
    """
    try:
        embedding = embedding_service.embed(request.text)
        return EmbeddingResponse(embedding=embedding)
    except Exception as e:
        logger.error(f"计算嵌入向量失败: {e}", exc_info=True)
        raise InternalServerException(message=f"计算嵌入向量失败: {str(e)}")


@router.post("/batch", response_model=EmbeddingBatchResponse, summary="批量计算文本嵌入向量")
async def compute_embedding_batch(request: EmbeddingBatchRequest):
    """
    批量计算文本的嵌入向量（同步接口）
    
    - **datas**: 批量数据列表，每个数据项包含 uuid 和 text
    - 返回批量处理结果，每个结果包含 uuid、embedding 和可选的 error
    - 单个项目失败不影响其他项目的处理
    """
    try:
        results = await embedding_service.embed_batch(request.datas)
        return EmbeddingBatchResponse(results=results)
    except Exception as e:
        logger.error(f"批量计算嵌入向量失败: {e}", exc_info=True)
        raise InternalServerException(message=f"批量计算嵌入向量失败: {str(e)}")
