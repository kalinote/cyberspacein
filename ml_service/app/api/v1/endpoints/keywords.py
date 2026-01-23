import logging
from fastapi import APIRouter, BackgroundTasks
from app.schemas.keywords import (
    KeywordsRequest,
    KeywordsResponse,
    KeywordsAsyncRequest,
    KeywordsAsyncResponse,
    KeywordsStatusResponse
)
from app.service.ml.keywords import keywords_service
from app.core.exceptions import InternalServerException, BadRequestException, NotFoundException

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/keywords",
    tags=["关键词提取"],
)


@router.post("/short", response_model=KeywordsResponse, summary="提取关键词（短文本）")
async def extract_keywords(request: KeywordsRequest):
    """
    从文本中提取关键词（同步接口）
    
    - **text**: 待提取关键词的文本内容（最多300字符）
    - 返回提取的关键词列表（5-10个）
    """
    if len(request.text) > 300:
        raise BadRequestException(message="文本长度不能超过300字符，请使用异步接口")
    
    try:
        keywords = await keywords_service.extract_keywords_in_executor(request.text)
        return KeywordsResponse(keywords=keywords)
    except Exception as e:
        logger.error(f"关键词提取失败: {e}", exc_info=True)
        raise InternalServerException(message=f"关键词提取失败: {str(e)}")


@router.post("/async", response_model=KeywordsAsyncResponse, summary="提交异步关键词提取任务")
async def extract_keywords_async(request: KeywordsAsyncRequest, background_tasks: BackgroundTasks):
    """
    提交异步关键词提取任务
    
    - **text**: 待提取关键词的文本内容
    - 立即返回token，通过token查询提取状态和结果
    """
    try:
        token = await keywords_service.create_task(request.text)
        background_tasks.add_task(
            keywords_service.extract_keywords_async,
            token,
            request.text
        )
        return KeywordsAsyncResponse(token=token)
    except RuntimeError as e:
        raise InternalServerException(message=str(e))
    except Exception as e:
        logger.error(f"提交关键词提取任务失败: {e}", exc_info=True)
        raise InternalServerException(message=f"提交关键词提取任务失败: {str(e)}")


@router.get("/status/{token}", response_model=KeywordsStatusResponse, summary="查询关键词提取任务状态")
async def get_keywords_status(token: str):
    """
    查询关键词提取任务状态和结果
    
    - **token**: 关键词提取任务token
    - 返回任务状态、关键词列表（如果已完成）或错误信息（如果失败）
    """
    try:
        return await keywords_service.get_task_status(token)
    except ValueError as e:
        raise NotFoundException(message=str(e))
    except Exception as e:
        logger.error(f"查询关键词提取任务状态失败: {e}", exc_info=True)
        raise InternalServerException(message=f"查询关键词提取任务状态失败: {str(e)}")
