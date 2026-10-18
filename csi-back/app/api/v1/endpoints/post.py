from elasticsearch.exceptions import NotFoundError
from fastapi import APIRouter
from loguru import logger

from app.db.elasticsearch import get_es
from app.models.platform.platform import PlatformModel
from app.schemas.post import PostSchema
from app.schemas.response import ApiResponseSchema
from app.utils.date_time import parse_datetime
from app.utils.entity_entities import parse_entities


router = APIRouter(prefix="/post", tags=["贴文"])


@router.get("/detail/{uuid}", response_model=ApiResponseSchema[PostSchema], summary="获取贴文详情")
async def get_post_detail(uuid: str):
    """读取贴文及媒体结果，按系统标准平台名称关联来源平台。

    Args:
        uuid: Elasticsearch 中贴文的唯一标识。

    Returns:
        ApiResponseSchema: 贴文详情，或系统统一的未找到和查询失败响应。
    """
    es = get_es()
    if not es:
        return ApiResponseSchema.error(code=250001, message="Elasticsearch连接未初始化")

    try:
        result = await es.get(index="post", id=uuid)
        source = result.get("_source", {})
        data = {**source, "uuid": source.get("uuid") or uuid, "entity_type": "post", "platform_uuid": None}
        if source.get("platform"):
            try:
                platform = await PlatformModel.find_one({"name": source["platform"]})
                if platform:
                    data["platform_uuid"] = platform.id
            except Exception as exc:
                logger.warning("查询贴文来源平台失败: {}", exc)
        for field in ("update_at", "crawled_at", "publish_at", "last_edit_at", "highlighted_at"):
            data[field] = parse_datetime(source.get(field))
        data["entities"] = parse_entities(source.get("entities"))
        return ApiResponseSchema.success(data=PostSchema.model_validate(data))
    except NotFoundError:
        return ApiResponseSchema.error(code=240415, message=f"贴文不存在，UUID: {uuid}")
    except Exception:
        logger.exception("查询贴文详情失败")
        return ApiResponseSchema.error(code=250002, message="查询贴文详情失败，请稍后重试")
