import os
import logging
from typing import List, Optional
from dotenv import load_dotenv
import requests


load_dotenv()

logger = logging.getLogger(__name__)


def get_embedding(text: str, prefix: str | None = None) -> List[float]:
    """获取文本嵌入向量的便捷函数
    
    Args:
        text: 输入文本
        prefix: 文本前缀（可选）
        
    Returns:
        嵌入向量列表
        
    Raises:
        ValueError: 接口返回错误
        RuntimeError: 接口调用失败
    """
    if not text or not text.strip():
        logger.warning("输入文本为空，返回空列表")
        return []
    
    base_url = os.getenv('ML_SERVICE_BASE_URL')
    if not base_url:
        raise ValueError("未配置 ML_SERVICE_BASE_URL 环境变量")
    
    url = f"{base_url.rstrip('/')}/api/v1/embedding"
    
    full_text = prefix + text if prefix else text
    
    try:
        response = requests.post(
            url,
            json={"text": full_text},
            headers={"Content-Type": "application/json"},
            timeout=30
        )
        response.raise_for_status()
        
        result = response.json()
        
        if result.get("code") != 0:
            error_message = result.get("message", "未知错误")
            raise ValueError(f"接口返回错误: {error_message}")
        
        data = result.get("data")
        if not data:
            raise ValueError("接口返回数据为空")
        
        embedding = data.get("embedding")
        if not embedding:
            raise ValueError("接口返回的嵌入向量为空")
        
        if not isinstance(embedding, list):
            raise ValueError("接口返回的嵌入向量格式错误")
        
        return embedding
        
    except requests.exceptions.RequestException as e:
        logger.error(f"HTTP请求失败: {e}")
        raise RuntimeError(f"调用嵌入接口失败: {str(e)}")
    except ValueError as e:
        logger.error(f"解析接口响应失败: {e}")
        raise
    except Exception as e:
        logger.error(f"获取嵌入向量失败: {e}")
        raise RuntimeError(f"获取嵌入向量失败: {str(e)}")
