from typing import List
from datetime import datetime
from fastapi import APIRouter, Depends, Query, Request
from pydantic import BaseModel
from beanie.operators import Set
from app.models.action.node import ActionNodeModel, ActionNodeHandleModel, ActionNodeInputModel
from app.schemas.action.node import (
    ActionNode,
    ActionNodeResponse,
    BaseComponent,
    EncapsulatedNodeDeleteConflictResponse,
    EncapsulatedNodeDeleteResponse,
    EncapsulatedNodeDetailResponse,
    EncapsulatedNodeFamilyResponse,
)
from app.schemas.general import PageParamsSchema, PageResponseSchema
from app.schemas.response import ApiResponseSchema
from app.service.component.service import get_components
from app.service.action import ActionInstanceService, node_model_to_response
from app.service.action.node_options import (
    apply_blueprint_io_handle_options,
    collect_node_handle_options,
)
from app.service.encapsulated_node import (
    EncapsulatedNodeReferencedError,
    delete_encapsulated_node_version,
    get_encapsulated_node_detail,
    list_encapsulated_node_families,
)
from app.schemas.constants import (
    ActionNodeDefinitionOriginEnum,
    ActionNodeKindEnum,
)
from app.utils.id_lib import generate_id
from app.utils.dict_helper import pack_dict

router = APIRouter(prefix="/resource", tags=["行动资源"])


class NativeNodeEnabledRequest(BaseModel):
    """后端原生节点启用状态请求。"""

    enabled: bool


@router.get(
    "/encapsulated-nodes",
    response_model=PageResponseSchema[EncapsulatedNodeFamilyResponse],
    summary="获取封装节点资源族列表",
)
async def get_encapsulated_nodes(
    params: PageParamsSchema = Depends(),
    keyword: str | None = Query(default=None, max_length=200),
):
    """按资源族分页获取封装节点及其有效版本。"""
    return await list_encapsulated_node_families(
        page=params.page,
        page_size=params.page_size,
        keyword=keyword,
    )


@router.get(
    "/encapsulated-nodes/{node_id}",
    response_model=ApiResponseSchema[EncapsulatedNodeDetailResponse],
    summary="获取封装节点版本详情",
)
async def get_encapsulated_node(node_id: str):
    """获取封装节点定义、源蓝图和可编辑蓝图引用。"""
    try:
        detail = await get_encapsulated_node_detail(node_id)
    except LookupError as exc:
        return ApiResponseSchema.error(code=240409, message=str(exc))
    except TypeError as exc:
        return ApiResponseSchema.error(code=240425, message=str(exc))
    return ApiResponseSchema.success(data=detail)


@router.delete(
    "/encapsulated-nodes/{node_id}",
    response_model=ApiResponseSchema[
        EncapsulatedNodeDeleteResponse | EncapsulatedNodeDeleteConflictResponse
    ],
    summary="删除封装节点版本",
)
async def delete_encapsulated_node(node_id: str):
    """软删除未被可编辑蓝图引用的单个封装节点版本。"""
    try:
        result = await delete_encapsulated_node_version(node_id)
    except LookupError as exc:
        return ApiResponseSchema.error(code=240409, message=str(exc))
    except TypeError as exc:
        return ApiResponseSchema.error(code=240425, message=str(exc))
    except EncapsulatedNodeReferencedError as exc:
        return ApiResponseSchema.error(
            code=240423,
            message=str(exc),
            data=EncapsulatedNodeDeleteConflictResponse(
                references=exc.references,
            ),
        )
    return ApiResponseSchema.success(data=result, message="封装节点版本已删除")


@router.get("/nodes", response_model=ApiResponseSchema[List[ActionNodeResponse]], summary="获取节点列表")
async def get_actions(panel: bool = False):
    query = {"is_deleted": False}
    if panel:
        query["enabled"] = True
        query["is_latest"] = True
    nodes = await ActionNodeModel.find(query).to_list()
    results = [await node_model_to_response(node) for node in nodes]
    options_by_direction = await collect_node_handle_options(
        ["source", "target"]
    )
    apply_blueprint_io_handle_options(results, options_by_direction)
    return ApiResponseSchema.success(data=results)


