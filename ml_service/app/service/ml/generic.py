import logging
import os
import json
import asyncio
import threading
from typing import Optional, Dict, List
from concurrent.futures import ThreadPoolExecutor
from llama_cpp import Llama
from app.core.config import settings
from app.service.ml.base import BaseMLService

logger = logging.getLogger(__name__)


class GenericMLService(BaseMLService):
    _instance: Optional['GenericMLService'] = None
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
            pool_size = settings.GENERIC_THREAD_POOL_SIZE
            if pool_size is None:
                pool_size = max(2, min(4, os.cpu_count() // 2))
            self._executor = ThreadPoolExecutor(max_workers=pool_size, thread_name_prefix="generic")
            logger.info(f"通用模型线程池已初始化，大小: {pool_size}")
        
        if self._llm is not None:
            logger.info("通用模型已初始化")
            return

        if not settings.GENERIC_MODEL_PATH:
            logger.warning("GENERIC_MODEL_PATH 未配置，通用模型功能将不可用")
            return

        try:
            n_ctx = settings.GENERIC_N_CTX or 10240
            n_threads = settings.GENERIC_N_THREADS or os.cpu_count()
            
            logger.info(f"加载通用模型: {settings.GENERIC_MODEL_PATH}")
            logger.info(f"n_ctx: {n_ctx}, n_threads: {n_threads}")
            
            self._llm = Llama(
                model_path=settings.GENERIC_MODEL_PATH,
                n_ctx=n_ctx,
                n_threads=n_threads,
                verbose=False
            )
            
            logger.info("通用模型初始化成功")
        except Exception as e:
            logger.error(f"通用模型初始化失败: {e}", exc_info=True)
            raise

    async def cleanup(self) -> None:
        if self._executor is not None:
            logger.info("正在关闭通用模型线程池...")
            try:
                self._executor.shutdown(wait=True)
            except Exception as e:
                logger.warning(f"关闭线程池时出现异常: {e}")
            finally:
                self._executor = None
                logger.info("通用模型线程池已关闭")
        
        self._llm = None
        self._lock = None
        logger.info("通用模型已清理")

    def _ensure_initialized(self) -> None:
        if self._llm is None:
            raise RuntimeError("通用模型未初始化，请先配置 GENERIC_MODEL_PATH 并调用 initialize()")
        if self._lock is None:
            raise RuntimeError("通用模型线程锁未初始化，请先调用 initialize()")
        if self._executor is None:
            raise RuntimeError("通用模型线程池未初始化，请先调用 initialize()")
    
    def is_executor_ready(self) -> bool:
        """检查执行器是否已初始化"""
        return self._executor is not None
    
    def is_model_ready(self) -> bool:
        """检查模型是否已加载"""
        return self._llm is not None
    
    async def inference_in_executor(
        self,
        json_schema: Dict,
        messages: List[Dict],
        max_tokens: Optional[int] = None,
        temperature: Optional[float] = None,
        top_p: Optional[float] = None
    ) -> str:
        """在线程池中执行推理任务"""
        self._ensure_initialized()
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            self._executor,
            self.inference,
            json_schema,
            messages,
            max_tokens,
            temperature,
            top_p
        )

    def inference(
        self,
        json_schema: Dict,
        messages: List[Dict],
        max_tokens: Optional[int] = None,
        temperature: Optional[float] = None,
        top_p: Optional[float] = None
    ) -> str:
        """执行模型推理"""
        self._ensure_initialized()
        
        if max_tokens is None:
            max_tokens = settings.GENERIC_MAX_TOKENS or 2048
        
        if temperature is None:
            temperature = settings.GENERIC_TEMPERATURE or 0.1
        
        if top_p is None:
            top_p = settings.GENERIC_TOP_P or 0.9
        
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
            
            return content
            
        except (KeyError, IndexError, TypeError) as e:
            logger.error(f"响应结构异常: {response if 'response' in locals() else '未知'}", exc_info=True)
            raise ValueError(f"响应格式错误: {e}") from e
        except Exception as e:
            logger.error(f"推理失败: {e}", exc_info=True)
            raise


generic_service = GenericMLService()
