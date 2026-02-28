import logging
from fastapi import APIRouter, Query, Depends
from elasticsearch.exceptions import NotFoundError

from app.db.elasticsearch import get_es
from app.schemas.forum import ForumSchema, CommentResultSchema
from app.schemas.response import ApiResponseSchema
from app.schemas.general import PageParamsSchema, PageResponseSchema
from app.models.platform.platform import PlatformModel
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
        platform_uuid = None
        if platform:
            try:
                platform_obj = await PlatformModel.find_one({"name": platform})
                if platform_obj:
                    platform_uuid = platform_obj.id
            except Exception as e:
                logger.warning(f"查询平台UUID失败: {e}, platform_name: {platform}")
        
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
                # logger.info(f"查询论坛详情: {query_body}")
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
            platform_uuid=platform_uuid,
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
            translate_content=source_data.get("translate_content"),
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


@router.get("/comments", response_model=PageResponseSchema[CommentResultSchema], summary="查询评论或点评")
async def get_comments(
    platform: str = Query(..., description="平台名称"),
    source_id: str = Query(..., description="父级source_id"),
    thread_type: str = Query(default="comment", description="帖子类型，comment(评论) 或 featured(点评)"),
    params: PageParamsSchema = Depends()
):
    es = get_es()
    if not es:
        return ApiResponseSchema.error(code=500, message="Elasticsearch连接未初始化")
    
    if thread_type not in ["comment", "featured"]:
        return ApiResponseSchema.error(code=400, message="thread_type参数只能是comment或featured")
    
    platform_id = None
    try:
        platform_obj = await PlatformModel.find_one({"name": platform})
        if platform_obj:
            platform_id = platform_obj.id
    except Exception as e:
        logger.warning(f"查询平台ID失败: {e}, platform_name: {platform}")

    try:
        query_body = {
            "query": {
                "bool": {
                    "must": [
                        {"term": {"platform.keyword": platform}},
                        {"term": {"parent_id.keyword": source_id}},
                        {"term": {"thread_type.keyword": thread_type}}
                    ]
                }
            },
            "aggs": {
                "dedup_groups": {
                    "terms": {
                        **(
                            {
                                "script": {
                                    "source": (
                                        "String sid = doc['source_id.keyword'].size() > 0 ? doc['source_id.keyword'].value : '_';"
                                        "String fl = doc['floor'].size() > 0 ? String.valueOf((long)doc['floor'].value) : '0';"
                                        "return sid + '|' + fl;"
                                    )
                                }
                            }
                            if thread_type == "featured"
                            else {"field": "source_id.keyword"}
                        ),
                        "size": 10000
                    },
                    "aggs": {
                        "latest": {
                            "top_hits": {
                                "sort": [{"last_edit_at": {"order": "desc", "missing": "_last"}}],
                                "size": 1
                            }
                        },
                        "floor_val": {
                            "max": {"field": "floor"}
                        }
                    }
                }
            },
            "size": 0
        }
        
        logger.info(f"查询论坛{thread_type}: platform={platform}, source_id={source_id}, page={params.page}, page_size={params.page_size}")
        result = await es.search(index="forum", body=query_body)
        buckets = result.get("aggregations", {}).get("dedup_groups", {}).get("buckets", [])
        
        buckets.sort(key=lambda b: (b.get("floor_val", {}).get("value") is None, b.get("floor_val", {}).get("value") or 0))
        
        total = len(buckets)
        start = (params.page - 1) * params.page_size
        page_buckets = buckets[start: start + params.page_size]
        
        search_results = []
        for bucket in page_buckets:
            latest_hit = bucket["latest"]["hits"]["hits"][0]
            source_data = latest_hit.get("_source", {})
            
            search_result = CommentResultSchema(
                uuid=source_data.get("uuid", latest_hit.get("_id", "")),
                entity_type=source_data.get("entity_type", ""),
                source_id=source_data.get("source_id", ""),
                data_version=source_data.get("data_version", 0),
                platform=source_data.get("platform") or "",
                platform_id=platform_id,
                section=source_data.get("section", ""),
                update_at=parse_datetime(source_data.get("update_at")),
                author_uuid=None,
                author_name=source_data.get("author_name", ""),
                nsfw=source_data.get("nsfw", False),
                aigc=source_data.get("aigc", False),
                keywords=source_data.get("keywords", []),
                clean_content=source_data.get("clean_content"),
                confidence=source_data.get("confidence", 1),
                is_highlighted=source_data.get("is_highlighted"),
                floor=source_data.get("floor")
            )
            search_results.append(search_result)
        
        return PageResponseSchema.create(
            items=search_results,
            total=total,
            page=params.page,
            page_size=params.page_size
        )
    
    except Exception as e:
        logger.error(f"查询论坛{thread_type}失败: {e}", exc_info=True)
        return ApiResponseSchema.error(code=500, message=f"查询失败: {str(e)}")

