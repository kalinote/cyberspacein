import logging
from fastapi import APIRouter, BackgroundTasks
from app.schemas.entities import (
    EntitiesRequest,
    EntitiesResponse,
    EntitiesAsyncRequest,
    EntitiesAsyncResponse,
    EntitiesStatusResponse
)
from app.service.ml.entities import entities_service
from app.core.exceptions import InternalServerException, BadRequestException, NotFoundException

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/entities",
    tags=["实体提取"],
)


@router.post("/short", response_model=EntitiesResponse, summary="提取实体（短文本）")
async def extract_entities(request: EntitiesRequest):
    """
    从文本中提取实体（同步接口）
    
    - **text**: 待提取实体的文本内容（最多300字符）
    - 返回提取的实体列表（包括人名、地名、国家地区、机构、企业等）
    """
    if len(request.text) > 300:
        raise BadRequestException(message="文本长度不能超过300字符，请使用异步接口")
    
    try:
        entities = await entities_service.extract_entities_in_executor(request.text)
        return EntitiesResponse(entities=entities)
    except Exception as e:
        logger.error(f"实体提取失败: {e}", exc_info=True)
        raise InternalServerException(message=f"实体提取失败: {str(e)}")


@router.post("/async", response_model=EntitiesAsyncResponse, summary="提交异步实体提取任务")
async def extract_entities_async(request: EntitiesAsyncRequest, background_tasks: BackgroundTasks):
    """
    提交异步实体提取任务
    
    - **text**: 待提取实体的文本内容
    - 立即返回token，通过token查询提取状态和结果
    """
    try:
        token = await entities_service.create_task(request.text)
        background_tasks.add_task(
            entities_service.extract_entities_async,
            token,
            request.text
        )
        return EntitiesAsyncResponse(token=token)
    except RuntimeError as e:
        raise InternalServerException(message=str(e))
    except Exception as e:
        logger.error(f"提交实体提取任务失败: {e}", exc_info=True)
        raise InternalServerException(message=f"提交实体提取任务失败: {str(e)}")


@router.get("/status/{token}", response_model=EntitiesStatusResponse, summary="查询实体提取任务状态")
async def get_entities_status(token: str):
    """
    查询实体提取任务状态和结果
    
    - **token**: 实体提取任务token
    - 返回任务状态、实体列表（如果已完成）或错误信息（如果失败）
    """
    try:
        return await entities_service.get_task_status(token)
    except ValueError as e:
        raise NotFoundException(message=str(e))
    except Exception as e:
        logger.error(f"查询实体提取任务状态失败: {e}", exc_info=True)
        raise InternalServerException(message=f"查询实体提取任务状态失败: {str(e)}")
