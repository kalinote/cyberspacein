import logging
from datetime import datetime
from fastapi import APIRouter
from elasticsearch.exceptions import NotFoundError

from app.db.elasticsearch import get_es
from app.schemas.forum import ForumSchema
from app.schemas.response import ApiResponseSchema

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
        
        def parse_datetime(value):
            if value is None:
                return None
            if isinstance(value, datetime):
                return value
            if isinstance(value, str):
                try:
                    return datetime.fromisoformat(value.replace('Z', '+00:00'))
                except:
                    try:
                        return datetime.strptime(value, "%Y-%m-%dT%H:%M:%S")
                    except:
                        return None
            return None
        
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
            topic_thread_uuid=topic_thread_uuid
        )
        
        return ApiResponseSchema.success(data=forum_data)
    
    except NotFoundError:
        return ApiResponseSchema.error(code=404, message=f"论坛不存在，UUID: {uuid}")
    except Exception as e:
        return ApiResponseSchema.error(code=500, message=f"查询论坛详情失败: {str(e)}")
