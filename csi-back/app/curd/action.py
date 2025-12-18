import json
import logging
from app.core.config import settings
from app.utils.async_fetch import async_get

logger = logging.getLogger(__name__)

async def get_components_project_by_name(project_name: str):
    try:
        url = settings.CRAWLAB_BASE_URL + "/projects"
        response = await async_get(
            url,
            params={
                "conditions": json.dumps([{"key": "name", "op": "eq", "value": project_name}]),
                "sort": json.dumps([]),
                "stats": "true"
            },
            headers={"Authorization": settings.CRAWLAB_TOKEN}
        )
        return response["data"][0]["_id"]
    except Exception as e:
        logger.error(f"获取组件项目ID失败: {e}")
        return None

async def get_components_by_project_id(project_id: str, page: int = 1, page_size: int = 10):
    try:
        url = settings.CRAWLAB_BASE_URL + "/spiders"
        response = await async_get(
            url,
            params={
                "conditions": json.dumps([{"key": "project_id", "op": "eq", "value": project_id}]),
                "page": page,
                "size": page_size,
                "sort": json.dumps([]),
                "stats": "true"
            },
            headers={"Authorization": settings.CRAWLAB_TOKEN}
        )
        return response["data"]
    except Exception as e:
        logger.error(f"获取组件失败: {e}")
        return None