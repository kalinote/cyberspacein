import logging
import os
import llama_cpp
from typing import Optional, List
from llama_cpp import Llama
from app.core.config import settings
from app.service.ml.base import BaseMLService
from app.schemas.embedding import EmbeddingBatchItem, EmbeddingBatchItemResponse

logger = logging.getLogger(__name__)


class EmbeddingService(BaseMLService):
    _instance: Optional['EmbeddingService'] = None
    _model: Optional[Llama] = None
    _initialized: bool = False

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    async def initialize(self) -> None:
        if EmbeddingService._initialized:
            logger.info("嵌入模型已初始化")
            return

        if not settings.EMBEDDING_MODEL_PATH:
            logger.warning("EMBEDDING_MODEL_PATH 未配置，嵌入功能将不可用")
            return

        if EmbeddingService._model is not None:
            logger.info("嵌入模型已加载")
            return

        try:
            model_path = settings.EMBEDDING_MODEL_PATH
            if not os.path.exists(model_path):
                raise FileNotFoundError(f"模型文件不存在: {model_path}")

            logger.info(f"正在加载嵌入模型: {model_path}")
            EmbeddingService._model = Llama(
                model_path=model_path,
                embedding=True,
                n_ctx=8192,
                verbose=False,
                pooling_type=llama_cpp.LLAMA_POOLING_TYPE_LAST
            )
            EmbeddingService._initialized = True
            logger.info("嵌入模型加载成功")
        except Exception as e:
            logger.error(f"嵌入模型加载失败: {e}", exc_info=True)
            raise

    async def cleanup(self) -> None:
        EmbeddingService._model = None
        EmbeddingService._initialized = False
        logger.info("嵌入模型已清理")

    def _ensure_available(self) -> None:
        if not EmbeddingService._initialized:
            raise RuntimeError("嵌入模型未初始化，请先配置 EMBEDDING_MODEL_PATH 并调用 initialize()")
        if EmbeddingService._model is None:
            raise RuntimeError("嵌入模型未加载，请先调用 initialize()")

    def is_available(self) -> bool:
        return EmbeddingService._initialized and EmbeddingService._model is not None

    def embed(self, text: str, prefix: str | None = None) -> List[float]:
        if not text or not text.strip():
            embedding_dim = settings.EMBEDDING_DIM
            return [0.0] * embedding_dim

        self._ensure_available()

        try:
            input_text = prefix + text if prefix else text
            result = EmbeddingService._model.create_embedding(input_text)
            if result and 'data' in result and len(result['data']) > 0:
                embedding = result['data'][0]['embedding']
                return embedding
            else:
                raise ValueError("模型返回的嵌入结果为空")
        except Exception as e:
            logger.error(f"生成嵌入向量失败: {e}", exc_info=True)
            raise

    async def embed_batch(self, items: List[EmbeddingBatchItem]) -> List[EmbeddingBatchItemResponse]:
        self._ensure_available()
        
        results = []
        for item in items:
            try:
                embedding = self.embed(item.text)
                results.append(EmbeddingBatchItemResponse(
                    uuid=item.uuid,
                    embedding=embedding,
                    error=None
                ))
            except Exception as e:
                error_msg = str(e)
                logger.error(f"处理数据项 {item.uuid} 失败: {error_msg}", exc_info=True)
                results.append(EmbeddingBatchItemResponse(
                    uuid=item.uuid,
                    embedding=None,
                    error=error_msg
                ))
        
        return results


embedding_service = EmbeddingService()
