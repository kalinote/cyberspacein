import json
import logging
from app.core.config import settings
from app.utils.async_fetch import async_get, async_post, unwrap_response

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
        data = unwrap_response(response)
        if data and isinstance(data, list) and len(data) > 0:
            return data[0]["_id"]
        return None
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