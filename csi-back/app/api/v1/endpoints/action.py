import logging
from typing import Dict, Any, List
from fastapi import APIRouter, Depends
from app.schemas.action.node import ActionNode

from app.curd.action import get_components_by_project_id, get_components_project_by_name
from app.schemas.action.node import BaseComponent, ActionNodeResponse, ActionNodeHandleResponse, ActionNodeInputResponse, ActionNodeOption
from app.schemas.general import PageParams, PageResponse
from app.schemas.response import ApiResponse
from app.schemas.enum import ActionNodeTypeEnum
from app.utils.id_lib import generate_id
from app.models.action.node import ActionNodeModel, ActionNodeHandleModel, ActionNodeInputModel
from app.models.action.blueprint import ActionBlueprintModel, PositionModel, NodeDataModel, GraphNodeModel, GraphEdgeModel, ViewportModel, GraphModel
from app.schemas.action.blueprint import ActionBlueprint, ActionBlueprintBaseInfoResponse, ActionBlueprintDetailResponse
from app.utils.dict_helper import pack_dict, unpack_dict
from app.utils.workflow import count_workflow_paths

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/action",
    tags=["action"],
)

@router.post("/blueprint", response_model=ApiResponse[ActionBlueprintDetailResponse])
async def create_blueprint(data: ActionBlueprint):
    blueprint_id = generate_id(data.name + data.version + str(len(data.graph.nodes)) + str(len(data.graph.edges)))
    
    existing_blueprint = await ActionBlueprintModel.find_one({"_id": blueprint_id})
    if existing_blueprint:
        return ApiResponse.error(code=400, message=f"蓝图已存在，ID: {blueprint_id}")
    
    nodes_models = []
    for node in data.graph.nodes:
        node_data_model = NodeDataModel(
            definition_id=node.data.definition_id,
            version=node.data.version,
            form_data=pack_dict(node.data.form_data)
        )
        
        position_model = PositionModel(
            x=node.position.x,
            y=node.position.y
        )
        
        node_model = GraphNodeModel(
            id=node.id,
            type=node.type,
            position=position_model,
            data=node_data_model
        )
        nodes_models.append(node_model)
    
    edges_models = []
    for edge in data.graph.edges:
        edge_model = GraphEdgeModel(
            id=edge.id,
            source=edge.source,
            sourceHandle=edge.sourceHandle,
            target=edge.target,
            targetHandle=edge.targetHandle
        )
        edges_models.append(edge_model)
    
    viewport_model = ViewportModel(
        x=data.graph.viewport.x,
        y=data.graph.viewport.y,
        zoom=data.graph.viewport.zoom
    )
    
    graph_model = GraphModel(
        nodes=nodes_models,
        edges=edges_models,
        viewport=viewport_model
    )
    
    blueprint_model = ActionBlueprintModel(
        id=blueprint_id,
        name=data.name,
        version=data.version,
        description=data.description,
        target=data.target,
        implementation_period=data.implementation_period,
        resource=data.resource,
        graph=graph_model
    )
    
    await blueprint_model.insert()
    logger.info(f"成功创建蓝图: {blueprint_id}")
    
    response_data = ActionBlueprintDetailResponse(
        id=blueprint_id,
        name=data.name,
        version=data.version,
        description=data.description,
        target=data.target,
        implementation_period=data.implementation_period,
        resource=data.resource,
        graph=data.graph,
        created_at=blueprint_model.created_at,
        updated_at=blueprint_model.updated_at
    )
    
    return ApiResponse.success(data=response_data)

@router.get("/blueprint/list", response_model=PageResponse[ActionBlueprintBaseInfoResponse])
async def get_blueprints(
    params: PageParams = Depends()
):
    """获取蓝图列表，用于monitor页面的行动蓝图一栏"""
    skip = (params.page - 1) * params.page_size
    
    total = await ActionBlueprintModel.find_all().count()
    blueprints = await ActionBlueprintModel.find_all().skip(skip).limit(params.page_size).to_list()
    
    results = []
    for blueprint in blueprints:
        steps = len(blueprint.graph.nodes)
        
        graph_dict = blueprint.graph.model_dump()
        workflow_data = {"graph": graph_dict}
        branches = count_workflow_paths(workflow_data)
        
        results.append(ActionBlueprintBaseInfoResponse(
            id=blueprint.id,
            name=blueprint.name,
            version=blueprint.version,
            description=blueprint.description,
            target=blueprint.target,
            implementation_period=blueprint.implementation_period,
            created_at=blueprint.created_at,
            updated_at=blueprint.updated_at,
            steps=steps,
            branches=branches
        ))
    
    return PageResponse.create(results, total, params.page, params.page_size)
    

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
                custom_style=unpack_dict(handle.custom_style)
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
                custom_style=unpack_dict(input_item.custom_style),
                custom_props=unpack_dict(input_item.custom_props)
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
        
        handle_db_dict = handle_dict.copy()
        if "custom_style" in handle_db_dict:
            handle_db_dict["custom_style"] = pack_dict(handle_db_dict.get("custom_style"))
        handle_models.append(ActionNodeHandleModel(**handle_db_dict))

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

        input_db_dict = input_dict.copy()
        if "custom_style" in input_db_dict:
            input_db_dict["custom_style"] = pack_dict(input_db_dict.get("custom_style"))
        if "custom_props" in input_db_dict:
            input_db_dict["custom_props"] = pack_dict(input_db_dict.get("custom_props"))
        input_models.append(ActionNodeInputModel(**input_db_dict))

    node_model = ActionNodeModel(
        id=node_id,
        name=data.name,
        description=data.description,
        type=data.type.value,
        version=data.version,
        handles=handle_models,
        inputs=input_models,
        default_configs=pack_dict(data.default_configs),
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