import os
import logging
import llama_cpp
from typing import List, Optional
from dotenv import load_dotenv
from llama_cpp import Llama


load_dotenv()

logger = logging.getLogger(__name__)


class EmbeddingModel:
    """文本嵌入模型封装类"""
    
    _instance: Optional['EmbeddingModel'] = None
    _model: Optional[Llama] = None
    _initialized: bool = False
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self):
        if not EmbeddingModel._initialized:
            self._load_model()
            EmbeddingModel._initialized = True
    
    def _load_model(self):
        """加载嵌入模型"""
        if EmbeddingModel._model is not None:
            return
        
        model_path = os.getenv('MODEL_PATH')
        if not model_path:
            raise ValueError("未配置 MODEL_PATH 环境变量")
        
        if not os.path.exists(model_path):
            raise FileNotFoundError(f"模型文件不存在: {model_path}")
        
        try:
            logger.info(f"正在加载模型: {model_path}")
            EmbeddingModel._model = Llama(
                model_path=model_path,
                embedding=True,
                n_ctx=8192,
                verbose=False,
                pooling_type=llama_cpp.LLAMA_POOLING_TYPE_LAST
            )
            logger.info("模型加载成功")
        except Exception as e:
            logger.error(f"模型加载失败: {e}")
            raise
    
    def embed(self, text: str, prefix: str | None = None) -> List[float]:
        """生成文本嵌入向量
        
        Args:
            text: 输入文本
            
        Returns:
            嵌入向量列表
        """
        if not text or not text.strip():
            embedding_dim = int(os.getenv('EMBEDDING_DIM', '2560'))
            return [0.0] * embedding_dim
        
        if EmbeddingModel._model is None:
            self._load_model()
        
        try:
            result = EmbeddingModel._model.create_embedding(prefix + text if prefix else text)
            if result and 'data' in result and len(result['data']) > 0:
                embedding = result['data'][0]['embedding']
                return embedding
            else:
                raise ValueError("模型返回的嵌入结果为空")
        except Exception as e:
            logger.error(f"生成嵌入向量失败: {e}")
            raise

_model_instance: Optional[EmbeddingModel] = None


def initialize_model() -> EmbeddingModel:
    """初始化嵌入模型（在程序启动时调用）
    
    Returns:
        嵌入模型实例
        
    Raises:
        ValueError: 模型配置错误
        FileNotFoundError: 模型文件不存在
    """
    global _model_instance
    if _model_instance is None:
        _model_instance = EmbeddingModel()
    return _model_instance


def get_embedding(text: str, prefix: str | None = None) -> List[float]:
    """获取文本嵌入向量的便捷函数
    
    Args:
        text: 输入文本
        
    Returns:
        嵌入向量列表
        
    Raises:
        RuntimeError: 模型未初始化
    """
    global _model_instance
    if _model_instance is None:
        raise RuntimeError("模型未初始化，请先调用 initialize_model()")
    return _model_instance.embed(text, prefix)
