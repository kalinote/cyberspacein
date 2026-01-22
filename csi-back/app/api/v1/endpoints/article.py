import logging
from datetime import datetime
from fastapi import APIRouter
from elasticsearch.exceptions import NotFoundError

from app.db.elasticsearch import get_es
from app.schemas.article import ArticleSchema
from app.schemas.highlight import HighlightRequestSchema
from app.schemas.response import ApiResponseSchema
from app.utils.date_time import parse_datetime

logger = logging.getLogger(__name__)


router = APIRouter(
    prefix="/article",
    tags=["article"],
)

@router.get("/detail/{uuid}", response_model=ApiResponseSchema[ArticleSchema], summary="获取文章详情")
async def get_article_detail(uuid: str):
    es = get_es()
    if not es:
        return ApiResponseSchema.error(code=500, message="Elasticsearch连接未初始化")
    
    try:
        result = await es.get(index="article", id=uuid)
        source_data = result.get("_source", {})
        
        article_data = ArticleSchema(
            uuid=source_data.get("uuid", uuid),
            source_id=source_data.get("source_id"),
            data_version=source_data.get("data_version"),
            entity_type=source_data.get("entity_type"),
            url=source_data.get("url"),
            tags=source_data.get("tags"),
            platform=source_data.get("platform"),
            section=source_data.get("section"),
            spider_name=source_data.get("spider_name"),
            update_at=parse_datetime(source_data.get("update_at")),
            crawled_at=parse_datetime(source_data.get("crawled_at")),
            publish_at=parse_datetime(source_data.get("publish_at")),
            last_edit_at=parse_datetime(source_data.get("last_edit_at")),
            language=source_data.get("language"),
            author_id=source_data.get("author_id"),
            author_name=source_data.get("author_name"),
            nsfw=source_data.get("nsfw"),
            aigc=source_data.get("aigc"),
            translation_content=source_data.get("translation_content"),
            keywords=source_data.get("keywords"),
            emotion=source_data.get("emotion"),
            political_bias=source_data.get("political_bias"),
            confidence=source_data.get("confidence"),
            subjective_rating=source_data.get("subjective_rating"),
            title=source_data.get("title"),
            clean_content=source_data.get("clean_content"),
            raw_content=source_data.get("raw_content"),
            safe_raw_content=source_data.get("safe_raw_content"),
            cover_image=source_data.get("cover_image"),
            likes=source_data.get("likes"),
            is_highlighted=source_data.get("is_highlighted", False),
            highlighted_at=parse_datetime(source_data.get("highlighted_at")),
            highlight_reason=source_data.get("highlight_reason")
        )
        
        return ApiResponseSchema.success(data=article_data)
    
    except NotFoundError:
        return ApiResponseSchema.error(code=404, message=f"文章不存在，UUID: {uuid}")
    except Exception as e:
        return ApiResponseSchema.error(code=500, message=f"查询文章详情失败: {str(e)}")

@router.put("/highlight/{uuid}", response_model=ApiResponseSchema[dict], summary="设置/取消重点目标标记")
async def set_article_highlight(uuid: str, data: HighlightRequestSchema):
    """
    设置或取消文章的重点目标标记
    """
    es = get_es()
    if not es:
        return ApiResponseSchema.error(code=500, message="Elasticsearch连接未初始化")
    
    try:
        current_time = datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
        if data.is_highlighted:
            update_data = {
                "is_highlighted": True,
                "highlighted_at": current_time,
                "highlight_reason": data.highlight_reason,
                "update_at": current_time
            }
        else:
            update_data = {
                "is_highlighted": False,
                "highlighted_at": None,
                "highlight_reason": None,
                "update_at": current_time
            }
        
        await es.update(
            index="article",
            id=uuid,
            body={"doc": update_data}
        )
        
        logger.info(f"成功更新文章标记状态: {uuid}, is_highlighted={data.is_highlighted}")
        return ApiResponseSchema.success(data={"message": "标记状态更新成功"})
    
    except NotFoundError:
        return ApiResponseSchema.error(code=404, message=f"文章不存在，UUID: {uuid}")
    except Exception as e:
        logger.error(f"更新文章标记状态失败: {e}", exc_info=True)
        return ApiResponseSchema.error(code=500, message=f"更新标记状态失败: {str(e)}")