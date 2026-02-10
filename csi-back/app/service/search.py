import asyncio
import logging

from app.schemas.search import EntitySearchRequestSchema, SearchResultSchema
from app.schemas.constants import ALL_INDEX, SearchModeEnum
from app.schemas.general import PageResponseSchema
from app.core.config import settings
from app.models.platform.platform import PlatformModel
from app.utils.date_time import parse_datetime
from app.utils.search import merge_highlight_tags, has_keywords, rrf_merge
from app.utils.embedding import embed_query_async

logger = logging.getLogger(__name__)


def _get_es_total(result: dict) -> int:
    total = result["hits"]["total"]
    return total["value"] if isinstance(total, dict) else total


def build_filter_must(params: EntitySearchRequestSchema) -> list:
    must = []
    if params.platform:
        must.append({"term": {"platform.keyword": params.platform}})
    if params.author:
        must.append({"term": {"author_name.keyword": params.author}})
    if params.aigc is not None:
        must.append({"term": {"aigc": params.aigc}})
    if params.nsfw is not None:
        must.append({"term": {"nsfw": params.nsfw}})
    if params.is_highlighted is not None:
        must.append({"term": {"is_highlighted": params.is_highlighted}})
    return must


async def hit_to_search_result(hit: dict) -> SearchResultSchema:
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
    title = (merge_highlight_tags(title) or "") if title is not None else ""
    clean_content = source_data.get("clean_content")
    if highlight_data.get("clean_content"):
        clean_content = merge_highlight_tags(highlight_data["clean_content"][0])
    keywords_hits = 0
    if highlight_data:
        for fragments in highlight_data.values():
            for fragment in fragments:
                keywords_hits += fragment.count("<em>")
    return SearchResultSchema(
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


async def hits_to_search_results(hits: list) -> list[SearchResultSchema]:
    return await asyncio.gather(*[hit_to_search_result(h) for h in hits])


async def search_filter_only(es, params: EntitySearchRequestSchema) -> PageResponseSchema[SearchResultSchema]:
    filter_must = build_filter_must(params)
    query = {
        "bool": {
            "must": [{"match_all": {}}],
            "filter": filter_must if filter_must else []
        }
    }
    from_ = (params.page - 1) * params.page_size
    query_body = {
        "query": query,
        "from": from_,
        "size": params.page_size
    }
    if params.sort_by == "relevance":
        pass
    elif params.sort_by in ["crawled_at", "last_edit_at"]:
        sort_order = params.sort_order if params.sort_order in ["asc", "desc"] else "desc"
        query_body["sort"] = [{params.sort_by: {"order": sort_order, "missing": "_last"}}]
    else:
        query_body["sort"] = [{"crawled_at": {"order": "desc", "missing": "_last"}}]
    result = await es.search(index=ALL_INDEX, body=query_body)
    total = _get_es_total(result)
    hits = result["hits"]["hits"]
    items = await hits_to_search_results(hits)
    return PageResponseSchema.create(items=items, total=total, page=params.page, page_size=params.page_size)


async def search_keyword(es, params: EntitySearchRequestSchema) -> PageResponseSchema[SearchResultSchema]:
    from_ = (params.page - 1) * params.page_size
    query_body = keyword_query_body(params, from_, params.page_size)
    result = await es.search(index=ALL_INDEX, body=query_body)
    total = _get_es_total(result)
    hits = result["hits"]["hits"]
    items = await hits_to_search_results(hits)
    return PageResponseSchema.create(items=items, total=total, page=params.page, page_size=params.page_size)


def keyword_query_body(params: EntitySearchRequestSchema, from_: int, size: int) -> dict:
    query_must = []
    if has_keywords(params.keywords):
        query_must.append({
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
        })
    filter_must = build_filter_must(params)
    for c in filter_must:
        query_must.append(c)
    body = {
        "query": {"bool": {"must": query_must if query_must else [{"match_all": {}}]}},
        "from": from_,
        "size": size
    }
    if has_keywords(params.keywords):
        body["highlight"] = {
            "pre_tags": ["<em>"],
            "post_tags": ["</em>"],
            "fields": {"title": {}, "clean_content": {"fragment_size": 200, "number_of_fragments": 3}}
        }
    if params.sort_by == "relevance":
        pass
    elif params.sort_by in ["crawled_at", "last_edit_at"]:
        sort_order = params.sort_order if params.sort_order in ["asc", "desc"] else "desc"
        body["sort"] = [{params.sort_by: {"order": sort_order, "missing": "_last"}}]
    else:
        body["sort"] = [{"crawled_at": {"order": "desc", "missing": "_last"}}]
    return body


async def search_vector(es, params: EntitySearchRequestSchema, query_vector: list[float]) -> PageResponseSchema[SearchResultSchema]:
    filter_must = build_filter_must(params)
    from_ = (params.page - 1) * params.page_size
    size = params.page_size
    k = max(from_ + size, 10)
    num_candidates = min(10000, max(k * settings.VECTOR_NUM_CANDIDATES_MULTIPLIER, 100))
    knn = {
        "field": "clean_content_vector",
        "query_vector": query_vector,
        "k": k,
        "num_candidates": num_candidates
    }
    if filter_must:
        knn["filter"] = {"bool": {"must": filter_must}}
    query_body = {
        "query": {"knn": knn},
        "from": from_,
        "size": size
    }
    result = await es.search(index=ALL_INDEX, body=query_body)
    total = _get_es_total(result)
    hits = result["hits"]["hits"]
    items = await hits_to_search_results(hits)
    return PageResponseSchema.create(items=items, total=total, page=params.page, page_size=params.page_size)


async def search_entity(es, params: EntitySearchRequestSchema, instruct: str = "") -> PageResponseSchema[SearchResultSchema]:
    if not has_keywords(params.keywords):
        return await search_filter_only(es, params)

    if params.search_mode == SearchModeEnum.KEYWORD:
        return await search_keyword(es, params)

    if params.search_mode == SearchModeEnum.VECTOR:
        query_vector = await embed_query_async(params.keywords, instruct)
        return await search_vector(es, params, query_vector)

    if params.search_mode == SearchModeEnum.HYBRID:
        query_vector = await embed_query_async(params.keywords, instruct)
        hybrid_size = min(settings.HYBRID_TOTAL_CAP, max((params.page * params.page_size) + 200, 500))
        keyword_body = keyword_query_body(params, 0, hybrid_size)
        filter_must = build_filter_must(params)
        vec_k = hybrid_size
        vec_num_candidates = min(10000, max(vec_k * settings.VECTOR_NUM_CANDIDATES_MULTIPLIER, 100))
        knn = {
            "field": "clean_content_vector",
            "query_vector": query_vector,
            "k": vec_k,
            "num_candidates": vec_num_candidates
        }
        if filter_must:
            knn["filter"] = {"bool": {"must": filter_must}}
        vector_body = {"query": {"knn": knn}, "from": 0, "size": hybrid_size}

        kw_result, vec_result = await asyncio.gather(
            es.search(index=ALL_INDEX, body=keyword_body),
            es.search(index=ALL_INDEX, body=vector_body)
        )

        kw_total = _get_es_total(kw_result)
        vec_total = _get_es_total(vec_result)
        keyword_hits = kw_result["hits"]["hits"]
        vector_hits = vec_result["hits"]["hits"]
        merged = rrf_merge(keyword_hits, vector_hits, settings.RRF_K)
        from_ = (params.page - 1) * params.page_size
        page_hits = merged[from_: from_ + params.page_size]
        total_estimate = min(settings.HYBRID_TOTAL_CAP, kw_total + vec_total)
        items = await hits_to_search_results(page_hits)
        return PageResponseSchema.create(
            items=items,
            total=total_estimate,
            page=params.page,
            page_size=params.page_size
        )

    return await search_keyword(es, params)
