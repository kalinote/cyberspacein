import logging
import os
import json
import uuid
from datetime import datetime
from typing import Optional
from llama_cpp import Llama
from app.core.config import settings
from app.service.ml.base import BaseMLService
from app.schemas.translate import TranslateTaskStatus, TranslateStatusResponse
from app.db import get_redis

logger = logging.getLogger(__name__)


class TranslateService(BaseMLService):
    _instance: Optional['TranslateService'] = None
    _llm: Optional[Llama] = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    async def initialize(self) -> None:
        if self._llm is not None:
            logger.info("翻译模型已初始化")
            return

        if not settings.TRANSLATE_MODEL_PATH:
            logger.warning("TRANSLATE_MODEL_PATH 未配置，翻译功能将不可用")
            return

        try:
            n_ctx = settings.TRANSLATE_N_CTX or 2048
            n_threads = settings.TRANSLATE_N_THREADS or os.cpu_count()
            
            logger.info(f"加载翻译模型: {settings.TRANSLATE_MODEL_PATH}")
            logger.info(f"n_ctx: {n_ctx}, n_threads: {n_threads}")
            
            self._llm = Llama(
                model_path=settings.TRANSLATE_MODEL_PATH,
                n_ctx=n_ctx,
                n_threads=n_threads
            )
            logger.info("翻译模型初始化成功")
        except Exception as e:
            logger.error(f"翻译模型初始化失败: {e}", exc_info=True)
            raise

    async def cleanup(self) -> None:
        self._llm = None
        logger.info("翻译模型已清理")

    def _ensure_initialized(self) -> None:
        if self._llm is None:
            raise RuntimeError("翻译模型未初始化，请先配置 TRANSLATE_MODEL_PATH 并调用 initialize()")

    def translate(self, text: str, target_lang: str) -> str:
        self._ensure_initialized()
        
        if not text or not text.strip():
            return ""
        
        prompt = f"<|user|>\n请将以下内容翻译成{target_lang}：\n{text}\n<|assistant|>\n"
        
        max_tokens = settings.TRANSLATE_MAX_TOKENS
        if max_tokens is None:
            max_tokens = len(text) * 2
        
        temperature = settings.TRANSLATE_TEMPERATURE or 0.3
        top_p = settings.TRANSLATE_TOP_P or 0.9
        
        try:
            response = self._llm(
                prompt,
                max_tokens=max_tokens,
                temperature=temperature,
                top_p=top_p,
                stop=["<|endoftext|>", "<|user|>"]
            )
            
            result = response["choices"][0]["text"].strip()
            return result
        except Exception as e:
            logger.error(f"翻译失败: {e}", exc_info=True)
            raise

    def _get_task_key(self, token: str) -> str:
        """获取任务Redis key"""
        return f"translate:task:{token}"

    async def _save_task_status(self, token: str, status: TranslateTaskStatus, result: str = None, error: str = None):
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
            
            ttl = settings.TRANSLATE_RESULT_TTL
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

    async def create_task(self, text: str, target_lang: str) -> str:
        """创建异步翻译任务，返回token"""
        redis_client = get_redis()
        if not redis_client:
            raise RuntimeError("Redis未连接，异步翻译功能不可用")
        
        token = str(uuid.uuid4())
        
        task_data = {
            "status": TranslateTaskStatus.pending.value,
            "result": None,
            "error": None,
            "created_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat()
        }
        
        key = self._get_task_key(token)
        ttl = settings.TRANSLATE_RESULT_TTL
        
        await redis_client.setex(key, ttl, json.dumps(task_data, ensure_ascii=False))
        logger.info(f"已创建翻译任务: {token}")
        
        return token

    async def translate_async(self, token: str, text: str, target_lang: str):
        """异步执行翻译任务"""
        try:
            await self._save_task_status(token, TranslateTaskStatus.processing)
            
            result = self.translate(text, target_lang)
            
            await self._save_task_status(token, TranslateTaskStatus.completed, result=result)
            logger.info(f"翻译任务完成: {token}")
        except Exception as e:
            error_msg = str(e)
            logger.error(f"翻译任务失败: {token}, 错误: {error_msg}", exc_info=True)
            await self._save_task_status(token, TranslateTaskStatus.failed, error=error_msg)

    async def get_task_status(self, token: str) -> TranslateStatusResponse:
        """获取任务状态"""
        task_data = await self._get_task_status(token)
        
        if not task_data:
            raise ValueError("任务不存在或已过期")
        
        status = TranslateTaskStatus(task_data.get("status", "pending"))
        result = task_data.get("result")
        error = task_data.get("error")
        
        return TranslateStatusResponse(
            status=status,
            result=result,
            error=error
        )


translate_service = TranslateService()
