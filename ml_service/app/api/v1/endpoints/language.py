import logging
from fastapi import APIRouter
from app.schemas.language import (
    LanguageDetectRequest,
    LanguageDetectResponse,
    LanguageDetectBatchRequest,
    LanguageDetectBatchResponse,
    LanguageConfidenceRequest,
    LanguageConfidenceResponse,
    LanguageDetectMultipleRequest,
    LanguageDetectMultipleResponse,
    LanguageInfo,
    LanguageConfidenceItem,
    LanguageSegment
)
from app.service.ml.language import language_service
from app.core.exceptions import InternalServerException

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/language",
    tags=["语种检测"],
)


@router.post("/detect", response_model=LanguageDetectResponse, summary="检测文本语言")
async def detect_language(request: LanguageDetectRequest):
    """
    检测单个文本的语言类型
    
    - **text**: 要检测的文本内容
    - 返回检测到的语言信息，如果无法检测则返回 None
    """
    try:
        result = language_service.detect_language(request.text)
        
        if result is None:
            return LanguageDetectResponse(result=None)
        
        return LanguageDetectResponse(
            result=LanguageInfo(
                language=result["language"],
                iso_code_639_1=result.get("iso_code_639_1"),
                iso_code_639_3=result.get("iso_code_639_3")
            )
        )
    except Exception as e:
        logger.error(f"语言检测失败: {e}", exc_info=True)
        raise InternalServerException(message=f"语言检测失败: {str(e)}")


@router.post("/detect-batch", response_model=LanguageDetectBatchResponse, summary="批量检测文本语言")
async def detect_languages_batch(request: LanguageDetectBatchRequest):
    """
    批量检测多个文本的语言类型
    
    - **texts**: 要检测的文本列表
    - 返回检测结果列表，与输入文本列表一一对应
    """
    try:
        results = language_service.detect_languages_batch(request.texts)
        
        language_infos = []
        for result in results:
            if result is None:
                language_infos.append(None)
            else:
                language_infos.append(
                    LanguageInfo(
                        language=result["language"],
                        iso_code_639_1=result.get("iso_code_639_1"),
                        iso_code_639_3=result.get("iso_code_639_3")
                    )
                )
        
        return LanguageDetectBatchResponse(results=language_infos)
    except Exception as e:
        logger.error(f"批量语言检测失败: {e}", exc_info=True)
        raise InternalServerException(message=f"批量语言检测失败: {str(e)}")


@router.post("/confidence", response_model=LanguageConfidenceResponse, summary="计算语言置信度")
async def compute_language_confidence(request: LanguageConfidenceRequest):
    """
    计算文本在所有候选语言中的置信度值
    
    - **text**: 要计算置信度的文本内容
    - 返回所有候选语言的置信度列表，按置信度降序排列
    """
    try:
        confidences = language_service.compute_language_confidence(request.text)
        
        confidence_items = [
            LanguageConfidenceItem(
                language=conf["language"],
                iso_code_639_1=conf.get("iso_code_639_1"),
                iso_code_639_3=conf.get("iso_code_639_3"),
                confidence=conf["confidence"]
            )
            for conf in confidences
        ]
        
        return LanguageConfidenceResponse(confidences=confidence_items)
    except Exception as e:
        logger.error(f"计算语言置信度失败: {e}", exc_info=True)
        raise InternalServerException(message=f"计算语言置信度失败: {str(e)}")


@router.post("/detect-multiple", response_model=LanguageDetectMultipleResponse, summary="检测混合语言文本")
async def detect_multiple_languages(request: LanguageDetectMultipleRequest):
    """
    检测混合语言文本中不同语言片段
    
    - **text**: 要检测的混合语言文本内容
    - 返回文本中不同语言片段的位置和语言类型
    """
    try:
        segments = language_service.detect_multiple_languages(request.text)
        
        segment_items = [
            LanguageSegment(
                language=seg["language"],
                iso_code_639_1=seg.get("iso_code_639_1"),
                iso_code_639_3=seg.get("iso_code_639_3"),
                start_index=seg["start_index"],
                end_index=seg["end_index"],
                text=seg["text"]
            )
            for seg in segments
        ]
        
        return LanguageDetectMultipleResponse(segments=segment_items)
    except Exception as e:
        logger.error(f"混合语言检测失败: {e}", exc_info=True)
        raise InternalServerException(message=f"混合语言检测失败: {str(e)}")
