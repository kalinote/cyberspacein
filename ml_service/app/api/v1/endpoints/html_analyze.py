import logging

from fastapi import APIRouter

from app.schemas.html_analyze import (
    HtmlExtractTextRequest,
    HtmlExtractTextResponse,
    HtmlCleanRequest,
    HtmlCleanResponse,
    HtmlExtractLinksRequest,
    HtmlExtractLinksResponse,
    HtmlBatchRequest,
    HtmlExtractTextBatchItem,
    HtmlCleanBatchItem,
    HtmlExtractLinksBatchItem,
)
from app.service.ml.html_analyze import html_analyze_service
from app.core.exceptions import InternalServerException

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/html-analyze",
    tags=["HTML 静态分析"],
)


@router.post("/extract-text", response_model=HtmlExtractTextResponse, summary="提取 HTML 中的纯文本")
async def extract_text(request: HtmlExtractTextRequest):
    try:
        text = html_analyze_service.extract_text(request.html)
        return HtmlExtractTextResponse(text=text)
    except Exception as e:
        logger.error(f"HTML 文本提取失败: {e}", exc_info=True)
        raise InternalServerException(message=f"HTML 文本提取失败: {str(e)}")


@router.post("/clean", response_model=HtmlCleanResponse, summary="清理 HTML 标签与脚本")
async def clean_html(request: HtmlCleanRequest):
    try:
        html = html_analyze_service.clean_html(request.html)
        return HtmlCleanResponse(html=html)
    except Exception as e:
        logger.error(f"HTML 清理失败: {e}", exc_info=True)
        raise InternalServerException(message=f"HTML 清理失败: {str(e)}")


@router.post("/extract-links", response_model=HtmlExtractLinksResponse, summary="提取 HTML 中所有资源链接")
async def extract_links(request: HtmlExtractLinksRequest):
    try:
        links = html_analyze_service.extract_resource_links(request.html)
        return HtmlExtractLinksResponse(links=links)
    except Exception as e:
        logger.error(f"HTML 资源链接提取失败: {e}", exc_info=True)
        raise InternalServerException(message=f"HTML 资源链接提取失败: {str(e)}")


@router.post("/extract-text-batch", response_model=list[HtmlExtractTextBatchItem], summary="批量提取 HTML 中的纯文本")
async def extract_text_batch(request: HtmlBatchRequest):
    try:
        result = []
        for item in request.datas:
            text = html_analyze_service.extract_text(item.html)
            result.append(HtmlExtractTextBatchItem(uuid=item.uuid, text=text))
        return result
    except Exception as e:
        logger.error(f"批量 HTML 文本提取失败: {e}", exc_info=True)
        raise InternalServerException(message=f"批量 HTML 文本提取失败: {str(e)}")


@router.post("/clean-batch", response_model=list[HtmlCleanBatchItem], summary="批量清理 HTML 标签与脚本")
async def clean_html_batch(request: HtmlBatchRequest):
    try:
        result = []
        for item in request.datas:
            html = html_analyze_service.clean_html(item.html)
            result.append(HtmlCleanBatchItem(uuid=item.uuid, html=html))
        return result
    except Exception as e:
        logger.error(f"批量 HTML 清理失败: {e}", exc_info=True)
        raise InternalServerException(message=f"批量 HTML 清理失败: {str(e)}")


@router.post("/extract-links-batch", response_model=list[HtmlExtractLinksBatchItem], summary="批量提取 HTML 中所有资源链接")
async def extract_links_batch(request: HtmlBatchRequest):
    try:
        result = []
        for item in request.datas:
            links = html_analyze_service.extract_resource_links(item.html)
            result.append(HtmlExtractLinksBatchItem(uuid=item.uuid, links=links))
        return result
    except Exception as e:
        logger.error(f"批量 HTML 资源链接提取失败: {e}", exc_info=True)
        raise InternalServerException(message=f"批量 HTML 资源链接提取失败: {str(e)}")
