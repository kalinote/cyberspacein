import logging
import json
import uuid
from datetime import datetime
from typing import Optional, List, Dict
from app.core.config import settings
from app.service.ml.base import BaseMLService
from app.service.ml.generic import generic_service
from app.schemas.entities import EntitiesTaskStatus, EntitiesStatusResponse
from app.db import get_redis
from app.utils.text_processing import split_text_with_overlap, remove_think_tags

logger = logging.getLogger(__name__)


class EntitiesService(BaseMLService):
    _instance: Optional['EntitiesService'] = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    async def initialize(self) -> None:
        if not generic_service.is_model_ready():
            logger.warning("通用模型服务未初始化或模型未加载，实体提取功能将不可用")
            return
        
        if not generic_service.is_executor_ready():
            logger.warning("通用模型服务线程池未初始化，实体提取功能将不可用")
            return
        
        logger.info("实体提取服务初始化成功")

    async def cleanup(self) -> None:
        logger.info("实体提取服务已清理")

    def _ensure_available(self) -> None:
        """检查服务是否可用"""
        if not generic_service.is_model_ready():
            raise RuntimeError("通用模型未初始化，请先配置 GENERIC_MODEL_PATH 并调用 initialize()")
        if not generic_service.is_executor_ready():
            raise RuntimeError("通用模型线程池未初始化，请先调用 initialize()")
    
    def is_available(self) -> bool:
        """检查服务是否可用"""
        return generic_service.is_model_ready() and generic_service.is_executor_ready()
    
    ENTITY_CATEGORIES_EN = ("person", "location", "organization", "company", "region", "network_user")

    def _build_entities_messages_optimized(self, text: str) -> list:
        """构建实体提取的消息列表（Markdown格式）"""
        think_label = "/no_think" if len(text) < 300 else "/think"
        return [
            {
                "role": "system",
                "content": "你是一个专业的实体提取助手。"
            },
            {
                "role": "user",
                "content": f"""{think_label} 请从下方文本中提取实体。

### 要求：
1. 仅提取以下类别：person、location、organization、company、region、network_user。
2. 不要提取数字、时间、书名、抽象概念。
3. 格式：每行一个，使用 "实体 | 类别" 的格式，类别必须使用英文 key（见下方）。

### 类别（英文 key）与含义：
- **person**：真实人物的姓名（人名）
- **location**：地理位置名称（地名）
- **organization**：组织机构名称（机构）
- **company**：公司、企业名称（企业）
- **region**：国家、地区、区域（国家地区）
- **network_user**：疑似网络用户名、账号、昵称等。如：社交媒体/论坛/评论区中的用户名、含特殊字符或数字的疑似账号、@提及（结果不带@）

### 示例：
输入：张三在阿里巴巴杭州总部工作，用户@tech_guru在数码博主‘数码狂人’的贴文评论区留言。
输出：
张三 | person
阿里巴巴 | company
杭州 | location
tech_guru | network_user
数码狂人 | network_user

### 待处理文本：
{text}
"""
            }
        ]
    
    def _normalize_category(self, category: str) -> Optional[str]:
        """将类别名称映射为英文 key，不在白名单内的返回 None"""
        if not category:
            return None
        raw = category.strip().lower()
        category_map = {
            "人名": "person", "人物": "person", "人员": "person",
            "地名": "location", "地点": "location", "位置": "location",
            "机构": "organization", "组织机构": "organization", "组织": "organization",
            "企业": "company", "公司": "company",
            "国家地区": "region", "国家": "region", "地区": "region", "区域": "region",
            "网络用户": "network_user", "用户名": "network_user", "用户": "network_user",
            "账号": "network_user", "昵称": "network_user", "id": "network_user",
            "person": "person", "location": "location", "organization": "organization",
            "company": "company", "region": "region", "network_user": "network_user",
        }
        return category_map.get(raw) or (raw if raw in self.ENTITY_CATEGORIES_EN else None)
    
    def _merge_entities_results(self, results: List[Dict[str, List[str]]]) -> Dict[str, List[str]]:
        """合并多个实体提取结果，按类别合并并去重（key 为英文）"""
        merged = {k: [] for k in self.ENTITY_CATEGORIES_EN}
        for result in results:
            for category, entities in result.items():
                if category in merged:
                    for entity in entities:
                        if entity not in merged[category]:
                            merged[category].append(entity)
        return {k: v for k, v in merged.items() if v}
    
    def _parse_entities_result(self, result_text: str) -> Dict[str, List[str]]:
        """解析实体提取结果（Markdown格式），输出 key 为英文类别"""
        try:
            result_text = remove_think_tags(result_text)
            entities_by_category: Dict[str, List[str]] = {k: [] for k in self.ENTITY_CATEGORIES_EN}

            for line in result_text.split('\n'):
                line = line.strip()
                if not line:
                    continue
                if '|' in line:
                    parts = line.split('|', 1)
                    entity = parts[0].strip()
                    category = parts[1].strip() if len(parts) > 1 else ""
                    if entity and category:
                        category_normalized = self._normalize_category(category)
                        if category_normalized and category_normalized in entities_by_category:
                            if entity not in entities_by_category[category_normalized]:
                                entities_by_category[category_normalized].append(entity)

            result = {k: v for k, v in entities_by_category.items() if v}
            if not result:
                logger.warning(f"未提取到任何实体，原始响应: {result_text[:200]}")
            return result
        except Exception as e:
            logger.error(f"解析实体提取结果失败，原始响应: {result_text[:200]}", exc_info=True)
            raise ValueError(f"无法解析模型返回的格式: {e}") from e
    
    async def extract_entities_in_executor(self, text: str) -> Dict[str, List[str]]:
        """在线程池中执行实体提取任务"""
        if not text or not text.strip():
            return {}
        
        self._ensure_available()
        
        messages = self._build_entities_messages_optimized(text)
        
        result_text = await generic_service.inference_in_executor(
            messages=messages,
            json_schema=None,
            max_tokens=2048,
            temperature=0.1
        )
        
        return self._parse_entities_result(result_text)

    def _get_task_key(self, token: str) -> str:
        """获取任务Redis key"""
        return f"entities:task:{token}"

    async def _save_task_status(self, token: str, status: EntitiesTaskStatus, result: Dict[str, List[str]] = None, error: str = None, all: int = None, finished: int = None):
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
            
            if all is not None:
                task_data["all"] = all
            if finished is not None:
                task_data["finished"] = finished
            
            if existing_data:
                existing = json.loads(existing_data)
                task_data["created_at"] = existing.get("created_at", datetime.now().isoformat())
                if "all" not in task_data:
                    task_data["all"] = existing.get("all")
                if "finished" not in task_data:
                    task_data["finished"] = existing.get("finished")
            else:
                task_data["created_at"] = datetime.now().isoformat()
            
            ttl = settings.ENTITIES_RESULT_TTL
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
        """创建异步实体提取任务，返回token"""
        redis_client = get_redis()
        if not redis_client:
            raise RuntimeError("Redis未连接，异步实体提取功能不可用")
        
        token = str(uuid.uuid4())
        
        task_data = {
            "status": EntitiesTaskStatus.pending.value,
            "result": None,
            "error": None,
            "created_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat()
        }
        
        key = self._get_task_key(token)
        ttl = settings.ENTITIES_RESULT_TTL
        
        await redis_client.setex(key, ttl, json.dumps(task_data, ensure_ascii=False))
        logger.info(f"已创建实体提取任务: {token}")
        
        return token

    async def extract_entities_async(self, token: str, text: str):
        """异步执行实体提取任务（支持分段处理）"""
        try:
            segments = split_text_with_overlap(text)
            total_segments = len(segments)
            
            await self._save_task_status(token, EntitiesTaskStatus.processing, all=total_segments, finished=0)
            
            if total_segments == 1:
                entities_dict = await self.extract_entities_in_executor(text)
                await self._save_task_status(token, EntitiesTaskStatus.completed, result=entities_dict, all=total_segments, finished=1)
            else:
                segment_results = []
                failed_segments = []
                
                for i, segment in enumerate(segments, 1):
                    try:
                        result = await self.extract_entities_in_executor(segment)
                        segment_results.append(result)
                        await self._save_task_status(token, EntitiesTaskStatus.processing, all=total_segments, finished=i)
                    except Exception as e:
                        error_msg = f"第 {i} 段处理失败: {str(e)}"
                        logger.error(f"实体提取任务 {token} - {error_msg}", exc_info=True)
                        failed_segments.append(i)
                        await self._save_task_status(token, EntitiesTaskStatus.processing, all=total_segments, finished=i)
                        continue
                
                if not segment_results:
                    raise ValueError(f"所有段处理都失败，共 {total_segments} 段")
                
                if failed_segments:
                    logger.warning(f"任务 {token} 有 {len(failed_segments)} 段处理失败: {failed_segments}，将使用成功处理的段的结果")
                
                entities_dict = self._merge_entities_results(segment_results)
                await self._save_task_status(token, EntitiesTaskStatus.completed, result=entities_dict, all=total_segments, finished=total_segments)
        except Exception as e:
            error_msg = str(e)
            logger.error(f"实体提取任务失败: {token}, 错误: {error_msg}", exc_info=True)
            await self._save_task_status(token, EntitiesTaskStatus.failed, error=error_msg)

    async def get_task_status(self, token: str) -> EntitiesStatusResponse:
        """获取任务状态"""
        task_data = await self._get_task_status(token)
        
        if not task_data:
            raise ValueError("任务不存在或已过期")
        
        status = EntitiesTaskStatus(task_data.get("status", "pending"))
        result = task_data.get("result")
        error = task_data.get("error")
        all_segments = task_data.get("all")
        finished_segments = task_data.get("finished")
        
        return EntitiesStatusResponse(
            status=status,
            entities=result,
            error=error,
            all=all_segments,
            finished=finished_segments
        )


entities_service = EntitiesService()
