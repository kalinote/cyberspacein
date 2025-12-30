from datetime import datetime
import logging
import random
from typing import Dict, Any, List
from fastapi import APIRouter, BackgroundTasks, Depends
from app.core.config import settings
from app.models.action.action import ActionInstanceModel, ActionInstanceNodeModel
from app.models.action.configs import ActionNodesHandleConfigModel
from app.schemas.action.action import ActionConfigIO, ActionConfigMeta, ActionDetailResponse, ActionInstanceBaseInfoResponse, ActionNodeConfigInitResponse, ActionNodeDetailResponse, StartActionRequest, StartActionResponse
from app.schemas.action.configs import ActionNodesHandleConfigAllResponse, ActionNodesHandleConfigRequest, ActionNodesHandleConfigResponse
from app.schemas.action.node import ActionNode
from app.schemas.action.sdk import SDKResultRequest

from app.service.component import get_components_by_project_id, get_components_project_by_name
from app.schemas.action.node import BaseComponent, ActionNodeResponse, ActionNodeHandleResponse, ActionNodeInputResponse, ActionNodeOption
from app.schemas.general import PageParams, PageResponse
from app.schemas.response import ApiResponse
from app.schemas.enum import ActionConfigIOTypeEnum, ActionFlowStatusEnum, ActionInstanceNodeStatusEnum, ActionNodeTypeEnum
from app.service.action import ActionInstanceService
from app.utils.id_lib import generate_id
from app.models.action.node import ActionNodeModel, ActionNodeHandleModel, ActionNodeInputModel
from app.models.action.blueprint import ActionBlueprintModel, PositionModel, NodeDataModel, GraphNodeModel, GraphEdgeModel, ViewportModel, GraphModel
from app.schemas.action.blueprint import ActionBlueprint, ActionBlueprintBaseInfoResponse, ActionBlueprintDetailResponse, GraphNode, GraphEdge, Position, NodeData, Graph, Viewport
from app.utils.dict_helper import pack_dict, unpack_dict
from app.utils.workflow import count_workflow_paths, graph_model2schemas

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/action",
    tags=["action"],
)

@router.post("/start", response_model=ApiResponse[StartActionResponse], summary="开始行动")
async def start_action(
    data: StartActionRequest,
    background_tasks: BackgroundTasks
):
    blueprint = await ActionBlueprintModel.find_one({"_id": data.blueprint_id})
    if not blueprint:
        return ApiResponse.error(code=404, message=f"蓝图不存在，ID: {data.blueprint_id}")
    
    result, message = await ActionInstanceService.init(data.blueprint_id)
    if not result:
        return ApiResponse.error(code=500, message=message)
    background_tasks.add_task(ActionInstanceService.start, message)
    
    return ApiResponse.success(data=StartActionResponse(action_id=message))

@router.get("/list", response_model=PageResponse[ActionInstanceBaseInfoResponse], summary="获取行动列表")
async def get_action_instances(
    params: PageParams = Depends()
):
    skip = (params.page - 1) * params.page_size
    total = await ActionInstanceModel.find_all().count()
    action_instances = await ActionInstanceModel.find_all().skip(skip).limit(params.page_size).to_list()
    
    results = []
    for action_instance in action_instances:
        blueprint = await ActionBlueprintModel.find_one({"_id": action_instance.blueprint_id})
        if not blueprint:
            continue
        
        completed_steps = len(action_instance.finished_nodes_id) if action_instance.finished_nodes_id else 0
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
    
    return PageResponse.create(results, total, params.page, params.page_size)

