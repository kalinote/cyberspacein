import json
from datetime import datetime
from loguru import logger
from app.core.config import settings
from app.models.action.action import ActionInstanceModel
from app.utils.async_fetch import async_get, async_post, unwrap_response
from app.models.action.component_run import ComponentRunModel
from app.schemas.constants import ActionFlowStatusEnum, ComponentRunStatusEnum

logger = logger.bind(name=__name__)

# TODO(native-scheduler): 自研 Worker 上线后删除 Crawlab 资源查询和派发调用；
# CSI 的 Action 调度和 ComponentRun 数据保持不变。

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
    
async def run_component(
    component_id: str,
    command: str,
    command_args: list[str],
    priority: int = 5,
):
    try:
        url = settings.CRAWLAB_BASE_URL + f"/spiders/{component_id}/run"
        response = await async_post(
            url,
            data={
                "cmd": command,
                "param": " ".join(command_args),
                "mode": "random",
                "priority": priority
            },
            headers={"Authorization": settings.CRAWLAB_TOKEN}
        )
        return unwrap_response(response)
    except Exception as e:
        logger.error(f"运行组件失败: {e}")
        return None


async def cancel_component_run(component_run: ComponentRunModel) -> bool:
    """请求 Crawlab 立即终止组件对应的运行任务。"""
    platform_task_id = component_run.platform_task_id
    if not platform_task_id and component_run.dispatch_ref:
        dispatch_parts = component_run.dispatch_ref.rsplit(":", 1)
        if len(dispatch_parts) == 2 and dispatch_parts[1] != component_run.id:
            platform_task_id = dispatch_parts[1]
    if not platform_task_id:
        logger.warning(f"组件运行缺少平台任务ID，无法主动停止: {component_run.id}")
        return False
    try:
        response = await async_post(
            settings.CRAWLAB_BASE_URL + f"/tasks/{platform_task_id}/cancel",
            data={},
            headers={"Authorization": settings.CRAWLAB_TOKEN},
            timeout=5,
        )
        if response is None or (
            isinstance(response, dict)
            and response.get("code") not in {None, 0, 200}
        ):
            logger.error(f"停止组件平台任务失败: {component_run.id}, 响应: {response}")
            return False
        return True
    except Exception as e:
        logger.error(f"停止组件平台任务失败: {component_run.id}, 错误: {e}")
        return False


async def dispatch_component_run(
    component_run: ComponentRunModel,
    command: str,
    command_args: list[str],
    priority: int = 5,
) -> bool:
    # TODO(native-scheduler): Crawlab 仅用于开发阶段临时派发。自研 Worker
    # 接管组件运行后，用内部任务队列替换本函数实现并删除 Crawlab 配置。
    action = await ActionInstanceModel.find_one({"_id": component_run.action_id})
    if action is not None and action.status == ActionFlowStatusEnum.PAUSED:
        return False
    if action is None or action.status != ActionFlowStatusEnum.RUNNING:
        component_run.status = ComponentRunStatusEnum.CANCELLED
        component_run.cancel_requested = True
        component_run.error_message = "行动已结束，组件不再派发"
        component_run.finished_at = datetime.now()
        component_run.updated_at = datetime.now()
        await component_run.save()
        return False
    dispatch_key = f"component-run:{component_run.id}"
    now = datetime.now()
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
                "lease_expires_at": None,
                "updated_at": now,
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

    result = await run_component(
        component_run.component_id,
        command,
        command_args,
        priority=priority,
    )
    component_run = await ComponentRunModel.find_one({"_id": component_run.id})
    if component_run is None:
        return False
    if result is None:
        now = datetime.now()
        await ComponentRunModel.find_one(
            {
                "_id": component_run.id,
                "status": {
                    "$in": [
                        ComponentRunStatusEnum.DISPATCHED,
                        ComponentRunStatusEnum.RUNNING,
                    ]
                },
            }
        ).update(
            {
                "$set": {
                    "status": ComponentRunStatusEnum.FAILED,
                    "error_message": "Crawlab 未接受组件运行任务",
                    "finished_at": now,
                    "updated_at": now,
                }
            }
        )
        return False
    update_fields = {"updated_at": datetime.now()}
    if isinstance(result, dict):
        platform_ref = str(
            result.get("_id") or result.get("id") or result.get("task_id") or ""
        ) or None
        if platform_ref:
            update_fields.update(
                {
                    "platform_task_id": platform_ref,
                    "dispatch_ref": f"{dispatch_key}:{platform_ref}",
                }
            )
    await ComponentRunModel.find_one({"_id": component_run.id}).update(
        {"$set": update_fields}
    )
    component_run = await ComponentRunModel.find_one({"_id": component_run.id})
    if component_run is None:
        return False
    if (
        component_run.cancel_requested
        or component_run.status
        not in {ComponentRunStatusEnum.DISPATCHED, ComponentRunStatusEnum.RUNNING}
    ):
        await cancel_component_run(component_run)
        return False
    return True
