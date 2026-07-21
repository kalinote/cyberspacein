from datetime import datetime, timedelta, timezone
from typing import Any

from fastapi import APIRouter, Request

from app.core.config import settings
from app.core.security import create_component_token
from app.models.action.action import ActionInstanceModel, ActionInstanceNodeModel
from app.models.action.blueprint import ActionBlueprintModel
from app.models.action.component_run import ComponentRunModel
from app.models.action.configs import ActionNodesHandleConfigModel
from app.models.action.node import ActionNodeModel
from app.schemas.action.log import ComponentLogBatchRequest, ComponentLogBatchResponse
from app.schemas.action.sdk import (
    SDKComponentInitResponse,
    SDKHeartbeatRequest,
    SDKHeartbeatResponse,
    SDKResultRequest,
)
from app.schemas.constants import ActionConfigIOTypeEnum, ComponentRunStatusEnum
from app.schemas.response import ApiResponseSchema
from app.service.action import ActionInstanceService
from app.service.action_log import ActionLogService
from app.utils.dict_helper import unpack_dict


router = APIRouter(prefix="/sdk", tags=["行动SDK"])


@router.post(
    "/{component_run_id}/token",
    response_model=ApiResponseSchema[dict[str, str]],
    summary="交换组件运行短期凭证",
)
async def exchange_component_token(component_run_id: str, request: Request):
    context = request.state.component_bootstrap_context
    return ApiResponseSchema.success(
        data={
            "component_token": create_component_token(
                context.action_id,
                context.node_instance_id,
                component_run_id,
            )
        }
    )


async def _build_io(node_instance: ActionInstanceNodeModel) -> tuple[dict, dict]:
    inputs: dict[str, Any] = {}
    for value in node_instance.inputs.values():
        inputs[value.key] = {"type": value.type.value, "value": value.value}

    outputs: dict[str, Any] = {}
    action_instance = await ActionInstanceModel.find_one({"_id": node_instance.action_id})
    if action_instance:
        blueprint = await ActionBlueprintModel.find_one({"_id": action_instance.blueprint_id})
        if blueprint:
            handle_queues: dict[str, list[str]] = {}
            for edge in blueprint.graph.edges:
                if edge.source != node_instance.node_id:
                    continue
                queue_name = node_instance.reference_queues.get(edge.target)
                if queue_name:
                    handle_queues.setdefault(edge.sourceHandle, []).append(queue_name)
            for handle_id, queue_names in handle_queues.items():
                handle = await ActionNodesHandleConfigModel.find_one({"_id": handle_id})
                if handle:
                    outputs[handle.handle_name] = {
                        "type": "reference",
                        "value": queue_names,
                    }
    for value in node_instance.outputs.values():
        if value.type != ActionConfigIOTypeEnum.REFERENCE:
            outputs[value.key] = {"type": value.type.value, "value": value.value}
    return inputs, outputs


@router.get(
    "/{component_run_id}/init",
    response_model=ApiResponseSchema[SDKComponentInitResponse],
    summary="获取组件运行上下文",
)
async def get_component_init(component_run_id: str):
    component_run = await ComponentRunModel.find_one({"_id": component_run_id})
    if component_run is None:
        return ApiResponseSchema.error(code=240417, message="组件运行实例不存在")
    if component_run.status not in {
        ComponentRunStatusEnum.DISPATCHED,
        ComponentRunStatusEnum.RUNNING,
    }:
        return ApiResponseSchema.error(code=240420, message="组件运行实例已结束")
    node_instance = await ActionInstanceNodeModel.find_one(
        {"_id": component_run.node_instance_id, "action_id": component_run.action_id}
    )
    if node_instance is None:
        return ApiResponseSchema.error(code=240417, message="节点实例不存在")

    definition = await ActionNodeModel.find_one(
        {"_id": node_instance.definition_id, "is_deleted": False}
    )
    if definition is None:
        return ApiResponseSchema.error(code=240418, message="节点定义不存在")
    config = unpack_dict(node_instance.configs) or {}
    inputs, outputs = await _build_io(node_instance)

    now = datetime.now()
    component_run.status = ComponentRunStatusEnum.RUNNING
    component_run.started_at = component_run.started_at or now
    component_run.last_heartbeat_at = now
    component_run.lease_expires_at = now + timedelta(seconds=settings.COMPONENT_LEASE_SECONDS)
    component_run.updated_at = now
    await component_run.save()

    return ApiResponseSchema.success(
        data=SDKComponentInitResponse(
            action_id=component_run.action_id,
            node_instance_id=node_instance.id,
            component_run_id=component_run.id,
            component_id=component_run.component_id,
            attempt=component_run.attempt,
            config=config,
            inputs=inputs,
            outputs=outputs,
            heartbeat_interval=settings.COMPONENT_HEARTBEAT_INTERVAL_SECONDS,
            lease_seconds=settings.COMPONENT_LEASE_SECONDS,
            timeout_seconds=settings.COMPONENT_RUN_TIMEOUT_SECONDS,
        )
    )


