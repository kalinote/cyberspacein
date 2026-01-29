import logging
from datetime import datetime
from fastapi import APIRouter, Path
from elasticsearch.exceptions import NotFoundError

from app.db.elasticsearch import get_es
from app.schemas.constants import ENTITY_TYPE_NAMES, EntityType
from app.schemas.highlight import HighlightRequestSchema
from app.schemas.response import ApiResponseSchema

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/highlight",
    tags=["highlight"],
)


@router.put("/{entity_type}/{uuid}", response_model=ApiResponseSchema[dict], summary="设置/取消重点目标标记")
async def set_highlight(
    entity_type: EntityType = Path(..., description="实体类型：article 或 forum"),
    uuid: str = Path(..., description="实体UUID"),
    data: HighlightRequestSchema = ...
):
    """
    设置或取消实体的重点目标标记，支持 article（文章）和 forum（论坛）两种类型
    """
    es = get_es()
    if not es:
        return ApiResponseSchema.error(code=500, message="Elasticsearch连接未初始化")
    
    entity_name = ENTITY_TYPE_NAMES.get(entity_type, entity_type.value)
    
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
            index=entity_type.value,
            id=uuid,
            body={"doc": update_data}
        )
        
        logger.info(f"成功更新{entity_name}标记状态: {uuid}, is_highlighted={data.is_highlighted}")
        return ApiResponseSchema.success(data={"message": "标记状态更新成功"})
    
    except NotFoundError:
        return ApiResponseSchema.error(code=404, message=f"{entity_name}不存在，UUID: {uuid}")
    except Exception as e:
        logger.error(f"更新{entity_name}标记状态失败: {e}", exc_info=True)
        return ApiResponseSchema.error(code=500, message=f"更新标记状态失败: {str(e)}")
