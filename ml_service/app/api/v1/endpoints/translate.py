import logging
from fastapi import APIRouter, BackgroundTasks
from app.schemas.translate import (
    TranslateRequest,
    TranslateResponse,
    TranslateAsyncRequest,
    TranslateAsyncResponse,
    TranslateStatusResponse
)
from app.service.ml.translate import translate_service
from app.core.exceptions import InternalServerException, BadRequestException, NotFoundException

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/translate",
    tags=["翻译"],
)


@router.post("/short", response_model=TranslateResponse, summary="翻译短文本")
async def translate_text(request: TranslateRequest):
    """
    将文本翻译成目标语种（同步接口）
    
    - **text**: 待翻译的文本内容（最多300字符）
    - **target_lang**: 目标语种（如：中文、英文、日文等）
    - 模型会自动识别原语种，无需传入
    - 返回翻译后的文本内容
    """
    if len(request.text) > 300:
        raise BadRequestException(message="文本长度不能超过300字符，请使用异步接口")
    
    try:
        result = await translate_service.translate_in_executor(
            request.text,
            request.target_lang
        )
        return TranslateResponse(result=result)
    except Exception as e:
        logger.error(f"翻译失败: {e}", exc_info=True)
        raise InternalServerException(message=f"翻译失败: {str(e)}")


@router.post("/async", response_model=TranslateAsyncResponse, summary="提交异步翻译任务")
async def translate_text_async(request: TranslateAsyncRequest, background_tasks: BackgroundTasks):
    """
    提交异步翻译任务
    TODO: 保留格式的翻译、基于上下文提示的翻译
    
    - **text**: 待翻译的文本内容
    - **target_lang**: 目标语种（如：中文、英文、日文等）
    - 立即返回token，通过token查询翻译状态和结果
    """
    try:
        token = await translate_service.create_task(request.text, request.target_lang)
        background_tasks.add_task(
            translate_service.translate_async,
            token,
            request.text,
            request.target_lang
        )
        return TranslateAsyncResponse(token=token)
    except RuntimeError as e:
        raise InternalServerException(message=str(e))
    except Exception as e:
        logger.error(f"提交翻译任务失败: {e}", exc_info=True)
        raise InternalServerException(message=f"提交翻译任务失败: {str(e)}")


@router.get("/status/{token}", response_model=TranslateStatusResponse, summary="查询翻译任务状态")
async def get_translate_status(token: str):
    """
    查询翻译任务状态和结果
    
    - **token**: 翻译任务token
    - 返回任务状态、结果（如果已完成）或错误信息（如果失败）
    """
    try:
        return await translate_service.get_task_status(token)
    except ValueError as e:
        raise NotFoundException(message=str(e))
    except Exception as e:
        logger.error(f"查询翻译任务状态失败: {e}", exc_info=True)
        raise InternalServerException(message=f"查询翻译任务状态失败: {str(e)}")
