import logging
from fastapi import APIRouter

from app.schemas.search import EntitySearchRequestSchema, SearchResultSchema
from app.schemas.general import PageResponseSchema
from app.schemas.response import ApiResponseSchema
from app.schemas.enum import ALL_INDEX
from app.db.elasticsearch import get_es
from app.models.platform.platform import PlatformModel
from app.utils.date_time import parse_datetime
from app.utils.search import merge_highlight_tags

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/search",
    tags=["search"],
)

@router.post("/entity", response_model=PageResponseSchema[SearchResultSchema], summary="搜索实体")
async def search_entity(params: EntitySearchRequestSchema):
    """
    搜索实体接口，支持从多个索引中搜索，并提供关键词搜索和多种过滤条件
    """
    es = get_es()
    if not es:
        return ApiResponseSchema.error(code=500, message="Elasticsearch连接未初始化")
    
    try:
        query_must = []
        
        if params.keywords:
            keyword_query = {
                "bool": {
                    "should": [
                        {"match": {"title": params.keywords}},
                        {"match": {"clean_content": params.keywords}},
                        {"match": {"raw_content": params.keywords}},
                        {"term": {"keywords": params.keywords}},
                        {"term": {"author_name": params.keywords}}
                    ],
                    "minimum_should_match": 1
                }
            }
            query_must.append(keyword_query)
        
        if params.platform:
            query_must.append({"term": {"platform": params.platform}})
        
        if params.author:
            query_must.append({"term": {"author_name": params.author}})
        
        if params.aigc is not None:
            query_must.append({"term": {"aigc": params.aigc}})
        
        if params.nsfw is not None:
            query_must.append({"term": {"nsfw": params.nsfw}})
        
        if params.is_highlighted is not None:
            query_must.append({"term": {"is_highlighted": params.is_highlighted}})
        
        query_body = {
            "query": {
                "bool": {
                    "must": query_must if query_must else [{"match_all": {}}]
                }
            },
            "from": (params.page - 1) * params.page_size,
            "size": params.page_size
        }
        
        if params.keywords:
            query_body["highlight"] = {
                "pre_tags": ["<em>"],
                "post_tags": ["</em>"],
                "fields": {
                    "title": {},
                    "clean_content": {
                        "fragment_size": 200,
                        "number_of_fragments": 3
                    }
                }
            }
        
        if params.sort_by == "relevance":
            pass
        elif params.sort_by in ["crawled_at", "last_edit_at"]:
            sort_order = params.sort_order if params.sort_order in ["asc", "desc"] else "desc"
            query_body["sort"] = [
                {
                    params.sort_by: {
                        "order": sort_order,
                        "missing": "_last"
                    }
                }
            ]
        else:
            query_body["sort"] = [
                {
                    "crawled_at": {
                        "order": "desc",
                        "missing": "_last"
                    }
                }
            ]
        
        result = await es.search(index=ALL_INDEX, body=query_body)
        
        total = result["hits"]["total"]["value"] if isinstance(result["hits"]["total"], dict) else result["hits"]["total"]
        hits = result["hits"]["hits"]
        
        search_results = []
        for hit in hits:
            source_data = hit.get("_source", {})
            highlight_data = hit.get("highlight", {})
            
            platform_name = source_data.get("platform")
            platform_id = None
            if platform_name:
                try:
                    platform = await PlatformModel.find_one({"name": platform_name})
                    if platform:
                        platform_id = platform.id
                except Exception as e:
                    logger.warning(f"查询平台ID失败: {e}, platform_name: {platform_name}")
            
            title = highlight_data.get("title", [source_data.get("title", "")])[0]
            title = merge_highlight_tags(title)
            clean_content = source_data.get("clean_content")
            if highlight_data.get("clean_content"):
                clean_content = merge_highlight_tags(highlight_data["clean_content"][0])
            
            keywords_hits = 0
            if highlight_data:
                for fragments in highlight_data.values():
                    for fragment in fragments:
                        keywords_hits += fragment.count("<em>")
            
            search_result = SearchResultSchema(
                uuid=source_data.get("uuid", hit.get("_id", "")),
                entity_type=source_data.get("entity_type", ""),
                source_id=source_data.get("source_id", ""),
                data_version=source_data.get("data_version", 0),
                platform=platform_name or "",
                platform_id=platform_id,
                section=source_data.get("section", ""),
                update_at=parse_datetime(source_data.get("update_at")),
                author_uuid=None,
                author_name=source_data.get("author_name", ""),
                nsfw=source_data.get("nsfw", False),
                aigc=source_data.get("aigc", False),
                keywords=source_data.get("keywords", []),
                title=title,
                clean_content=clean_content,
                confidence=source_data.get("confidence", 1),
                is_highlighted=source_data.get("is_highlighted"),
                keywords_hits=keywords_hits
            )
            search_results.append(search_result)
        
        return PageResponseSchema.create(
            items=search_results,
            total=total,
            page=params.page,
            page_size=params.page_size
        )
    
    except Exception as e:
        logger.error(f"搜索实体失败: {e}", exc_info=True)
        return ApiResponseSchema.error(code=500, message=f"搜索实体失败: {str(e)}")
