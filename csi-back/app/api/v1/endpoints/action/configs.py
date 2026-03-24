from typing import List
from fastapi import APIRouter, Depends
from app.models.action.accounts import AccountModel
from app.models.action.configs import ActionNodesHandleConfigModel
from app.models.action.node import ActionNodeModel
from app.models.action.sandbox import SandboxModel
from app.schemas.constants import ActionNodeTypeEnum
from app.schemas.action.configs import (
    ActionConfigsStatisticsResponse,
    ActionNodesHandleConfigAllResponse,
    ActionNodesHandleConfigRequest,
    ActionNodesHandleConfigResponse,
)
from app.schemas.general import PageParamsSchema, PageResponseSchema
from app.schemas.response import ApiResponseSchema
from app.service.action import ActionInstanceService
from app.utils.id_lib import generate_id
from app.utils.dict_helper import pack_dict, unpack_dict

router = APIRouter(prefix="/configs", tags=["节点配置"])


@router.get("/statistics", response_model=ApiResponseSchema[ActionConfigsStatisticsResponse], summary="获取节点配置统计信息")
async def get_node_configs_statistics():
    node_count = await ActionNodeModel.find(ActionNodeModel.is_deleted == False).count()
    handle_count = await ActionNodesHandleConfigModel.find_all().count()
    account_count = await AccountModel.find(AccountModel.is_deleted == False).count()
    container_count = await SandboxModel.find_all().count()

    statistics = ActionConfigsStatisticsResponse(
        node_count=node_count,
        handle_count=handle_count,
        account_count=account_count,
        container_count=container_count,
    )

    return ApiResponseSchema.success(data=statistics)


@router.get("/handles/all", response_model=ApiResponseSchema[List[ActionNodesHandleConfigAllResponse]], summary="获取所有节点配置handle列表")
async def get_all_node_configs_handles():
    handles = await ActionNodesHandleConfigModel.find_all().to_list()
    results = []
    for handle in handles:
        results.append(ActionNodesHandleConfigAllResponse(
            id=handle.id,
            label=handle.label
        ))
    return ApiResponseSchema.success(data=results)


@router.get("/handles", response_model=PageResponseSchema[ActionNodesHandleConfigResponse], summary="获取节点配置handle列表")
async def get_node_configs_handles(
    params: PageParamsSchema = Depends()
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
    return PageResponseSchema.create(results, total, params.page, params.page_size)


@router.post("/handles", response_model=ApiResponseSchema[ActionNodesHandleConfigResponse], summary="创建节点配置handle")
async def create_node_configs_handle(data: ActionNodesHandleConfigRequest):
    handle_id = generate_id(data.handle_name + data.type.value)

    if await ActionNodesHandleConfigModel.find_one({"_id": handle_id}):
        return ApiResponseSchema.error(code=240901, message=f"节点配置handle已存在，ID: {handle_id}")

    handle_model = ActionNodesHandleConfigModel(
        id=handle_id,
        handle_name=data.handle_name,
        type=data.type,
        label=data.label,
        color=data.color,
        other_compatible_interfaces=data.other_compatible_interfaces,
        custom_style=pack_dict(data.custom_style)
    )
    await handle_model.insert()

    await ActionInstanceService._clear_cache("handle", handle_id)
    await ActionInstanceService._clear_cache("handle_name", data.handle_name)

    return ApiResponseSchema.success(data=ActionNodesHandleConfigResponse(
        id=handle_id,
        handle_name=data.handle_name,
        type=data.type,
        label=data.label,
        color=data.color,
        other_compatible_interfaces=data.other_compatible_interfaces,
        custom_style=unpack_dict(data.custom_style)
    ))

@router.get("/filter/node_type", response_model=ApiResponseSchema[List[dict[str, str]]], summary="获取节点类型过滤列表")
async def get_node_type_filter_list():
    data = [{e.label: e.value} for e in ActionNodeTypeEnum]
    return ApiResponseSchema.success(data=data)