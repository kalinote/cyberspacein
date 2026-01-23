import logging
import json
import uuid
from datetime import datetime
from typing import Optional, List
from app.core.config import settings
from app.service.ml.base import BaseMLService
from app.service.ml.generic import generic_service
from app.schemas.keywords import KeywordsTaskStatus, KeywordsStatusResponse
from app.db import get_redis

logger = logging.getLogger(__name__)


class KeywordsService(BaseMLService):
    _instance: Optional['KeywordsService'] = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    async def initialize(self) -> None:
        if not generic_service.is_model_ready():
            logger.warning("通用模型服务未初始化或模型未加载，关键词提取功能将不可用")
            return
        
        if not generic_service.is_executor_ready():
            logger.warning("通用模型服务线程池未初始化，关键词提取功能将不可用")
            return
        
        logger.info("关键词提取服务初始化成功")

    async def cleanup(self) -> None:
        logger.info("关键词提取服务已清理")

    def _ensure_available(self) -> None:
        """检查服务是否可用"""
        if not generic_service.is_model_ready():
            raise RuntimeError("通用模型未初始化，请先配置 GENERIC_MODEL_PATH 并调用 initialize()")
        if not generic_service.is_executor_ready():
            raise RuntimeError("通用模型线程池未初始化，请先调用 initialize()")
    
    def is_available(self) -> bool:
        """检查服务是否可用"""
        return generic_service.is_model_ready() and generic_service.is_executor_ready()
    
    def _build_keywords_schema(self) -> dict:
        """构建关键词提取的JSON Schema"""
        return {
            "type": "object",
            "properties": {
                "keywords": {
                    "type": "array",
                    "items": {"type": "string"},
                    "minItems": 5,
                    "maxItems": 10
                }
            },
            "required": ["keywords"]
        }
    
    def _build_keywords_messages(self, text: str) -> list:
        """构建关键词提取的消息列表"""
        return [
            {
                "role": "system",
                "content": "你是一位专业的内容编辑和 SEO 专家。"
            },
            {
                "role": "user",
                "content": f"/think 请阅读下文，并从中提取 5-10 个关键词。 要求：\n\n关键词必须能概括文章的核心主题。\n\n优先选择专有名词、技术术语或具有代表性的动名词。\n\n排除"文章"、"方法"、"重要性"等无实际意义的泛泛之词。\n\n按重要性从高到低排列。 输出 JSON 格式。\n\n{text}"
            }
        ]
    
    def _parse_keywords_result(self, result_json: str) -> List[str]:
        """解析关键词提取结果"""
        try:
            result_data = json.loads(result_json)
        except json.JSONDecodeError as e:
            logger.error(f"JSON 解析失败，原始响应: {result_json}", exc_info=True)
            raise ValueError(f"无法解析模型返回的 JSON 格式: {e}") from e
        
        if "keywords" not in result_data:
            logger.error(f"JSON 中缺少 keywords 字段，解析结果: {result_data}")
            raise ValueError("模型返回的 JSON 中缺少 keywords 字段")
        
        keywords = result_data["keywords"]
        if not isinstance(keywords, list):
            raise ValueError("keywords 字段必须是数组")
        
        return keywords
    
    async def extract_keywords_in_executor(self, text: str) -> List[str]:
        """在线程池中执行关键词提取任务"""
        if not text or not text.strip():
            return []
        
        self._ensure_available()
        
        json_schema = self._build_keywords_schema()
        messages = self._build_keywords_messages(text)
        
        result_json = await generic_service.inference_in_executor(
            json_schema=json_schema,
            messages=messages,
            max_tokens=2048,
            temperature=0.1
        )
        
        return self._parse_keywords_result(result_json)

    def extract_keywords(self, text: str) -> List[str]:
        """同步提取关键词（用于内部调用，API端点使用异步方法）"""
        if not text or not text.strip():
            return []
        
        self._ensure_available()
        
        json_schema = self._build_keywords_schema()
        messages = self._build_keywords_messages(text)
        
        result_json = generic_service.inference(
            json_schema=json_schema,
            messages=messages,
            max_tokens=2048,
            temperature=0.1
        )
        
        return self._parse_keywords_result(result_json)

    def _get_task_key(self, token: str) -> str:
        """获取任务Redis key"""
        return f"keywords:task:{token}"

    async def _save_task_status(self, token: str, status: KeywordsTaskStatus, result: List[str] = None, error: str = None):
        """保存任务状态到Redis"""
        redis_client = get_redis()
        if not redis_client:
            logger.warning("Redis未连接，无法保存任务状态")
            return
        
        try:
            key = self._get_task_key(token)
            existing_data = await redis_client.get(key)
            
            task_data = {
                "status": status.value,
                "result": result,
                "error": error,
                "updated_at": datetime.now().isoformat()
            }
            
            if existing_data:
                existing = json.loads(existing_data)
                if "created_at" in existing:
                    task_data["created_at"] = existing["created_at"]
            else:
                task_data["created_at"] = datetime.now().isoformat()
            
            ttl = settings.KEYWORDS_RESULT_TTL
            await redis_client.setex(key, ttl, json.dumps(task_data, ensure_ascii=False))
        except Exception as e:
            logger.error(f"保存任务状态失败: {e}", exc_info=True)

    async def _get_task_status(self, token: str) -> Optional[dict]:
        """从Redis获取任务状态"""
        redis_client = get_redis()
        if not redis_client:
            return None
        
        try:
            key = self._get_task_key(token)
            data = await redis_client.get(key)
            if data:
                return json.loads(data)
            return None
        except Exception as e:
            logger.error(f"获取任务状态失败: {e}", exc_info=True)
            return None

    async def create_task(self, text: str) -> str:
        """创建异步关键词提取任务，返回token"""
        redis_client = get_redis()
        if not redis_client:
            raise RuntimeError("Redis未连接，异步关键词提取功能不可用")
        
        token = str(uuid.uuid4())
        
        task_data = {
            "status": KeywordsTaskStatus.pending.value,
            "result": None,
            "error": None,
            "created_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat()
        }
        
        key = self._get_task_key(token)
        ttl = settings.KEYWORDS_RESULT_TTL
        
        await redis_client.setex(key, ttl, json.dumps(task_data, ensure_ascii=False))
        logger.info(f"已创建关键词提取任务: {token}")
        
        return token

    async def extract_keywords_async(self, token: str, text: str):
        """异步执行关键词提取任务"""
        try:
            await self._save_task_status(token, KeywordsTaskStatus.processing)
            
            keywords = await self.extract_keywords_in_executor(text)
            
            await self._save_task_status(token, KeywordsTaskStatus.completed, result=keywords)
            logger.info(f"关键词提取任务完成: {token}")
        except Exception as e:
            error_msg = str(e)
            logger.error(f"关键词提取任务失败: {token}, 错误: {error_msg}", exc_info=True)
            await self._save_task_status(token, KeywordsTaskStatus.failed, error=error_msg)

    async def get_task_status(self, token: str) -> KeywordsStatusResponse:
        """获取任务状态"""
        task_data = await self._get_task_status(token)
        
        if not task_data:
            raise ValueError("任务不存在或已过期")
        
        status = KeywordsTaskStatus(task_data.get("status", "pending"))
        result = task_data.get("result")
        error = task_data.get("error")
        
        return KeywordsStatusResponse(
            status=status,
            keywords=result,
            error=error
        )


keywords_service = KeywordsService()
