from datetime import datetime
from fastapi import APIRouter, Depends, Path

from app.db.elasticsearch import get_es
from app.schemas.constants import EntityType
from app.schemas.general import PageParamsSchema, PageResponseSchema
from app.schemas.response import ApiResponseSchema
from app.schemas.timeline import TimelineDiffCompareResponseSchema, TimelineResponseSchema
from app.utils.date_time import parse_datetime


router = APIRouter(
    prefix="/timeline",
    tags=["时间线"],
)


@router.get("/{entity_type}/{source_id}", response_model=PageResponseSchema[TimelineResponseSchema], summary="获取指定source_id的所有时间线数据")
async def get_timeline(
    entity_type: EntityType = Path(..., description="实体类型：article 或 forum"),
    source_id: str = Path(..., description="实体source_id"),
    params: PageParamsSchema = Depends(),
):
    es = get_es()
    if not es:
        return ApiResponseSchema.error(code=500, message="Elasticsearch连接未初始化")

    index_name = entity_type.value
    from_ = (params.page - 1) * params.page_size
    query_body = {
        "query": {
            "bool": {
                "filter": [
                    {"term": {"source_id.keyword": source_id}}
                ],
                "must_not": [{"term": {"thread_type": "featured"}}]
            }
        },
        "sort": [{"crawled_at": {"order": "desc", "missing": "_last"}}],
        "from": from_,
        "size": params.page_size
    }
    result = await es.search(index=index_name, body=query_body)
    total = result["hits"]["total"]["value"]
    hits = result["hits"]["hits"]

    items = []
    for hit in hits:
        source_data = hit.get("_source", {})
        raw_entity_type = source_data.get("entity_type", entity_type.value)
        try:
            doc_entity_type = EntityType(raw_entity_type) if raw_entity_type else entity_type
        except ValueError:
            doc_entity_type = entity_type
        last_edit_at = parse_datetime(source_data.get("last_edit_at")) or parse_datetime(source_data.get("update_at")) or parse_datetime(source_data.get("crawled_at"))
        if last_edit_at is None:
            last_edit_at = datetime.min
        items.append(TimelineResponseSchema(
            uuid=source_data.get("uuid", hit.get("_id", "")),
            entity_type=doc_entity_type,
            source_id=source_data.get("source_id", source_id),
            last_edit_at=last_edit_at,
            crawled_at=parse_datetime(source_data.get("crawled_at")),
            title=source_data.get("title", ""),
            clean_content=source_data.get("clean_content"),
            confidence=source_data.get("confidence"),
            is_highlighted=source_data.get("is_highlighted"),
            highlight_reason=source_data.get("highlight_reason"),
        ))

    return PageResponseSchema.create(items=items, total=total, page=params.page, page_size=params.page_size)

@router.get("/{entity_type}/{uuid}/diff-compare", response_model=ApiResponseSchema[TimelineDiffCompareResponseSchema], summary="获取指定uuid的raw_content用于变更对比")
async def get_timeline_diff_compare(
    entity_type: EntityType = Path(..., description="实体类型：article 或 forum"),
    uuid: str = Path(..., description="实体uuid"),
):
    es = get_es()
    if not es:
        return ApiResponseSchema.error(code=500, message="Elasticsearch连接未初始化")

    index_name = entity_type.value
    result = await es.get(index=index_name, id=uuid, _source_includes=["raw_content", "last_edit_at", "title"])
    source_data = result.get("_source", {})
    last_edit_at = parse_datetime(source_data.get("last_edit_at")) or parse_datetime(source_data.get("update_at")) or parse_datetime(source_data.get("crawled_at"))
    return ApiResponseSchema.success(data=TimelineDiffCompareResponseSchema(
        raw_content=source_data.get("raw_content", ""),
        last_edit_at=last_edit_at,
        title=source_data.get("title", ""),
    ))