import json
from datetime import datetime, timedelta
from loguru import logger
from app.core.config import settings
from app.utils.async_fetch import async_get, async_post, unwrap_response
from app.models.action.component_run import ComponentRunModel
from app.schemas.constants import ComponentRunStatusEnum

logger = logger.bind(name=__name__)

# TODO(native-scheduler): 自研调度上线后删除本模块中的 Crawlab 资源、任务、
# 调度计划查询和派发调用；CSI 的 ComponentRun 数据届时保持不变。

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


async def dispatch_component_run(
    component_run: ComponentRunModel,
    command: str,
    command_args: list[str],
) -> bool:
    # TODO(native-scheduler): Crawlab 仅用于开发阶段临时派发。自研 Worker
    # 接管组件运行后，用内部任务队列替换本函数实现并删除 Crawlab 配置。
    dispatch_key = f"component-run:{component_run.id}"
    claim = await ComponentRunModel.find_one(
        {
            "_id": component_run.id,
            "status": ComponentRunStatusEnum.CREATED,
            "cancel_requested": False,
        }
    ).update(
        {
            "$set": {
                "status": ComponentRunStatusEnum.DISPATCHED,
                "dispatch_ref": dispatch_key,
                "lease_expires_at": datetime.now()
                + timedelta(seconds=settings.COMPONENT_RUN_TIMEOUT_SECONDS),
                "updated_at": datetime.now(),
            }
        }
    )
    if not claim or getattr(claim, "modified_count", 0) != 1:
        current = await ComponentRunModel.find_one({"_id": component_run.id})
        return bool(
            current
            and current.status
            in {ComponentRunStatusEnum.DISPATCHED, ComponentRunStatusEnum.RUNNING}
        )

    result = await run_component(component_run.component_id, command, command_args)
    component_run = await ComponentRunModel.find_one({"_id": component_run.id})
    if result is None:
        component_run.status = ComponentRunStatusEnum.FAILED
        component_run.error_message = "Crawlab 未接受组件运行任务"
        component_run.finished_at = datetime.now()
        component_run.updated_at = datetime.now()
        await component_run.save()
        return False
    if isinstance(result, dict):
        platform_ref = str(
            result.get("_id") or result.get("id") or result.get("task_id") or ""
        ) or None
        if platform_ref:
            component_run.dispatch_ref = f"{dispatch_key}:{platform_ref}"
    component_run.updated_at = datetime.now()
    await component_run.save()
    return True
    
async def get_base_component_tasks(page: int = 1, page_size: int = 10):
    try:
        url = settings.CRAWLAB_BASE_URL + "/tasks"
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
        if not isinstance(response, dict):
            return None, 0
        data = response.get("data")
        raw_total = response.get("total", 0)
        total = int(raw_total) if raw_total is not None else 0
        if data is None:
            return None, 0
        data = data if isinstance(data, list) else []

        component_names = await async_get(
            settings.CRAWLAB_BASE_URL + "/filters/spiders",
            headers={"Authorization": settings.CRAWLAB_TOKEN}
        )

        component_names_data = unwrap_response(component_names) or []

        component_map = {
            item["value"]: item["label"]
            for item in (component_names_data if isinstance(component_names_data, list) else [])
            if isinstance(item, dict) and item.get("value")
        }

        schedules_res = await async_get(
            settings.CRAWLAB_BASE_URL + "/filters/schedules",
            headers={"Authorization": settings.CRAWLAB_TOKEN}
        )
        schedules_data = unwrap_response(schedules_res) or []
        schedule_map = {
            item["value"]: item["label"]
            for item in (schedules_data if isinstance(schedules_data, list) else [])
            if isinstance(item, dict) and item.get("value")
        }

        tasks = data
        for task in tasks:
            if not isinstance(task, dict):
                continue
            spider_id = task.get("spider_id")
            if spider_id and spider_id in component_map:
                task["component_name"] = component_map[spider_id]
            schedule_id = task.get("schedule_id")
            if schedule_id and schedule_id in schedule_map:
                task["schedule_name"] = schedule_map[schedule_id]

        return tasks, total
    except Exception as e:
        logger.error(f"获取基础组件任务列表失败: {e}")
        return None, 0
    
async def get_base_component_schedules(page: int = 1, page_size: int = 10):
    try:
        url = settings.CRAWLAB_BASE_URL + "/schedules"
        response = await async_get(
            url,
            params={
                "page": page,
                "size": page_size,
                "sort": "[]"
            },
            headers={"Authorization": settings.CRAWLAB_TOKEN}
        )
        if not isinstance(response, dict):
            return None, 0
        data = response.get("data")
        raw_total = response.get("total", 0)
        total = int(raw_total) if raw_total is not None else 0
        if data is None:
            return None, 0
        data = data if isinstance(data, list) else []

        component_names = await async_get(
            settings.CRAWLAB_BASE_URL + "/filters/spiders",
            headers={"Authorization": settings.CRAWLAB_TOKEN}
        )
        component_names_data = unwrap_response(component_names) or []
        component_map = {
            item["value"]: item["label"]
            for item in (component_names_data if isinstance(component_names_data, list) else [])
            if isinstance(item, dict) and item.get("value")
        }

        for schedule in data:
            if not isinstance(schedule, dict):
                continue
            spider_id = schedule.get("spider_id")
            if spider_id and spider_id in component_map:
                schedule["component_name"] = component_map[spider_id]

        return data, total
    except Exception as e:
        logger.error(f"获取基础组件调度计划列表失败: {e}")
        return None, 0
