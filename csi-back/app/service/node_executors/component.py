from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from datetime import datetime

from app.core.config import settings
from app.models.action.action import ActionInstanceModel, ActionInstanceNodeModel
from app.models.action.component_run import ComponentRunModel
from app.models.action.node import ActionNodeModel
from app.models.action.node_execution import ActionNodeExecutionModel
from app.schemas.action.execution import (
    NodeExecutionContext,
    NodeExecutionOutcome,
    NodeExecutionSpec,
    NodeStartResult,
)
from app.schemas.constants import (
    DEFAULT_COMPONENT_COMMAND,
    DEFAULT_COMPONENT_COMMAND_ARGS,
    ComponentRunStatusEnum,
)
from app.service.component.auth import issue_component_bootstrap
from app.service.component.service import (
    cancel_component_run,
    dispatch_component_run,
)
from app.utils.id_lib import generate_id


class ComponentNodeExecutor:
    """通过现有 Crawlab 组件派发门面运行普通节点。"""

    def __init__(
        self,
        get_node_definition: Callable[[str], Awaitable[ActionNodeModel | None]],
    ):
        self._get_node_definition = get_node_definition

    async def start(
        self,
        context: NodeExecutionContext,
        spec: NodeExecutionSpec,
    ) -> NodeStartResult:
        action = await ActionInstanceModel.find_one({"_id": context.action_id})
        node_instance = await ActionInstanceNodeModel.find_one(
            {"_id": context.node_instance_id}
        )
        if action is None or node_instance is None:
            raise RuntimeError("普通节点所属行动或节点实例不存在")
        node_definition = await self._get_node_definition(
            node_instance.definition_id
        )
        if node_definition is None:
            component_config = spec.config.get("component") or {}
            if not component_config:
                raise RuntimeError("普通节点定义不存在且执行快照不完整")
        else:
            component_config = {
                "component_ids": list(node_definition.related_components),
                "component_timeouts": dict(node_definition.component_timeouts),
                "command": node_definition.command,
                "command_args": list(node_definition.command_args),
                **(spec.config.get("component") or {}),
            }
        component_ids = component_config.get("component_ids") or []
        component_timeouts = component_config.get("component_timeouts") or {}

        existing_runs = await ComponentRunModel.find(
            {"node_instance_id": node_instance.id}
        ).to_list()
        existing_by_component = {
            run.component_id: run for run in existing_runs
        }
        component_runs = []
        for component_id in component_ids:
            component_run = existing_by_component.get(component_id)
            if component_run is None:
                component_run = ComponentRunModel(
                    id=generate_id(f"{node_instance.id}:{component_id}:1"),
                    action_id=action.id,
                    node_instance_id=node_instance.id,
                    component_id=component_id,
                    attempt=1,
                    timeout_seconds=(
                        component_timeouts.get(
                            component_id,
                            settings.COMPONENT_RUN_TIMEOUT_SECONDS,
                        )
                        if component_timeouts
                        else settings.COMPONENT_RUN_TIMEOUT_SECONDS
                    ),
                )
                await component_run.insert()
            if component_run.status == ComponentRunStatusEnum.CREATED:
                component_runs.append(component_run)

        if component_runs:
            await self._dispatch(
                action,
                node_instance,
                str(component_config.get("command") or DEFAULT_COMPONENT_COMMAND),
                list(
                    component_config.get("command_args")
                    or DEFAULT_COMPONENT_COMMAND_ARGS
                ),
                component_runs,
            )
        elif not existing_runs:
            raise RuntimeError("普通节点未创建任何组件运行")
        return NodeStartResult(state="running")

    async def _dispatch(
        self,
        action: ActionInstanceModel,
        node_instance: ActionInstanceNodeModel,
        command: str,
        command_args_snapshot: list[str],
        component_runs: list[ComponentRunModel],
    ) -> None:
        """派发待运行组件，并在部分失败时收敛同节点剩余任务。"""
        command_args = [
            "run",
            *command_args_snapshot,
            "--api-base-url",
            settings.api_base_url,
        ]
        for component_run in component_runs:
            component_bootstrap = await issue_component_bootstrap(
                action.id,
                node_instance.id,
                component_run.id,
            )
            accepted = await dispatch_component_run(
                component_run,
                command,
                [
                    *command_args,
                    "--component-run-id",
                    component_run.id,
                    f"--component-bootstrap={component_bootstrap}",
                ],
                priority=action.schedule_priority,
            )
            if accepted:
                continue
            now = datetime.now()
            await ComponentRunModel.find(
                {
                    "node_instance_id": node_instance.id,
                    "status": ComponentRunStatusEnum.CREATED,
                }
            ).update(
                {
                    "$set": {
                        "status": ComponentRunStatusEnum.CANCELLED,
                        "error_message": "同节点组件派发失败，运行已取消",
                        "finished_at": now,
                        "updated_at": now,
                    }
                }
            )
            await ComponentRunModel.find(
                {
                    "node_instance_id": node_instance.id,
                    "status": {
                        "$in": [
                            ComponentRunStatusEnum.DISPATCHED,
                            ComponentRunStatusEnum.RUNNING,
                        ]
                    },
                }
            ).update({"$set": {"cancel_requested": True}})
            raise RuntimeError("运行组件失败，调度平台无结果返回")

    async def reconcile(
        self,
        execution: ActionNodeExecutionModel,
    ) -> NodeExecutionOutcome | None:
        return None

    async def cancel(
        self,
        execution: ActionNodeExecutionModel,
        reason: str,
    ) -> bool:
        runs = await ComponentRunModel.find(
            {
                "node_instance_id": execution.node_instance_id,
                "status": {
                    "$in": [
                        ComponentRunStatusEnum.CREATED,
                        ComponentRunStatusEnum.DISPATCHED,
                        ComponentRunStatusEnum.RUNNING,
                    ]
                },
            }
        ).to_list()
        if not runs:
            return True
        now = datetime.now()
        await ComponentRunModel.find(
            {
                "node_instance_id": execution.node_instance_id,
                "status": ComponentRunStatusEnum.CREATED,
            }
        ).update(
            {
                "$set": {
                    "status": ComponentRunStatusEnum.CANCELLED,
                    "cancel_requested": True,
                    "error_message": reason,
                    "finished_at": now,
                    "updated_at": now,
                }
            }
        )
        remote_runs = [
            run
            for run in runs
            if run.status
            in {
                ComponentRunStatusEnum.DISPATCHED,
                ComponentRunStatusEnum.RUNNING,
            }
        ]
        if not remote_runs:
            return True
        await ComponentRunModel.find(
            {"_id": {"$in": [run.id for run in remote_runs]}}
        ).update({"$set": {"cancel_requested": True, "updated_at": now}})
        results = await asyncio.gather(
            *(cancel_component_run(run) for run in remote_runs),
            return_exceptions=True,
        )
        return all(result is True for result in results)
