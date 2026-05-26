import re
from datetime import datetime
from typing import Any, Optional

from fastapi import APIRouter, Depends, Query
from loguru import logger

from app.models.agent.configs import AgentModelConfigModel
from app.schemas.agent.agent import AgentModelConfigCreateRequestSchema, AgentModelConfigSchema
from app.schemas.agent.configs import ModelConfigListItemSchema
from app.schemas.general import PageParamsSchema, PageResponseSchema
from app.schemas.response import ApiResponseSchema
from app.utils.id_lib import generate_id
import app.utils.status_codes as status_codes
from app.models.agent.nanobot import NanobotAgentModel, NanobotWorkspaceModel

logger = logger.bind(name=__name__)

router = APIRouter(prefix="/configs")


@router.post("/models", response_model=ApiResponseSchema[AgentModelConfigSchema], summary="新增模型配置")
async def create_agent_model_config(data: AgentModelConfigCreateRequestSchema):
    config_id = generate_id(data.name + data.base_url + data.model)
    existing = await AgentModelConfigModel.find_one({"_id": config_id})
    if existing:
        return ApiResponseSchema.error(code=status_codes.CONFLICT_EXISTS, message="同名且同基础URL、同模型ID的配置已存在")
    existing_by_name = await AgentModelConfigModel.find_one({"name": data.name})
    if existing_by_name:
        return ApiResponseSchema.error(code=status_codes.CONFLICT_NAME, message=f"模型名称已存在: {data.name}")
    doc = AgentModelConfigModel(
        id=config_id,
        name=data.name,
        description=data.description,
        base_url=data.base_url,
        api_key=data.api_key,
        model=data.model,
    )
    await doc.insert()
    logger.info(f"成功创建模型配置: {config_id} - {data.name}")
    return ApiResponseSchema.success(data=AgentModelConfigSchema.from_doc(doc))


@router.get("/models", response_model=PageResponseSchema[AgentModelConfigSchema], summary="查询模型配置列表")
async def get_agent_model_config_list(
    params: PageParamsSchema = Depends(),
    search: Optional[str] = Query(None, description="搜索关键词，模糊匹配名称或描述"),
):
    skip = (params.page - 1) * params.page_size
    query_filters = {}
    if search:
        pattern = re.compile(re.escape(search), re.IGNORECASE)
        query_filters["$or"] = [
            {"name": {"$regex": pattern}},
            {"description": {"$regex": pattern}},
        ]
    query = AgentModelConfigModel.find(query_filters)
    total = await query.count()
    items = await query.skip(skip).limit(params.page_size).to_list()
    results = [AgentModelConfigSchema.from_doc(m) for m in items]
    return PageResponseSchema.create(results, total, params.page, params.page_size)


@router.get("/models-list", response_model=ApiResponseSchema[list[ModelConfigListItemSchema]], summary="查询模型配置名称列表")
async def get_agent_models_list():
    items = await AgentModelConfigModel.find_all().to_list()
    results = [ModelConfigListItemSchema(id=m.id, name=m.name) for m in items]
    return ApiResponseSchema.success(data=results)


@router.get(
    "/model/{model_config_id}",
    response_model=ApiResponseSchema[AgentModelConfigSchema],
    summary="查询模型配置详情",
)
async def get_agent_model_config_detail(model_config_id: str):
    doc = await AgentModelConfigModel.find_one({"_id": model_config_id})
    if not doc:
        return ApiResponseSchema.error(
            code=status_codes.NOT_FOUND_MODEL_CONFIG,
            message="模型配置不存在",
        )
    return ApiResponseSchema.success(data=AgentModelConfigSchema.from_doc(doc))


@router.put(
    "/model/{model_config_id}",
    response_model=ApiResponseSchema[AgentModelConfigSchema],
    summary="编辑模型配置",
)
async def update_agent_model_config(
    model_config_id: str,
    data: AgentModelConfigCreateRequestSchema,
):
    doc = await AgentModelConfigModel.find_one({"_id": model_config_id})
    if not doc:
        return ApiResponseSchema.error(
            code=status_codes.NOT_FOUND_MODEL_CONFIG,
            message="模型配置不存在",
        )
    if data.name != doc.name:
        existing_by_name = await AgentModelConfigModel.find_one({"name": data.name})
        if existing_by_name and existing_by_name.id != model_config_id:
            return ApiResponseSchema.error(
                code=status_codes.CONFLICT_NAME,
                message=f"模型名称已存在: {data.name}",
            )
    doc.name = data.name
    doc.description = data.description
    doc.base_url = data.base_url
    doc.api_key = data.api_key
    doc.model = data.model
    doc.updated_at = datetime.now()
    await doc.save()
    return ApiResponseSchema.success(data=AgentModelConfigSchema.from_doc(doc))


@router.delete(
    "/model/{model_config_id}",
    response_model=ApiResponseSchema[Any],
    summary="删除模型配置",
)
async def delete_agent_model_config(model_config_id: str):
    bound_agent = await NanobotAgentModel.find_one({"model_config_id": model_config_id})
    if bound_agent:
        return ApiResponseSchema.error(
            code=status_codes.CONFLICT_STATE,
            message="仍有 Agent 绑定该模型配置，无法删除",
        )
    workspace_ref = await NanobotWorkspaceModel.find_one(
        {"model_config_ids": model_config_id}
    )
    if workspace_ref:
        return ApiResponseSchema.error(
            code=status_codes.CONFLICT_STATE,
            message="仍有工作区将该模型配置列入可选列表，无法删除",
        )
    doc = await AgentModelConfigModel.find_one({"_id": model_config_id})
    if not doc:
        return ApiResponseSchema.error(
            code=status_codes.NOT_FOUND_MODEL_CONFIG,
            message="模型配置不存在",
        )
    await doc.delete()
    return ApiResponseSchema.success(data=None, message="删除成功")