@router.get("/detail/{action_id}", response_model=ApiResponse[ActionDetailResponse], summary="获取行动详情")
async def get_action_detail(action_id: str):
    action_instance = await ActionInstanceModel.find_one({"_id": action_id})
    if not action_instance:
        return ApiResponse.error(code=404, message=f"行动不存在，ID: {action_id}")

    blueprint = await ActionBlueprintModel.find_one({"_id": action_instance.blueprint_id})
    if not blueprint:
        return ApiResponse.error(code=404, message=f"蓝图不存在，ID: {action_instance.blueprint_id}")
    
    completed_steps = len(action_instance.finished_nodes_id) if action_instance.finished_nodes_id else 0
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
        node_details[node_id] = ActionNodeDetailResponse(
            status=node_instance.status,
            progress=node_instance.progress,
            start_at=node_instance.start_at,
            finished_at=node_instance.finished_at,
            duration=node_instance.duration,
            inputs=unpack_dict(node_instance.inputs),
            outputs=unpack_dict(node_instance.outputs),
            error_message=node_instance.error_message
        )
    
    return ApiResponse.success(data=ActionDetailResponse(
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

@router.post("/blueprint", response_model=ApiResponse[ActionBlueprintDetailResponse], summary="创建蓝图")
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

@router.get("/blueprint/list", response_model=PageResponse[ActionBlueprintBaseInfoResponse], summary="获取蓝图列表")
async def get_blueprints(
    params: PageParams = Depends()
):
    """
    # 获取蓝图列表
    
    用于monitor页面的行动蓝图一栏
    """
    skip = (params.page - 1) * params.page_size
    
    total = await ActionBlueprintModel.find_all().count()
    blueprints = await ActionBlueprintModel.find_all().skip(skip).limit(params.page_size).to_list()
    
    results = []
    for blueprint in blueprints:
        steps = len(blueprint.graph.nodes)
        
        branches = count_workflow_paths(blueprint)
        
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
    
@router.get("/blueprint/detail/{blueprint_id}", response_model=ApiResponse[ActionBlueprintDetailResponse], summary="获取蓝图详情")
async def get_blueprint(blueprint_id: str):
    """
    # 获取蓝图详情
    
    注意这个接口应该放到list后面
    """
    blueprint = await ActionBlueprintModel.find_one({"_id": blueprint_id})
    if not blueprint:
        return ApiResponse.error(code=404, message=f"蓝图不存在，ID: {blueprint_id}")
    
    graph = graph_model2schemas(blueprint.graph)
    
    response_data = ActionBlueprintDetailResponse(
        id=blueprint.id,
        name=blueprint.name,
        version=blueprint.version,
        description=blueprint.description,
        target=blueprint.target,
        implementation_period=blueprint.implementation_period,
        resource=blueprint.resource,
        graph=graph,
        created_at=blueprint.created_at,
        updated_at=blueprint.updated_at
    )
    
    return ApiResponse.success(data=response_data)

#region 资源相关接口
@router.get("/resource/nodes", response_model=ApiResponse[List[ActionNodeResponse]], summary="获取节点列表")
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
            related_components=node.related_components,
            command=node.command,
            command_args=node.command_args
        ))

    return ApiResponse.success(data=results)


@router.post("/resource/nodes", response_model=ApiResponse[ActionNodeResponse], summary="创建节点")
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
        related_components=data.related_components,
        command=data.command,
        command_args=data.command_args
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
        related_components=data.related_components,
        command=data.command,
        command_args=data.command_args
    )

    return ApiResponse.success(data=response_data)


@router.get("/resource/base_components", response_model=PageResponse[BaseComponent], summary="获取基础组件列表")
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
            status=component["stat"].get("last_task", {}).get("status", "unknown"),
            last_run_at=component["stat"].get("last_task", {}).get("create_ts", None),
            total_runs=component["stat"].get("tasks", None),
            average_runtime=component["stat"].get("average_total_duration", None),
        ))

    return PageResponse.create(results, len(components), params.page, params.page_size)
#endregion