@router.post("/nodes", response_model=ApiResponseSchema[ActionNodeResponse], summary="创建节点")
async def create_node(data: ActionNode):
    if (
        data.node_kind != ActionNodeKindEnum.ORDINARY
        or data.definition_origin != ActionNodeDefinitionOriginEnum.USER
    ):
        return ApiResponseSchema.error(
            code=240425,
            message="通用节点接口只能创建普通节点",
        )
    if not data.related_components:
        return ApiResponseSchema.error(
            code=240001,
            message="普通节点必须关联至少一个基础组件",
        )
    node_id = generate_id(data.name + data.type.value + data.version)

    existing_node = await ActionNodeModel.find_one({"_id": node_id})
    if existing_node:
        return ApiResponseSchema.error(code=240901, message=f"节点已存在，ID: {node_id}")

    handle_models: list[ActionNodeHandleModel] = []
    for handle in data.handles:
        handle_models.append(ActionNodeHandleModel(
            id=handle.id,
            port_id=handle.port_id or handle.id,
            handle_config_id=handle.handle_config_id or handle.id,
            interface_type_id=handle.interface_type_id or handle.id,
            compatible_interface_type_ids=handle.compatible_interface_type_ids,
            relabel=handle.relabel,
            handle_name=handle.handle_name,
            data_type=handle.data_type,
            label=handle.label,
            color=handle.color,
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
        node_kind=data.node_kind,
        category=data.category,
        execution=data.execution,
        extension=None,
        definition_origin=ActionNodeDefinitionOriginEnum.USER,
        version=data.version,
        handles=handle_models,
        inputs=input_models,
        default_configs=pack_dict(data.default_configs),
        related_components=data.related_components,
        component_timeouts=dict(data.component_timeouts),
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
        return ApiResponseSchema.error(code=240409, message=f"节点不存在，ID: {node_id}")
    return ApiResponseSchema.success(data=await node_model_to_response(node))


@router.put("/nodes/{node_id}", response_model=ApiResponseSchema[ActionNodeResponse], summary="修改节点")
async def update_node(node_id: str, data: ActionNode):
    node = await ActionNodeModel.find_one({"_id": node_id, "is_deleted": False})
    if not node:
        return ApiResponseSchema.error(code=240409, message=f"节点不存在，ID: {node_id}")
    if node.definition_origin != ActionNodeDefinitionOriginEnum.USER:
        return ApiResponseSchema.error(
            code=240425,
            message="系统内置节点和封装节点不能通过通用接口修改",
        )
    if (
        data.node_kind != ActionNodeKindEnum.ORDINARY
        or data.definition_origin != ActionNodeDefinitionOriginEnum.USER
    ):
        return ApiResponseSchema.error(
            code=240425,
            message="节点一级类型和定义来源不能转换",
        )
    if not data.related_components:
        return ApiResponseSchema.error(
            code=240001,
            message="普通节点必须关联至少一个基础组件",
        )

    handle_models = []
    for handle in data.handles:
        handle_models.append(ActionNodeHandleModel(
            id=handle.id,
            port_id=handle.port_id or handle.id,
            handle_config_id=handle.handle_config_id or handle.id,
            interface_type_id=handle.interface_type_id or handle.id,
            compatible_interface_type_ids=handle.compatible_interface_type_ids,
            relabel=handle.relabel,
            handle_name=handle.handle_name,
            data_type=handle.data_type,
            label=handle.label,
            color=handle.color,
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
        ActionNodeModel.category: data.category,
        ActionNodeModel.node_kind: data.node_kind,
        ActionNodeModel.execution: data.execution,
        ActionNodeModel.version: data.version,
        ActionNodeModel.handles: handle_models,
        ActionNodeModel.inputs: input_models,
        ActionNodeModel.default_configs: pack_dict(data.default_configs),
        ActionNodeModel.related_components: data.related_components,
        ActionNodeModel.component_timeouts: dict(data.component_timeouts),
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
        return ApiResponseSchema.error(code=240409, message=f"节点不存在，ID: {node_id}")
    if node.definition_origin != ActionNodeDefinitionOriginEnum.USER:
        return ApiResponseSchema.error(
            code=240425,
            message="系统内置节点和封装节点不能通过通用接口删除",
        )
    await node.update(Set({
        ActionNodeModel.is_deleted: True,
        ActionNodeModel.updated_at: datetime.now(),
    }))
    await ActionInstanceService._clear_cache("node", node_id)
    return ApiResponseSchema.success()


@router.patch(
    "/nodes/{node_id}/enabled",
    response_model=ApiResponseSchema[ActionNodeResponse],
    summary="启用或禁用后端原生节点",
)
async def set_native_node_enabled(
    node_id: str,
    data: NativeNodeEnabledRequest,
    request: Request,
):
    node = await ActionNodeModel.find_one({"_id": node_id, "is_deleted": False})
    if not node:
        return ApiResponseSchema.error(code=240409, message=f"节点不存在，ID: {node_id}")
    if node.definition_origin != ActionNodeDefinitionOriginEnum.BACKEND_BUILTIN:
        return ApiResponseSchema.error(
            code=240425,
            message="该接口只能修改后端原生节点启用状态",
        )
    user = getattr(getattr(request.state, "auth_context", None), "user", None)
    now = datetime.now()
    await node.update(
        Set(
            {
                ActionNodeModel.enabled: data.enabled,
                ActionNodeModel.disabled_at: None if data.enabled else now,
                ActionNodeModel.disabled_by: (
                    None if data.enabled else getattr(user, "id", None)
                ),
                ActionNodeModel.updated_at: now,
            }
        )
    )
    await ActionInstanceService._clear_cache("node", node_id)
    updated = await ActionNodeModel.get(node_id)
    return ApiResponseSchema.success(data=await node_model_to_response(updated))


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