@router.post(
    "/{component_run_id}/heartbeat",
    response_model=ApiResponseSchema[SDKHeartbeatResponse],
    summary="上报组件运行心跳",
)
async def heartbeat(component_run_id: str, data: SDKHeartbeatRequest):
    component_run = await ComponentRunModel.find_one({"_id": component_run_id})
    if component_run is None:
        return ApiResponseSchema.error(code=240417, message="组件运行实例不存在")
    if component_run.status not in {
        ComponentRunStatusEnum.DISPATCHED,
        ComponentRunStatusEnum.RUNNING,
    }:
        return ApiResponseSchema.success(
            data=SDKHeartbeatResponse(
                command="cancel",
                lease_expires_at=(
                    component_run.lease_expires_at or datetime.now()
                ).replace(tzinfo=timezone.utc).isoformat(),
            )
        )
    now = datetime.now()
    component_run.progress = data.progress
    component_run.last_heartbeat_at = now
    component_run.lease_expires_at = now + timedelta(seconds=settings.COMPONENT_LEASE_SECONDS)
    component_run.updated_at = now
    await component_run.save()
    active_runs = await ComponentRunModel.find(
        {"node_instance_id": component_run.node_instance_id}
    ).to_list()
    average_progress = (
        sum(run.progress for run in active_runs) / len(active_runs)
        if active_runs
        else data.progress
    )
    await ActionInstanceService.update_progress(
        component_run.node_instance_id, average_progress
    )
    refreshed = create_component_token(
        component_run.action_id,
        component_run.node_instance_id,
        component_run.id,
    )
    return ApiResponseSchema.success(
        data=SDKHeartbeatResponse(
            command="cancel" if component_run.cancel_requested else "continue",
            lease_expires_at=component_run.lease_expires_at.replace(
                tzinfo=timezone.utc
            ).isoformat(),
            component_token=refreshed,
        )
    )


@router.post(
    "/{component_run_id}/log-batches",
    response_model=ApiResponseSchema[ComponentLogBatchResponse],
    summary="批量提交组件运行日志",
)
async def submit_logs(component_run_id: str, batch: ComponentLogBatchRequest):
    component_run = await ComponentRunModel.find_one({"_id": component_run_id})
    if component_run is None:
        return ApiResponseSchema.error(code=240417, message="组件运行实例不存在")
    result = await ActionLogService.ingest(component_run, batch)
    return ApiResponseSchema.success(data=result)


@router.post(
    "/{component_run_id}/result",
    response_model=ApiResponseSchema[dict[str, Any]],
    summary="提交组件运行结果",
)
async def submit_result(component_run_id: str, result: SDKResultRequest):
    accepted = await ActionInstanceService.finish_component_run(component_run_id, result)
    if not accepted:
        return ApiResponseSchema.error(code=240419, message="组件运行结果未被接受")
    return ApiResponseSchema.success(data={"accepted": True})