#region SDK相关接口
@router.get("/sdk/{node_instance_id}/init", response_model=ApiResponse[ActionNodeConfigInitResponse], summary="获取节点配置初始化")
async def get_node_config_init(node_instance_id: str):
    """
    # 获取节点配置初始化
    
    用于基础构建SDK获取基本节点参数配置
    """
    logger.info(f"获取节点配置初始化: {node_instance_id}")
    node_instance = await ActionInstanceNodeModel.find_one({"_id": node_instance_id})
    if not node_instance:
        return ApiResponse.error(code=404, message=f"节点实例不存在，ID: {node_instance_id}")
    
    node_instance = await ActionInstanceNodeModel.find_one({"_id": node_instance_id})
    if not node_instance:
        return ApiResponse.error(code=404, message=f"节点实例不存在，ID: {node_instance_id}")
    
    node_definition = await ActionNodeModel.find_one({"_id": node_instance.definition_id})
    if not node_definition:
        return ApiResponse.error(code=404, message=f"节点定义不存在，ID: {node_instance.definition_id}")
    
    response_data = ActionNodeConfigInitResponse(
        meta=ActionConfigMeta(
            node_instance_id=node_instance_id,
            action_id=node_instance.action_id
        ),
        config=unpack_dict(node_instance.configs),
        inputs={},
        outputs={
            "data_out": ActionConfigIO(
                type=ActionConfigIOTypeEnum.VALUE,
            )
        }
    )
    
    return ApiResponse.success(data=response_data)

@router.post("/sdk/{node_instance_id}/result", response_model=ApiResponse[Dict[str, Any]], summary="上报节点配置结果")
async def report_action_node_result(
    node_instance_id: str, 
    result: SDKResultRequest,
    background_tasks: BackgroundTasks
):
    logger.info(f"上报节点结果: {node_instance_id}, {result}")
    background_tasks.add_task(ActionInstanceService.finish_node, node_instance_id, result)
    return ApiResponse.success()

@router.post("/sdk/{node_instance_id}/heartbeat", response_model=ApiResponse[Dict[str, Any]], summary="上报节点心跳")
async def report_action_node_heartbeat(node_instance_id: str, data: Dict[str, Any]):
    logger.info(f"上报节点心跳: {node_instance_id}, {data}")
    return ApiResponse.success()
#endregion

#region 节点配置相关接口
@router.get("/configs/handles/all", response_model=ApiResponse[List[ActionNodesHandleConfigAllResponse]], summary="获取所有节点配置handle列表")
async def get_all_node_configs_handles():
    handles = await ActionNodesHandleConfigModel.find_all().to_list()
    results = []
    for handle in handles:
        results.append(ActionNodesHandleConfigAllResponse(
            id=handle.id,
            label=handle.label
        ))
    return ApiResponse.success(data=results)

@router.get("/configs/handles", response_model=PageResponse[ActionNodesHandleConfigResponse], summary="获取节点配置handle列表")
async def get_node_configs_handles(
    params: PageParams = Depends()
):
    skip = (params.page - 1) * params.page_size
    total = await ActionNodesHandleConfigModel.find_all().count()
    handles = await ActionNodesHandleConfigModel.find_all().skip(skip).limit(params.page_size).to_list()
    results = []
    for handle in handles:
        results.append(ActionNodesHandleConfigResponse(
            id=handle.id,
            handle_name=handle.handle_name,
            type=handle.type,
            label=handle.label,
            color=handle.color,
            custom_style=unpack_dict(handle.custom_style)
        ))
    return PageResponse.create(results, total, params.page, params.page_size)

@router.post("/configs/handles", response_model=ApiResponse[ActionNodesHandleConfigResponse], summary="创建节点配置handle")
async def create_node_configs_handle(data: ActionNodesHandleConfigRequest):
    handle_id = generate_id(data.handle_name + data.type.value)
    handle_model = ActionNodesHandleConfigModel(
        id=handle_id,
        handle_name=data.handle_name,
        type=data.type,
        label=data.label,
        color=data.color,
        custom_style=pack_dict(data.custom_style)
    )
    await handle_model.insert()
    
    return ApiResponse.success(data=ActionNodesHandleConfigResponse(
        id=handle_id,
        handle_name=data.handle_name,
        type=data.type,
        label=data.label,
        color=data.color,
        custom_style=unpack_dict(data.custom_style)
    ))
#endregion