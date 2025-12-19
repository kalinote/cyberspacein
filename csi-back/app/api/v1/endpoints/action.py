import logging
from typing import Dict, Any, List
from fastapi import APIRouter, Depends
from app.schemas.action import ActionNode

from app.curd.action import get_components_by_project_id, get_components_project_by_name
from app.schemas.action import BaseComponent, ActionNodeResponse, ActionNodeHandleResponse, ActionNodeInputResponse, ActionNodeOption
from app.schemas.general import PageParams, PageResponse
from app.schemas.response import ApiResponse
from app.schemas.enum import ActionNodeTypeEnum
from app.utils.id_lib import generate_id
from app.models.action import ActionNodeModel, ActionNodeHandleModel, ActionNodeInputModel

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/action",
    tags=["action"],
)


@router.get("/resource_management/nodes", response_model=ApiResponse[List[ActionNodeResponse]])
async def get_actions():
    nodes = await ActionNodeModel.find_all().to_list()

    results = []
    for node in nodes:
        handles_response = []
        for handle in node.handles:
            handles_response.append(ActionNodeHandleResponse(
                id=handle.id,
                name=handle.name,
                type=handle.type,
                position=handle.position,
                socket_type=handle.socket_type,
                allowed_socket_types=handle.allowed_socket_types,
                label=handle.label,
                custom_style=handle.custom_style
            ))

        inputs_response = []
        for input_item in node.inputs:
            options = None
            if input_item.options:
                options = [ActionNodeOption(**opt)
                           for opt in input_item.options]

            inputs_response.append(ActionNodeInputResponse(
                id=input_item.id,
                name=input_item.name,
                type=input_item.type,
                position=input_item.position,
                label=input_item.label,
                description=input_item.description,
                required=input_item.required,
                default=input_item.default,
                options=options,
                custom_style=input_item.custom_style,
                custom_props=input_item.custom_props
            ))

        results.append(ActionNodeResponse(
            id=node.id,
            name=node.name,
            description=node.description,
            type=ActionNodeTypeEnum(node.type),
            version=node.version,
            handles=handles_response,
            inputs=inputs_response,
            related_components=node.related_components
        ))

    return ApiResponse.success(data=results)


@router.post("/resource_management/nodes", response_model=ApiResponse[ActionNodeResponse])
async def create_node(data: ActionNode):
    node_id = generate_id(data.name + data.type.value + data.version)

    existing_node = await ActionNodeModel.find_one({"_id": node_id})
    if existing_node:
        return ApiResponse.error(code=400, message=f"节点已存在，ID: {node_id}")

    handles_with_id = []
    handle_models = []
    for handle in data.handles:
        handle_id = generate_id(
            handle.type + handle.socket_type + handle.name)
        handle_dict = {
            **handle.model_dump(),
            "id": handle_id
        }
        handles_with_id.append(handle_dict)
        handle_models.append(ActionNodeHandleModel(**handle_dict))

    inputs_with_id = []
    input_models = []
    for input_item in data.inputs:
        input_id = generate_id(input_item.type + input_item.name)
        input_dict = {
            **input_item.model_dump(),
            "id": input_id
        }
        if input_item.options:
            input_dict["options"] = [opt.model_dump()
                                     for opt in input_item.options]
        inputs_with_id.append(input_dict)
        input_models.append(ActionNodeInputModel(**input_dict))

    node_model = ActionNodeModel(
        id=node_id,
        name=data.name,
        description=data.description,
        type=data.type.value,
        version=data.version,
        handles=handle_models,
        inputs=input_models,
        related_components=data.related_components
    )

    await node_model.insert()
    logger.info(f"成功创建节点: {node_id}")

    response_data = ActionNodeResponse(
        id=node_id,
        name=data.name,
        description=data.description,
        type=data.type,
        version=data.version,
        handles=handles_with_id,
        inputs=inputs_with_id,
        related_components=data.related_components
    )

    return ApiResponse.success(data=response_data)


@router.get("/resource_management/base_components", response_model=PageResponse[BaseComponent])
async def get_base_components(
    params: PageParams = Depends()
):
    project_id = await get_components_project_by_name("csi_base_components")
    components = await get_components_by_project_id(project_id, params.page, params.page_size)

    results = []
    for component in components:
        results.append(BaseComponent(
            id=component["_id"],
            name=component["name"],
            description=component["description"],
            status=component["stat"]["last_task"].get("status", "unknown"),
            last_run_at=component["stat"]["last_task"].get("create_ts", None),
            total_runs=component["stat"]["tasks"],
            average_runtime=component["stat"]["average_total_duration"],
        ))

    return PageResponse.create(results, len(components), params.page, params.page_size)


@router.get("/node_config/{node_id}/init", response_model=ApiResponse[Dict[str, Any]])
async def get_node_config_init(node_id: str):
    logger.info(f"获取节点配置初始化: {node_id}")
    return ApiResponse.success(data={
        "meta": {
            "node_id": node_id,     # 节点id，指的是在一个行动流程中的节点，而不是数据库中的“静态的”节点id
            "action_id": "694251b96d9534925bd9f6f3",     # 行动流程id
        },
        
        # 静态配置，对应静态节点的input中的配置内容
        "config": {
            "page": 2,
            "crawler_type": "keyword"
        },
        
        # 输入数据，对应静态节点中的type为target的handle，也就是上游数据来源
        "inputs": {
            "keywords": {
                # type分为value和reference，分别对应直接数据和数据队列
                "type": "value",
                "value": ["黑丝"]
            },
            "platforms": {
                "type": "value",
                "value": ["javbus"]
            }
        },
        
        # 输出数据，对应静态节点中的type为source的handle，也就是下游数据去向，目前固定为rabbitmq队列
        "outputs": {
            "data_out": [
                {
                    "type": "reference",
                    "value": ["tmp_queue"]     # 数据队列名称
                }
            ]
        }
    })

@router.post("/node_config/{node_id}/result", response_model=ApiResponse[Dict[str, Any]])
async def report_action_node_result(node_id: str, data: Dict[str, Any]):
    logger.info(f"上报节点配置结果: {node_id}, {data}")
    return ApiResponse.success(data={})

@router.post("/node_config/{node_id}/heartbeat", response_model=ApiResponse[Dict[str, Any]])
async def report_action_node_heartbeat(node_id: str, data: Dict[str, Any]):
    logger.info(f"上报节点心跳: {node_id}, {data}")
    return ApiResponse.success(data={})