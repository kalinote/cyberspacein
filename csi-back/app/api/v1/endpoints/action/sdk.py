from datetime import datetime, timedelta, timezone
from typing import Any

from fastapi import APIRouter, Request

from app.core.config import settings
from app.core.exceptions import BadRequestException, ForbiddenException
from app.core.security import create_component_token
from app.models.action.action import ActionInstanceModel, ActionInstanceNodeModel
from app.models.action.component_run import ComponentRunModel
from app.models.action.node import ActionNodeModel
from app.schemas.action.log import ComponentLogBatchRequest, ComponentLogBatchResponse
from app.schemas.action.sdk import (
    SDKComponentInitResponse,
    SDKHeartbeatRequest,
    SDKHeartbeatResponse,
    SDKResultRequest,
)
from app.schemas.constants import ActionConfigIOTypeEnum, ComponentRunStatusEnum
from app.schemas.component_signal import (
    ComponentSignalBatchRequest,
    ComponentSignalBatchResponse,
)
from app.schemas.response import ApiResponseSchema
from app.service.action import ActionInstanceService
from app.service.action.log import ActionLogService
from app.service.component_signal.ingestion import ComponentSignalIngestionService
from app.utils.dict_helper import unpack_dict


router = APIRouter(prefix="/sdk", tags=["行动SDK"])


@router.post(
    "/{component_run_id}/token",
    response_model=ApiResponseSchema[dict[str, Any]],
    summary="交换组件运行短期凭证",
)
async def exchange_component_token(component_run_id: str, request: Request):
    context = request.state.component_bootstrap_context
    component_run = await ComponentRunModel.find_one({"_id": component_run_id})
    if component_run is None:
        return ApiResponseSchema.error(code=240417, message="组件运行实例不存在")
    return ApiResponseSchema.success(
        data={
            "component_token": create_component_token(
                context.action_id,
                context.node_instance_id,
                component_run_id,
            ),
            "attempt": component_run.attempt,
        }
    )


async def _build_io(
    node_instance: ActionInstanceNodeModel,
    definition: ActionNodeModel | None = None,
) -> tuple[dict, dict]:
    """从行动执行计划和队列绑定构造组件输入输出。"""
    binding_by_queue = {}
    if any(
        value.type == ActionConfigIOTypeEnum.REFERENCE
        for value in node_instance.inputs.values()
    ):
        action_nodes = await ActionInstanceNodeModel.find(
            {"action_id": node_instance.action_id}
        ).to_list()
        binding_by_queue = {
            binding.queue_name: binding
            for action_node in action_nodes
            for binding in action_node.reference_queue_bindings.values()
        }
    inputs: dict[str, Any] = {}
    for value in node_instance.inputs.values():
        input_payload = {"type": value.type.value, "value": value.value}
        if value.type == ActionConfigIOTypeEnum.REFERENCE:
            queue_names = (
                value.value
                if isinstance(value.value, list)
                else [value.value]
            )
            streams = []
            for queue_name in queue_names:
                if not isinstance(queue_name, str):
                    continue
                binding = binding_by_queue.get(queue_name)
                if binding is None:
                    continue
                streams.append(
                    {
                        "queue_name": binding.queue_name,
                        "stream_id": binding.stream_id,
                        "protocol": binding.protocol_version.value,
                        "expected_producer_ids": binding.expected_producer_ids,
                    }
                )
            if streams:
                input_payload["streams"] = streams
        inputs[value.key] = input_payload

    outputs: dict[str, Any] = {}
    action_instance = await ActionInstanceModel.find_one({"_id": node_instance.action_id})
    if action_instance:
        handle_queues: dict[str, list[str]] = {}
        handle_streams: dict[str, list[dict[str, Any]]] = {}
        for binding in node_instance.reference_queue_bindings.values():
            handle_queues.setdefault(
                binding.source_port_id,
                [],
            ).append(binding.queue_name)
            handle_streams.setdefault(
                binding.source_port_id,
                [],
            ).append(
                {
                    "queue_name": binding.queue_name,
                    "stream_id": binding.stream_id,
                    "protocol": binding.protocol_version.value,
                }
            )
        for handle_id, queue_names in handle_queues.items():
            snapshot_handle, handle = await (
                ActionInstanceService.resolve_node_handle_definition(
                    definition,
                    handle_id,
                )
            )
            handle_name = (
                handle.handle_name
                if handle
                else snapshot_handle.relabel
                if snapshot_handle and snapshot_handle.relabel
                else handle_id
            )
            if handle_name:
                outputs[handle_name] = {
                    "type": "reference",
                    "value": queue_names,
                    "streams": handle_streams[handle_id],
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
    definition = await ActionInstanceService.get_instance_node_definition(
        node_instance
    )
    if definition is None:
        return ApiResponseSchema.error(code=240418, message="节点定义不存在")
    config = unpack_dict(node_instance.configs) or {}
    inputs, outputs = await _build_io(node_instance, definition)

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
            timeout_seconds=component_run.timeout_seconds,
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
    "/{component_run_id}/signals",
    response_model=ApiResponseSchema[ComponentSignalBatchResponse],
    summary="批量提交组件资源信号",
)
async def submit_signals(
    component_run_id: str,
    batch: ComponentSignalBatchRequest,
    request: Request,
):
    context = request.state.component_context
    content_length = request.headers.get("content-length")
    if content_length:
        try:
            if int(content_length) > settings.COMPONENT_SIGNAL_MAX_REQUEST_BYTES:
                raise BadRequestException("组件信号请求大小超过限制")
        except ValueError as exc:
            raise BadRequestException("Content-Length 请求头格式无效") from exc
    if (
        len(batch.model_dump_json().encode("utf-8"))
        > settings.COMPONENT_SIGNAL_MAX_REQUEST_BYTES
    ):
        raise BadRequestException("组件信号请求大小超过限制")
    try:
        result = await ComponentSignalIngestionService().ingest_batch(
            context,
            batch,
        )
    except PermissionError as exc:
        raise ForbiddenException(str(exc)) from exc
    except ValueError as exc:
        raise BadRequestException(str(exc)) from exc
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
