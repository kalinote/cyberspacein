from datetime import datetime
import logging
import re
from typing import Dict, Any, Optional
from fastapi import APIRouter, Depends, Query
from beanie.operators import Set
from app.models.action.components_task import BaseComponentsTaskConfigModel, BaseComponentsConfigModel
from app.schemas.action.components_task import (
    BaseComponentsTaskConfigCreateRequest,
    BaseComponentsTaskConfigUpdateRequest,
    BaseComponentsTaskConfigResponse,
    BaseComponentsConfigSchema,
    BaseComponentsTaskResponse,
)
from app.schemas.general import PageParamsSchema, PageResponseSchema
from app.schemas.response import ApiResponseSchema
from app.service.component import get_base_component_tasks
from app.utils.id_lib import generate_id

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/components-task", tags=["基础组件任务"])


@router.post("/configs", response_model=ApiResponseSchema[BaseComponentsTaskConfigResponse], summary="创建基础组件任务配置")
async def create_base_component_task_config(data: BaseComponentsTaskConfigCreateRequest):
    config_id = generate_id(data.name + data.type + data.version + data.config_data.meta.node_instance_id)
    existing = await BaseComponentsTaskConfigModel.find_one({"node_instance_id": data.config_data.meta.node_instance_id})
    if existing:
        return ApiResponseSchema.error(code=400, message=f"基础组件任务配置已存在，ID: {config_id}")
    config_data_model = BaseComponentsConfigModel(**data.config_data.model_dump())
    doc = BaseComponentsTaskConfigModel(
        id=config_id,
        node_instance_id=data.config_data.meta.node_instance_id,
        name=data.name,
        description=data.description,
        type=data.type,
        version=data.version,
        config_data=config_data_model,
    )
    await doc.insert()
    logger.info(f"成功创建基础组件任务配置: {config_id}")
    return ApiResponseSchema.success(data=BaseComponentsTaskConfigResponse(
        id=doc.id,
        node_instance_id=doc.node_instance_id,
        name=doc.name,
        description=doc.description,
        type=doc.type,
        version=doc.version,
        config_data=BaseComponentsConfigSchema.model_validate(doc.config_data.model_dump()),
        created_at=doc.created_at,
        updated_at=doc.updated_at,
    ))


@router.get("/configs", response_model=PageResponseSchema[BaseComponentsTaskConfigResponse], summary="获取基础组件任务配置列表")
async def get_base_component_task_configs(
    params: PageParamsSchema = Depends(),
    keyword: Optional[str] = Query(None, description="关键词，匹配标题、描述、config_data.meta.node_instance_id"),
):
    skip = (params.page - 1) * params.page_size
    query_filters: Dict[str, Any] = {"is_deleted": False}
    if keyword:
        pattern = re.compile(re.escape(keyword), re.IGNORECASE)
        query_filters["$or"] = [
            {"name": {"$regex": pattern}},
            {"description": {"$regex": pattern}},
            {"config_data.meta.node_instance_id": {"$regex": pattern}},
        ]
    query = BaseComponentsTaskConfigModel.find(query_filters)
    total = await query.count()
    items = await query.skip(skip).limit(params.page_size).to_list()
    results = [
        BaseComponentsTaskConfigResponse(
            id=doc.id,
            node_instance_id=doc.node_instance_id,
            name=doc.name,
            description=doc.description,
            type=doc.type,
            version=doc.version,
            config_data=BaseComponentsConfigSchema.model_validate(doc.config_data.model_dump()),
            created_at=doc.created_at,
            updated_at=doc.updated_at,
        )
        for doc in items
    ]
    return PageResponseSchema.create(results, total, params.page, params.page_size)


