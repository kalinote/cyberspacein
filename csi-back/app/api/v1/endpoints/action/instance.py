from typing import List
from fastapi import APIRouter, BackgroundTasks, Depends
from app.models.action.action import ActionInstanceModel, ActionInstanceNodeModel
from app.models.action.configs import ActionNodesHandleConfigModel
from app.models.action.blueprint import ActionBlueprintModel
from app.schemas.action.action import (
    ActionDetailResponse,
    ActionInstanceBaseInfoResponse,
    ActionNodeDetailResponse,
    StartActionRequest,
    StartActionResponse,
)
from app.schemas.general import PageParamsSchema, PageResponseSchema
from app.schemas.response import ApiResponseSchema
from app.schemas.constants import ActionInstanceNodeStatusEnum
from app.service.action import ActionInstanceService
from app.utils.dict_helper import unpack_dict
from app.utils.workflow import graph_model2schemas

router = APIRouter(tags=["行动实例"])


@router.post("/start", response_model=ApiResponseSchema[StartActionResponse], summary="开始行动")
async def start_action(
    data: StartActionRequest,
    background_tasks: BackgroundTasks
):
    blueprint = await ActionBlueprintModel.find_one({"_id": data.blueprint_id})
    if not blueprint:
        return ApiResponseSchema.error(code=404, message=f"蓝图不存在，ID: {data.blueprint_id}")

    if not data.params:
        result, message = await ActionInstanceService.init(data.blueprint_id)
    else:
        result, message = await ActionInstanceService.init(data.blueprint_id, data.params)
    if not result:
        return ApiResponseSchema.error(code=500, message=message)
    background_tasks.add_task(ActionInstanceService.start, message)

    return ApiResponseSchema.success(data=StartActionResponse(action_id=message))


@router.get("/list", response_model=PageResponseSchema[ActionInstanceBaseInfoResponse], summary="获取行动列表")
async def get_action_instances(
    params: PageParamsSchema = Depends()
):
    skip = (params.page - 1) * params.page_size
    total = await ActionInstanceModel.find_all().count()
    action_instances = await ActionInstanceModel.find_all().skip(skip).limit(params.page_size).to_list()

    results: List[ActionInstanceBaseInfoResponse] = []
    for action_instance in action_instances:
        blueprint = await ActionBlueprintModel.find_one({"_id": action_instance.blueprint_id})
        if not blueprint:
            continue

        completed_steps = len(action_instance.finished_nodes_instance) if action_instance.finished_nodes_instance else 0
        total_steps = len(action_instance.nodes_id) if action_instance.nodes_id else 0

        results.append(ActionInstanceBaseInfoResponse(
            id=action_instance.id,
            name=blueprint.name,
            description=blueprint.description,
            status=action_instance.status,
            start_at=action_instance.start_at,
            finished_at=action_instance.finished_at,
            duration=action_instance.duration,
            progress=action_instance.progress,
            completed_steps=completed_steps,
            total_steps=total_steps
        ))

    return PageResponseSchema.create(results, total, params.page, params.page_size)


@router.get("/detail/{action_id}", response_model=ApiResponseSchema[ActionDetailResponse], summary="获取行动详情")
async def get_action_detail(action_id: str):
    action_instance = await ActionInstanceModel.find_one({"_id": action_id})
    if not action_instance:
        return ApiResponseSchema.error(code=404, message=f"行动不存在，ID: {action_id}")

    blueprint = await ActionBlueprintModel.find_one({"_id": action_instance.blueprint_id})
    if not blueprint:
        return ApiResponseSchema.error(code=404, message=f"蓝图不存在，ID: {action_instance.blueprint_id}")

    completed_steps = len(action_instance.finished_nodes_instance) if action_instance.finished_nodes_instance else 0
    total_steps = len(action_instance.nodes_id) if action_instance.nodes_id else 0

    graph = graph_model2schemas(blueprint.graph)

    node_instance_map: dict[str, ActionInstanceNodeModel] = {}
    for node_id in action_instance.nodes_id:
        node_instance = await ActionInstanceNodeModel.find_one({"action_id": action_instance.id, "node_id": node_id})
        if node_instance:
            node_instance_map[node_id] = node_instance

    for node in graph.nodes:
        if node.id in node_instance_map:
            node_instance = node_instance_map[node.id]
            node.data.form_data = unpack_dict(node_instance.configs) or {}

    node_details = {}
    for node_id in action_instance.nodes_id:
        if node_id not in node_instance_map:
            node_details[node_id] = ActionNodeDetailResponse(
                status=ActionInstanceNodeStatusEnum.UNKNOWN,
            )
            continue

        node_instance = node_instance_map[node_id]

        combined_outputs = dict(node_instance.outputs)
        for target_node_id, queue_name in node_instance.reference_queues.items():
            for edge in blueprint.graph.edges:
                if edge.source == node_id and edge.target == target_node_id:
                    handle_config = await ActionNodesHandleConfigModel.find_one({"_id": edge.sourceHandle})
                    if handle_config:
                        combined_outputs[edge.sourceHandle] = {
                            "type": "reference",
                            "key": handle_config.handle_name,
                            "value": queue_name
                        }
                    break

        node_details[node_id] = ActionNodeDetailResponse(
            status=node_instance.status,
            progress=node_instance.progress,
            start_at=node_instance.start_at,
            finished_at=node_instance.finished_at,
            duration=node_instance.duration,
            inputs=node_instance.inputs,
            outputs=combined_outputs,
            error_message=node_instance.error_message
        )

    return ApiResponseSchema.success(data=ActionDetailResponse(
        id=action_instance.id,
        name=blueprint.name,
        description=blueprint.description,
        status=action_instance.status,
        resource=blueprint.resource,
        implementation_period=blueprint.implementation_period,
        start_at=action_instance.start_at,
        finished_at=action_instance.finished_at,
        duration=action_instance.duration,
        progress=action_instance.progress,
        completed_steps=completed_steps,
        total_steps=total_steps,
        graph=graph,
        node_details=node_details
    ))
