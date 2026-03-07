from typing import List
from fastapi import APIRouter, Depends
from beanie.operators import In
from app.models.action.configs import ActionNodesHandleConfigModel
from app.models.action.node import ActionNodeModel, ActionNodeHandleModel, ActionNodeInputModel
from app.schemas.action.node import (
    ActionNode,
    BaseComponent,
    ActionNodeResponse,
    ActionNodeHandleResponse,
    ActionNodeInputResponse,
    ActionNodeOption,
)
from app.schemas.general import PageParamsSchema, PageResponseSchema
from app.schemas.response import ApiResponseSchema
from app.schemas.constants import ActionNodeTypeEnum
from app.service.component import get_components
from app.service.action import ActionInstanceService
from app.utils.id_lib import generate_id
from app.utils.dict_helper import pack_dict, unpack_dict

router = APIRouter(prefix="/resource", tags=["行动资源"])


@router.get("/nodes", response_model=ApiResponseSchema[List[ActionNodeResponse]], summary="获取节点列表")
async def get_actions():
    nodes = await ActionNodeModel.find_all().to_list()

    results = []
    for node in nodes:
        handle_ids = [handle.id for handle in node.handles]
        handle_configs = await ActionNodesHandleConfigModel.find(In(ActionNodesHandleConfigModel.id, handle_ids)).to_list()
        handle_config_map = {handle.id: handle for handle in handle_configs}

        handles_response = []
        for handle in node.handles:
            handle_config = handle_config_map.get(handle.id)
            custom_style = unpack_dict(handle_config.custom_style)
            custom_style.update(unpack_dict(handle.custom_style))

            handles_response.append(ActionNodeHandleResponse(
                id=handle.id,
                relabel=handle.relabel,
                type=handle.type,
                position=handle.position,
                custom_style=custom_style,
                handle_name=handle_config.handle_name,
                data_type=handle_config.type,
                label=handle_config.label,
                color=handle_config.color,
                other_compatible_interfaces=handle_config.other_compatible_interfaces,
            ))

        inputs_response = []
        for input_item in node.inputs:
            options = None
            if input_item.options:
                options = [ActionNodeOption(**opt) for opt in input_item.options]

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

    return ApiResponseSchema.success(data=results)


@router.post("/nodes", response_model=ApiResponseSchema[ActionNodeResponse], summary="创建节点")
async def create_node(data: ActionNode):
    node_id = generate_id(data.name + data.type.value + data.version)

    existing_node = await ActionNodeModel.find_one({"_id": node_id})
    if existing_node:
        return ApiResponseSchema.error(code=400, message=f"节点已存在，ID: {node_id}")

    handle_models: list[ActionNodeHandleModel] = []
    for handle in data.handles:
        handle_models.append(ActionNodeHandleModel(
            id=handle.id,
            relabel=handle.relabel,
            type=handle.type,
            position=handle.position,
            custom_style=pack_dict(handle.custom_style)
        ))

    inputs_with_id = []
    input_models = []
    for input_item in data.inputs:
        input_id = generate_id(input_item.type + input_item.name)
        input_dict = {
            **input_item.model_dump(),
            "id": input_id
        }
        if input_item.options:
            input_dict["options"] = [opt.model_dump() for opt in input_item.options]
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

    await ActionInstanceService._clear_cache("node", node_id)

    handle_ids = [handle.id for handle in handle_models]
    handle_configs = await ActionNodesHandleConfigModel.find(In(ActionNodesHandleConfigModel.id, handle_ids)).to_list()
    handle_config_map = {handle.id: handle for handle in handle_configs}

    handle_responses = []
    for handle in handle_models:
        handle_config = handle_config_map.get(handle.id)
        custom_style = unpack_dict(handle_config.custom_style)
        custom_style.update(unpack_dict(handle.custom_style))

        handle_responses.append(ActionNodeHandleResponse(
            id=handle.id,
            relabel=handle.relabel,
            type=handle.type,
            position=handle.position,
            custom_style=custom_style,
            handle_name=handle_config.handle_name,
            data_type=handle_config.type,
            label=handle_config.label,
            color=handle_config.color,
            other_compatible_interfaces=handle_config.other_compatible_interfaces,
        ))

    response_data = ActionNodeResponse(
        id=node_id,
        name=data.name,
        description=data.description,
        type=data.type,
        version=data.version,
        handles=handle_responses,
        inputs=inputs_with_id,
        related_components=data.related_components,
        command=data.command,
        command_args=data.command_args
    )

    return ApiResponseSchema.success(data=response_data)


@router.get("/base_components", response_model=PageResponseSchema[BaseComponent], summary="获取基础组件列表")
async def get_base_components(
    params: PageParamsSchema = Depends()
):
    components = await get_components(params.page, params.page_size)

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

    return PageResponseSchema.create(results, len(components), params.page, params.page_size)
