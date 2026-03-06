import logging
from typing import Dict, Any
from fastapi import APIRouter, BackgroundTasks
from app.models.action.action import ActionInstanceModel, ActionInstanceNodeModel
from app.models.action.configs import ActionNodesHandleConfigModel
from app.models.action.base_components import BaseComponentsTaskConfigModel
from app.models.action.node import ActionNodeModel
from app.models.action.blueprint import ActionBlueprintModel
from app.schemas.action.action import ActionConfigMeta, ActionNodeConfigInitResponse
from app.schemas.action.sdk import SDKResultRequest
from app.schemas.response import ApiResponseSchema
from app.schemas.constants import ActionConfigIOTypeEnum
from app.service.action import ActionInstanceService
from app.utils.dict_helper import unpack_dict

logger = logging.getLogger(__name__)

router = APIRouter(tags=["行动SDK"])


@router.get("/sdk/{node_instance_id}/init", response_model=ApiResponseSchema[ActionNodeConfigInitResponse], summary="获取节点配置初始化")
async def get_node_config_init(node_instance_id: str):
    logger.info(f"获取节点配置初始化: {node_instance_id}")
    task_config = await BaseComponentsTaskConfigModel.find_one({"node_instance_id": node_instance_id})
    if task_config:
        return ApiResponseSchema.success(data=ActionNodeConfigInitResponse(
            meta=ActionConfigMeta(
                node_instance_id=task_config.config_data.meta.node_instance_id,
                action_id=task_config.config_data.meta.action_id
            ),
            config=task_config.config_data.config,
            inputs=task_config.config_data.inputs,
            outputs=task_config.config_data.outputs
        ))

    node_instance = await ActionInstanceNodeModel.find_one({"_id": node_instance_id})
    if not node_instance:
        return ApiResponseSchema.error(code=404, message=f"节点实例不存在，ID: {node_instance_id}")

    node_definition = await ActionNodeModel.find_one({"_id": node_instance.definition_id})
    if not node_definition:
        return ApiResponseSchema.error(code=404, message=f"节点定义不存在，ID: {node_instance.definition_id}")

    inputs = {}
    for value in node_instance.inputs.values():
        inputs[value.key] = {
            "type": value.type.value,
            "value": value.value
        }

    action_instance = await ActionInstanceModel.find_one({"_id": node_instance.action_id})
    if not action_instance:
        return ApiResponseSchema.error(code=404, message=f"行动实例不存在，ID: {node_instance.action_id}")

    blueprint = await ActionBlueprintModel.find_one({"_id": action_instance.blueprint_id})
    if not blueprint:
        return ApiResponseSchema.error(code=404, message=f"蓝图不存在，ID: {action_instance.blueprint_id}")

    outputs = {}
    handle_queues = {}
    for edge in blueprint.graph.edges:
        if edge.source == node_instance.node_id:
            if edge.target in node_instance.reference_queues:
                queue_name = node_instance.reference_queues[edge.target]
                if edge.sourceHandle not in handle_queues:
                    handle_queues[edge.sourceHandle] = []
                handle_queues[edge.sourceHandle].append(queue_name)

    for handle_id, queue_names in handle_queues.items():
        handle_config = await ActionNodesHandleConfigModel.find_one({"_id": handle_id})
        if handle_config:
            outputs[handle_config.handle_name] = {
                "type": "reference",
                "value": queue_names
            }

    for value in node_instance.outputs.values():
        if value.type != ActionConfigIOTypeEnum.REFERENCE:
            outputs[value.key] = {
                "type": value.type.value,
                "value": value.value
            }

    response_data = ActionNodeConfigInitResponse(
        meta=ActionConfigMeta(
            node_instance_id=node_instance_id,
            action_id=node_instance.action_id
        ),
        config=unpack_dict(node_instance.configs),
        inputs=inputs,
        outputs=outputs
    )

    return ApiResponseSchema.success(data=response_data)


@router.post("/sdk/{node_instance_id}/result", response_model=ApiResponseSchema[Dict[str, Any]], summary="上报节点配置结果")
async def report_action_node_result(
    node_instance_id: str,
    result: SDKResultRequest,
    background_tasks: BackgroundTasks
):
    logger.info(f"上报节点结果: {node_instance_id}, {result}")
    background_tasks.add_task(ActionInstanceService.finish_node, node_instance_id, result)
    return ApiResponseSchema.success()


@router.post("/sdk/{node_instance_id}/heartbeat", response_model=ApiResponseSchema[Dict[str, Any]], summary="上报节点心跳")
async def report_action_node_heartbeat(
    node_instance_id: str, data: Dict[str, Any],
    background_tasks: BackgroundTasks
):
    logger.info(f"上报节点心跳: {node_instance_id}, {data}")
    background_tasks.add_task(ActionInstanceService.update_progress, node_instance_id, data.get("progress", 0))
    return ApiResponseSchema.success()
