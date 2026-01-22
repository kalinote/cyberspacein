import logging
from datetime import datetime
from fastapi import APIRouter
from elasticsearch.exceptions import NotFoundError

from app.db.elasticsearch import get_es
from app.schemas.forum import ForumSchema
from app.schemas.highlight import HighlightRequestSchema
from app.schemas.response import ApiResponseSchema
from app.utils.date_time import parse_datetime

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/forum",
    tags=["forum"],
)

@router.get("/detail/{uuid}", response_model=ApiResponseSchema[ForumSchema], summary="获取论坛详情")
async def get_forum_detail(uuid: str):
    es = get_es()
    if not es:
        return ApiResponseSchema.error(code=500, message="Elasticsearch连接未初始化")
    
    try:
        result = await es.get(index="forum", id=uuid)
        source_data = result.get("_source", {})
        
        platform = source_data.get("platform")
        topic_id = source_data.get("topic_id")
        topic_thread_uuid = None
        
        if platform and topic_id:
            try:
                query_body = {
                    "query": {
                        "bool": {
                            "must": [
                                {"term": {"platform.keyword": platform}},
                                {"term": {"topic_id.keyword": topic_id}},
                                {"term": {"thread_type.keyword": "thread"}}
                            ]
                        }
                    },
                    "sort": [
                        {
                            "last_edit_at": {
                                "order": "desc",
                                "missing": "_last"
                            }
                        }
                    ],
                    "size": 1,
                    "_source": ["uuid"]
                }
                logger.info(f"查询论坛详情: {query_body}")
                search_result = await es.search(index="forum", body=query_body)
                hits = search_result.get("hits", {}).get("hits", [])
                if hits:
                    topic_thread_uuid = hits[0].get("_source", {}).get("uuid")
            except Exception:
                topic_thread_uuid = None
        
        forum_data = ForumSchema(
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
            clean_content=source_data.get("clean_content"),
            raw_content=source_data.get("raw_content"),
            safe_raw_content=source_data.get("safe_raw_content"),
            topic_id=source_data.get("topic_id"),
            parent_id=source_data.get("parent_id"),
            floor=source_data.get("floor"),
            thread_type=source_data.get("thread_type"),
            category_tag=source_data.get("category_tag"),
            title=source_data.get("title"),
            files_urls=source_data.get("files_urls"),
            status_flags=source_data.get("status_flags"),
            likes=source_data.get("likes"),
            dislikes=source_data.get("dislikes"),
            collections=source_data.get("collections"),
            comments=source_data.get("comments"),
            views=source_data.get("views"),
            topic_thread_uuid=topic_thread_uuid,
            is_highlighted=source_data.get("is_highlighted", False),
            highlighted_at=parse_datetime(source_data.get("highlighted_at")),
            highlight_reason=source_data.get("highlight_reason")
        )
        
        return ApiResponseSchema.success(data=forum_data)
    
    except NotFoundError:
        return ApiResponseSchema.error(code=404, message=f"论坛不存在，UUID: {uuid}")
    except Exception as e:
        return ApiResponseSchema.error(code=500, message=f"查询论坛详情失败: {str(e)}")

@router.put("/highlight/{uuid}", response_model=ApiResponseSchema[dict], summary="设置/取消重点目标标记")
async def set_forum_highlight(uuid: str, data: HighlightRequestSchema):
    """
    设置或取消论坛的重点目标标记
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
            index="forum",
            id=uuid,
            body={"doc": update_data}
        )
        
        logger.info(f"成功更新论坛标记状态: {uuid}, is_highlighted={data.is_highlighted}")
        return ApiResponseSchema.success(data={"message": "标记状态更新成功"})
    
    except NotFoundError:
        return ApiResponseSchema.error(code=404, message=f"论坛不存在，UUID: {uuid}")
    except Exception as e:
        logger.error(f"更新论坛标记状态失败: {e}", exc_info=True)
        return ApiResponseSchema.error(code=500, message=f"更新标记状态失败: {str(e)}")
