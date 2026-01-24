import logging
import json
import uuid
from datetime import datetime
from typing import Optional, List, Tuple
from app.core.config import settings
from app.service.ml.base import BaseMLService
from app.service.ml.generic import generic_service
from app.schemas.keywords import KeywordsTaskStatus, KeywordsStatusResponse
from app.db import get_redis
from app.utils.text_processing import split_text_with_overlap, remove_think_tags

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
    
    def _build_keywords_messages(self, text: str, include_summary: bool = False) -> list:
        # 短文本暂时不做思考，节省时间
        think_label = "/no_think" if len(text) < 300 else "/think"
        
        if include_summary:
            return [
                {
                    "role": "system",
                    "content": "你是一个专业的文本分析师，擅长提取核心关键词和总结内容。"
                },
                {
                    "role": "user",
                    "content": f"""/no_think 请从下方文本中提取 5-10 个核心关键词，并生成一段不超过30字的总结。

### 提取原则：
1. **准确性**：必须是文中原话，或者是文中核心概念的精准概括。
2. **简洁性**：关键词通常是名词或短语（2-6个字），严禁提取整句话，严禁将单个字作为关键词。
3. **重要性**：只提取最能代表文章主题的词，不要将无意义的短语、链接等作为关键词。

### 输出格式：
1. 首先输出总结，格式为："总结：xxx（不超过30字）"
2. 然后空一行
3. 接着输出关键词，每行一个，格式为："关键词：\n- 关键词1\n- 关键词2"
4. 不要包含任何其他解释
5. 如果内容涉及成人内容，必须提供NSFW作为一个关键词。

### 示例：
输入：深度学习是机器学习的一个子集，它利用多层神经网络来模拟人脑的学习过程，...
输出：
总结：介绍深度学习作为机器学习的子集，通过多层神经网络模拟人脑学习。

关键词：
- 深度学习
- 机器学习
- 神经网络
- 模拟人脑

### 待处理文本：
{text}
"""
                }
            ]
        else:
            return [
                {
                    "role": "system",
                    "content": "你是一个专业的文本分析师，擅长提取核心关键词。"
                },
                {
                    "role": "user",
                    "content": f"""/no_think 请从下方文本中提取 5-10 个核心关键词。

### 提取原则：
1. **准确性**：必须是文中原话，或者是文中核心概念的精准概括。
2. **简洁性**：关键词通常是名词或短语（2-6个字），严禁提取整句话，严禁将单个字作为关键词。
3. **重要性**：只提取最能代表文章主题的词，不要将无意义的短语、链接等作为关键词。

### 输出格式：
1. 不要包含任何解释，每行一个关键词，格式为："- 关键词"
2. 如果内容涉及成人内容，必须提供NSFW作为一个关键词。

### 示例：
输入：深度学习是机器学习的一个子集，它利用多层神经网络来模拟人脑的学习过程。
输出：
- 深度学习
- 机器学习
- 神经网络
- 模拟人脑

### 待处理文本：
{text}
"""
                }
            ]
    
    def _parse_keywords_result(self, result_text: str) -> List[str]:
        """解析关键词提取结果（Markdown格式）"""
        try:
            result_text = remove_think_tags(result_text)
            
            keywords = []
            for line in result_text.split('\n'):
                line = line.strip()
                if not line:
                    continue
                
                if line.startswith('- '):
                    keyword = line[2:].strip()
                    if keyword:
                        keywords.append(keyword)
            
            if not keywords:
                logger.warning(f"未提取到任何关键词，原始响应: {result_text[:200]}")
            
            return keywords
            
        except Exception as e:
            logger.error(f"解析关键词提取结果失败，原始响应: {result_text[:200]}", exc_info=True)
            raise ValueError(f"无法解析模型返回的格式: {e}") from e
    
    def _parse_keywords_and_summary_result(self, result_text: str) -> Tuple[str, List[str]]:
        """解析关键词提取结果（包含总结和关键词）"""
        try:
            result_text = remove_think_tags(result_text)
            
            summary = ""
            keywords = []
            in_keywords_section = False
            
            for line in result_text.split('\n'):
                line = line.strip()
                if not line:
                    if in_keywords_section:
                        continue
                    else:
                        continue
                
                if line.startswith('总结：'):
                    summary = line[3:].strip()
                    if summary.endswith('（不超过30字）'):
                        summary = summary[:-7].strip()
                elif line.startswith('关键词：'):
                    in_keywords_section = True
                elif in_keywords_section and line.startswith('- '):
                    keyword = line[2:].strip()
                    if keyword:
                        keywords.append(keyword)
            
            if not summary:
                logger.warning(f"未提取到总结，原始响应: {result_text[:200]}")
            if not keywords:
                logger.warning(f"未提取到任何关键词，原始响应: {result_text[:200]}")
            
            return summary, keywords
            
        except Exception as e:
            logger.error(f"解析关键词和总结结果失败，原始响应: {result_text[:200]}", exc_info=True)
            raise ValueError(f"无法解析模型返回的格式: {e}") from e
    
    async def extract_keywords_in_executor(self, text: str) -> List[str]:
        """在线程池中执行关键词提取任务"""
        if not text or not text.strip():
            return []
        
        self._ensure_available()
        
        messages = self._build_keywords_messages(text, include_summary=False)
        
        result_text = await generic_service.inference_in_executor(
            messages=messages,
            json_schema=None,
            max_tokens=2048,
            temperature=0.1
        )
        
        return self._parse_keywords_result(result_text)
    
    async def extract_keywords_with_summary_in_executor(self, text: str) -> Tuple[str, List[str]]:
        """在线程池中执行关键词提取任务（异步接口专用，返回总结和关键词）"""
        if not text or not text.strip():
            return "", []
        
        self._ensure_available()
        
        messages = self._build_keywords_messages(text, include_summary=True)
        
        result_text = await generic_service.inference_in_executor(
            messages=messages,
            json_schema=None,
            max_tokens=2048,
            temperature=0.1
        )
        
        return self._parse_keywords_and_summary_result(result_text)

    def _get_task_key(self, token: str) -> str:
        """获取任务Redis key"""
        return f"keywords:task:{token}"

    async def _save_task_status(self, token: str, status: KeywordsTaskStatus, result: List[str] = None, error: str = None, all: int = None, finished: int = None):
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

    def _merge_keywords_results(self, results: List[List[str]]) -> List[str]:
        """合并多个分段的关键词结果并去重"""
        merged = []
        seen = set()
        
        for keywords in results:
            for keyword in keywords:
                if keyword not in seen:
                    seen.add(keyword)
                    merged.append(keyword)
        
        return merged
    
    def _build_refine_messages(self, summaries: List[str], segment_keywords: List[List[str]], all_keywords: List[str], target_count: int) -> list:
        """构建二次精炼的提示词"""
        chunks_data = []
        for i, (summary, keywords) in enumerate(zip(summaries, segment_keywords), 1):
            keywords_str = " | ".join(keywords)
            chunks_data.append(f"段落{i}摘要：{summary}\n段落{i}关键词：{keywords_str}")
        
        all_chunks_data = "\n\n".join(chunks_data)
        all_keywords_str = " | ".join(all_keywords)
        all_chunks_data += f"\n\n所有候选关键词：{all_keywords_str}"
        
        return [
            {
                "role": "system",
                "content": "你是一个高层级的内容主编，擅长从各段精华中提炼全局核心。"
            },
            {
                "role": "user",
                "content": f"""### 任务背景
以下是一篇长文各段落的"摘要"和"候选关键词"。请通过这些信息，总结出整篇文章最核心的 {target_count} 个关键词。

### 输入数据
{all_chunks_data}

### 筛选原则
1. **全局性**：优先选择在多个段落中反复提及、或贯穿全篇的核心概念。
2. **代表性**：排除仅在局部段落出现的细枝末节。
3. **专业性**：使用标准、正式的专有名词。

### 输出格式：
1. 不要包含任何解释，每行一个关键词，格式为："- 关键词"
2. 如果提供的关键词中包含NSFW，则输出中必须包含NSFW。
"""
            }
        ]
    
    async def _refine_keywords(self, summaries: List[str], segment_keywords: List[List[str]], all_keywords: List[str], target_count: int) -> List[str]:
        """执行二次精炼，从所有关键词中选出最相关的target_count个"""
        self._ensure_available()
        
        messages = self._build_refine_messages(summaries, segment_keywords, all_keywords, target_count)
        
        result_text = await generic_service.inference_in_executor(
            messages=messages,
            json_schema=None,
            max_tokens=2048,
            temperature=0.1
        )
        
        return self._parse_keywords_result(result_text)

    async def extract_keywords_async(self, token: str, text: str):
        """异步执行关键词提取任务（支持分段处理）"""
        try:
            segments = split_text_with_overlap(text)
            total_segments = len(segments)
            
            await self._save_task_status(token, KeywordsTaskStatus.processing, all=total_segments, finished=0)
            
            if total_segments == 1:
                summary, keywords = await self.extract_keywords_with_summary_in_executor(text)
                await self._save_task_status(token, KeywordsTaskStatus.completed, result=keywords, all=total_segments, finished=1)
            else:
                segment_summaries = []
                segment_keywords_list = []
                
                for i, segment in enumerate(segments, 1):
                    try:
                        summary, keywords = await self.extract_keywords_with_summary_in_executor(segment)
                        segment_summaries.append(summary)
                        segment_keywords_list.append(keywords)
                        await self._save_task_status(token, KeywordsTaskStatus.processing, all=total_segments, finished=i)
                    except Exception as e:
                        logger.warning(f"关键词提取任务 {token} - 第 {i} 段处理失败: {str(e)}，跳过该段", exc_info=True)
                        await self._save_task_status(token, KeywordsTaskStatus.processing, all=total_segments, finished=i)
                        continue
                
                if not segment_keywords_list:
                    raise ValueError(f"所有段处理都失败，共 {total_segments} 段")
                
                all_keywords = self._merge_keywords_results(segment_keywords_list)
                # TODO: 最大关键词数量计算方法可能需要进一步优化
                threshold = max(10, total_segments * 2)
                
                if len(all_keywords) > threshold:
                    logger.info(f"关键词数量 {len(all_keywords)} 超过阈值 {threshold}，开始二次精炼")
                    keywords = await self._refine_keywords(segment_summaries, segment_keywords_list, all_keywords, threshold)
                else:
                    keywords = all_keywords
                
                await self._save_task_status(token, KeywordsTaskStatus.completed, result=keywords, all=total_segments, finished=total_segments)
        except Exception as e:
            logger.error(f"关键词提取任务失败: {token}, 错误: {str(e)}", exc_info=True)
            await self._save_task_status(token, KeywordsTaskStatus.failed, error=str(e))

    async def get_task_status(self, token: str) -> KeywordsStatusResponse:
        """获取任务状态"""
        task_data = await self._get_task_status(token)
        
        if not task_data:
            raise ValueError("任务不存在或已过期")
        
        status = KeywordsTaskStatus(task_data.get("status", "pending"))
        result = task_data.get("result")
        error = task_data.get("error")
        all_segments = task_data.get("all")
        finished_segments = task_data.get("finished")
        
        return KeywordsStatusResponse(
            status=status,
            keywords=result,
            error=error,
            all=all_segments,
            finished=finished_segments
        )


keywords_service = KeywordsService()
