import json
import logging
from app.core.config import settings
from app.utils.async_fetch import async_get, async_post, unwrap_response

logger = logging.getLogger(__name__)

async def get_components(page: int = 1, page_size: int = 10):
    try:
        url = settings.CRAWLAB_BASE_URL + "/spiders"
        response = await async_get(
            url,
            params={
                "page": page,
                "size": page_size,
                "sort": json.dumps([]),
                "stats": "true"
            },
            headers={"Authorization": settings.CRAWLAB_TOKEN}
        )
        data = unwrap_response(response)
        return data if data is not None else None
    except Exception as e:
        logger.error(f"获取组件失败: {e}")
        return None
    
async def run_component(component_id: str, command: str, command_args: list[str]):
    try:
        url = settings.CRAWLAB_BASE_URL + f"/spiders/{component_id}/run"
        response = await async_post(
            url,
            data={
                "cmd": command,
                "param": " ".join(command_args),
                "mode": "random",
                "priority": 5
            },
            headers={"Authorization": settings.CRAWLAB_TOKEN}
        )
        return unwrap_response(response)
    except Exception as e:
        logger.error(f"运行组件失败: {e}")
        return None
    
async def get_base_component_tasks(page: int = 1, page_size: int = 10):
    try:
        url = settings.CRAWLAB_BASE_URL + f"/tasks"
        response = await async_get(
            url,
            params={
                "page": page,
                "size": page_size,
                "stats": "true",
                "sort": "[]"
            },
            headers={"Authorization": settings.CRAWLAB_TOKEN}
        )
        return unwrap_response(response)
    except Exception as e:
        logger.error(f"获取基础组件任务列表失败: {e}")
        return None