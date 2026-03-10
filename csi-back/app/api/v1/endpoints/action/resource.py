from typing import List
from datetime import datetime
from fastapi import APIRouter, Depends
from beanie.operators import Set
from app.models.action.node import ActionNodeModel, ActionNodeHandleModel, ActionNodeInputModel
from app.schemas.action.node import ActionNode, BaseComponent, ActionNodeResponse
from app.schemas.general import PageParamsSchema, PageResponseSchema
from app.schemas.response import ApiResponseSchema
from app.service.component import get_components
from app.service.action import ActionInstanceService, node_model_to_response
from app.utils.id_lib import generate_id
from app.utils.dict_helper import pack_dict

router = APIRouter(prefix="/resource", tags=["行动资源"])


@router.get("/nodes", response_model=ApiResponseSchema[List[ActionNodeResponse]], summary="获取节点列表")
async def get_actions():
    nodes = await ActionNodeModel.find(ActionNodeModel.is_deleted == False).to_list()
    results = [await node_model_to_response(node) for node in nodes]
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

    response_data = await node_model_to_response(node_model)
    return ApiResponseSchema.success(data=response_data)


@router.get("/nodes/{node_id}", response_model=ApiResponseSchema[ActionNodeResponse], summary="获取节点详情")
async def get_node_detail(node_id: str):
    node = await ActionNodeModel.find_one({"_id": node_id, "is_deleted": False})
    if not node:
        return ApiResponseSchema.error(code=404, message=f"节点不存在，ID: {node_id}")
    return ApiResponseSchema.success(data=await node_model_to_response(node))


@router.put("/nodes/{node_id}", response_model=ApiResponseSchema[ActionNodeResponse], summary="修改节点")
async def update_node(node_id: str, data: ActionNode):
    node = await ActionNodeModel.find_one({"_id": node_id, "is_deleted": False})
    if not node:
        return ApiResponseSchema.error(code=404, message=f"节点不存在，ID: {node_id}")

    handle_models = []
    for handle in data.handles:
        handle_models.append(ActionNodeHandleModel(
            id=handle.id,
            relabel=handle.relabel,
            type=handle.type,
            position=handle.position,
            custom_style=pack_dict(handle.custom_style)
        ))

    input_models = []
    for input_item in data.inputs:
        input_id = generate_id(input_item.type + input_item.name)
        input_dict = {**input_item.model_dump(), "id": input_id}
        if input_item.options:
            input_dict["options"] = [opt.model_dump() for opt in input_item.options]
        input_db_dict = input_dict.copy()
        if "custom_style" in input_db_dict:
            input_db_dict["custom_style"] = pack_dict(input_db_dict.get("custom_style"))
        if "custom_props" in input_db_dict:
            input_db_dict["custom_props"] = pack_dict(input_db_dict.get("custom_props"))
        input_models.append(ActionNodeInputModel(**input_db_dict))

    now = datetime.now()
    await node.update(Set({
        ActionNodeModel.name: data.name,
        ActionNodeModel.description: data.description,
        ActionNodeModel.type: data.type.value,
        ActionNodeModel.version: data.version,
        ActionNodeModel.handles: handle_models,
        ActionNodeModel.inputs: input_models,
        ActionNodeModel.default_configs: pack_dict(data.default_configs),
        ActionNodeModel.related_components: data.related_components,
        ActionNodeModel.command: data.command,
        ActionNodeModel.command_args: data.command_args,
        ActionNodeModel.updated_at: now,
    }))

    await ActionInstanceService._clear_cache("node", node_id)

    updated = await ActionNodeModel.get(node_id)
    return ApiResponseSchema.success(data=await node_model_to_response(updated))


@router.delete("/nodes/{node_id}", response_model=ApiResponseSchema[None], summary="删除节点")
async def delete_node(node_id: str):
    node = await ActionNodeModel.find_one({"_id": node_id, "is_deleted": False})
    if not node:
        return ApiResponseSchema.error(code=404, message=f"节点不存在，ID: {node_id}")
    await node.update(Set({
        ActionNodeModel.is_deleted: True,
        ActionNodeModel.updated_at: datetime.now(),
    }))
    await ActionInstanceService._clear_cache("node", node_id)
    return ApiResponseSchema.success()


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