@router.get("/configs/detail/{config_id}", response_model=ApiResponseSchema[BaseComponentsTaskConfigResponse], summary="获取基础组件任务配置详情")
async def get_base_component_task_config_detail(config_id: str):
    doc = await BaseComponentsTaskConfigModel.find_one({"_id": config_id, "is_deleted": False})
    if not doc:
        return ApiResponseSchema.error(code=404, message=f"基础组件任务配置不存在或已删除，ID: {config_id}")
    return ApiResponseSchema.success(data=BaseComponentsTaskConfigResponse(
        id=doc.id,
        node_instance_id=doc.node_instance_id,
        name=doc.name,
        description=doc.description,
        type=doc.type,
        version=doc.version,
        config_data=BaseComponentsConfigSchema.model_validate(doc.config_data.model_dump()),
        created_at=doc.created_at,
        updated_at=doc.updated_at,
    ))


@router.patch("/configs/{config_id}", response_model=ApiResponseSchema[BaseComponentsTaskConfigResponse], summary="更新基础组件任务配置")
async def update_base_component_task_config(config_id: str, data: BaseComponentsTaskConfigUpdateRequest):
    doc = await BaseComponentsTaskConfigModel.find_one({"_id": config_id, "is_deleted": False})
    if not doc:
        return ApiResponseSchema.error(code=404, message=f"基础组件任务配置不存在或已删除，ID: {config_id}")
    update_data = data.model_dump(exclude_unset=True)
    if "config_data" in update_data and update_data["config_data"] is not None:
        update_data["config_data"] = BaseComponentsConfigModel(**update_data["config_data"]).model_dump()
    update_data["updated_at"] = datetime.now()
    await doc.update({"$set": update_data})
    updated = await BaseComponentsTaskConfigModel.get(config_id)
    return ApiResponseSchema.success(data=BaseComponentsTaskConfigResponse(
        id=updated.id,
        node_instance_id=updated.node_instance_id,
        name=updated.name,
        description=updated.description,
        type=updated.type,
        version=updated.version,
        config_data=BaseComponentsConfigSchema.model_validate(updated.config_data.model_dump()),
        created_at=updated.created_at,
        updated_at=updated.updated_at,
    ))


@router.delete("/configs/{config_id}", response_model=ApiResponseSchema[None], summary="删除基础组件任务配置")
async def delete_base_component_task_config(config_id: str):
    doc = await BaseComponentsTaskConfigModel.find_one({"_id": config_id, "is_deleted": False})
    if not doc:
        return ApiResponseSchema.error(code=404, message=f"基础组件任务配置不存在或已删除，ID: {config_id}")
    await doc.update(Set({
        BaseComponentsTaskConfigModel.is_deleted: True,
        BaseComponentsTaskConfigModel.updated_at: datetime.now(),
    }))
    return ApiResponseSchema.success()

@router.get("/tasks", response_model=PageResponseSchema[BaseComponentsTaskResponse], summary="获取基础组件任务列表")
async def get_base_component_task_list(
    params: PageParamsSchema = Depends(),
):
    tasks, total = await get_base_component_tasks(params.page, params.page_size)
    if tasks is None:
        tasks = []
    return PageResponseSchema.create([BaseComponentsTaskResponse(
        id=task.get("_id"),
        base_components_id=task.get("spider_id"),
        status=task.get("status"),
        created_at=datetime.fromisoformat(task.get("stat", {}).get("create_ts").replace("Z", "+00:00")) if task.get("stat", {}).get("create_ts") else None,
        start_at=datetime.fromisoformat(task.get("stat", {}).get("start_ts").replace("Z", "+00:00")) if task.get("stat", {}).get("start_ts") else None,
        end_at=datetime.fromisoformat(task.get("stat", {}).get("end_ts").replace("Z", "+00:00")) if task.get("stat", {}).get("end_ts") else None,
        config_id="",
        error_message=task.get("error"),
        schedule_id=task.get("schedule_id"),
        priority=task.get("priority"),
        total_duration=task.get("stat", {}).get("total_duration"),
        component_name=task.get("component_name"),
        schedule_name=task.get("schedule_name"),
    ) for task in tasks], total, params.page, params.page_size)