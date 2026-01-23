import logging
import os
import json
import uuid
import asyncio
import threading
from datetime import datetime
from typing import Optional
from concurrent.futures import ThreadPoolExecutor
from llama_cpp import Llama
from app.core.config import settings
from app.service.ml.base import BaseMLService
from app.schemas.translate import TranslateTaskStatus, TranslateStatusResponse
from app.db import get_redis

logger = logging.getLogger(__name__)


class TranslateService(BaseMLService):
    _instance: Optional['TranslateService'] = None
    _llm: Optional[Llama] = None
    _executor: Optional[ThreadPoolExecutor] = None
    _lock: Optional[threading.Lock] = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    async def initialize(self) -> None:
        if self._lock is None:
            self._lock = threading.Lock()
        
        if self._executor is None:
            pool_size = settings.TRANSLATE_THREAD_POOL_SIZE
            if pool_size is None:
                pool_size = max(2, min(4, os.cpu_count() // 2))
            self._executor = ThreadPoolExecutor(max_workers=pool_size, thread_name_prefix="translate")
            logger.info(f"翻译线程池已初始化，大小: {pool_size}")
        
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
                n_threads=n_threads,
                verbose=False
            )
            
            logger.info("翻译模型初始化成功")
        except Exception as e:
            logger.error(f"翻译模型初始化失败: {e}", exc_info=True)
            raise

    async def cleanup(self) -> None:
        if self._executor is not None:
            logger.info("正在关闭翻译线程池...")
            try:
                self._executor.shutdown(wait=True)
            except Exception as e:
                logger.warning(f"关闭线程池时出现异常: {e}")
            finally:
                self._executor = None
                logger.info("翻译线程池已关闭")
        
        self._llm = None
        self._lock = None
        logger.info("翻译模型已清理")

    def _ensure_initialized(self) -> None:
        if self._llm is None:
            raise RuntimeError("翻译模型未初始化，请先配置 TRANSLATE_MODEL_PATH 并调用 initialize()")
        if self._lock is None:
            raise RuntimeError("翻译线程锁未初始化，请先调用 initialize()")
        if self._executor is None:
            raise RuntimeError("翻译线程池未初始化，请先调用 initialize()")
    
    def is_executor_ready(self) -> bool:
        """检查执行器是否已初始化"""
        return self._executor is not None
    
    async def translate_in_executor(self, text: str, target_lang: str) -> str:
        """在线程池中执行翻译任务"""
        self._ensure_initialized()
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            self._executor,
            self.translate,
            text,
            target_lang
        )

    def translate(self, text: str, target_lang: str) -> str:
        self._ensure_initialized()
        
        if not text or not text.strip():
            return ""
        
        json_schema = {
            "type": "object",
            "properties": {
                "result": {
                    "type": "string"
                }
            },
            "required": ["result"]
        }
        
        messages = [
            {
                "role": "system",
                "content": "你是一位专业的翻译专家。"
            },
            {
                "role": "user",
                "content": f"请将以下内容翻译成{target_lang}，注意只需要输出翻译后的结果，不要额外解释，注意语句通顺，输出 JSON 格式：\n\n{text}"
            }
        ]
        
        max_tokens = settings.TRANSLATE_MAX_TOKENS
        if max_tokens is None:
            max_tokens = len(text) * 2
        
        temperature = settings.TRANSLATE_TEMPERATURE or 0.3
        top_p = settings.TRANSLATE_TOP_P or 0.9
        
        try:
            with self._lock:
                response = self._llm.create_chat_completion(
                    messages=messages,
                    max_tokens=max_tokens,
                    temperature=temperature,
                    top_p=top_p,
                    response_format={
                        "type": "json_object",
                        "schema": json_schema
                    }
                )
            
            if "choices" not in response or not response["choices"]:
                raise ValueError("响应中缺少 choices 字段或 choices 为空")
            
            message = response["choices"][0].get("message")
            if not message:
                raise ValueError("响应中缺少 message 字段")
            
            content = message.get("content")
            if not content:
                raise ValueError("响应中缺少 content 字段")
            
            try:
                result_data = json.loads(content)
            except json.JSONDecodeError as e:
                logger.error(f"JSON 解析失败，原始响应: {content}", exc_info=True)
                raise ValueError(f"无法解析模型返回的 JSON 格式: {e}") from e
            
            if "result" not in result_data:
                logger.error(f"JSON 中缺少 result 字段，解析结果: {result_data}")
                raise ValueError("模型返回的 JSON 中缺少 result 字段")
            
            return result_data["result"]
            
        except (KeyError, IndexError, TypeError) as e:
            logger.error(f"响应结构异常: {response if 'response' in locals() else '未知'}", exc_info=True)
            raise ValueError(f"响应格式错误: {e}") from e
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
            
            result = await self.translate_in_executor(text, target_lang)
            
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
