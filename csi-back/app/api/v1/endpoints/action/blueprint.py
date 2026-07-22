from datetime import datetime

from elasticsearch import ApiError
from loguru import logger
from fastapi import APIRouter, Depends
from app.core.config import settings
from app.db.elasticsearch import get_es
from app.models.action.action import ActionInstanceModel, ActionInstanceNodeModel
from app.models.action.blueprint import (
    ActionBlueprintModel,
    PositionModel,
    NodeDataModel,
    GraphNodeModel,
    GraphEdgeModel,
    ViewportModel,
    GraphModel,
)
from app.models.action.component_run import ComponentRunModel
from app.models.action.schedule import ActionScheduleModel
from app.schemas.action.blueprint import (
    ActionBlueprintSchema,
    ActionBlueprintBaseInfoResponse,
    ActionBlueprintDetailResponseSchema,
    TemplateSpecSchema,
)
from app.schemas.general import PageParamsSchema, PageResponseSchema
from app.schemas.response import ApiResponseSchema
from app.schemas.constants import ActionFlowStatusEnum
from app.service.action import ActionInstanceService
from app.utils.id_lib import generate_id
from app.utils.dict_helper import pack_dict
from app.utils.workflow import count_workflow_paths, graph_model2schemas

logger = logger.bind(name=__name__)

router = APIRouter(prefix="/blueprint", tags=["行动蓝图"])


@router.post("", response_model=ApiResponseSchema[ActionBlueprintDetailResponseSchema], summary="创建蓝图")
async def create_blueprint(data: ActionBlueprintSchema):
    if data.is_template:
        param_names = [p.name for p in data.template.params]
        if len(param_names) != len(set(param_names)):
            return ApiResponseSchema.error(code=240001, message="参数名称必须唯一")

        for node_bindings in data.template.bindings.values():
            for binding_name, binding_param in node_bindings.items():
                if binding_param not in param_names:
                    return ApiResponseSchema.error(
                        code=240001,
                        message=f"绑定引用的参数 '{binding_param}' 不存在"
                    )

    blueprint_id = generate_id(data.name + data.version + str(len(data.graph.nodes)) + str(len(data.graph.edges)))

    existing_blueprint = await ActionBlueprintModel.find_one({"_id": blueprint_id})
    if existing_blueprint:
        return ApiResponseSchema.error(code=240901, message=f"蓝图已存在，ID: {blueprint_id}")

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
        graph=graph_model,
        is_template=data.is_template,
        template=data.template.model_dump() if data.template else None
    )

    await blueprint_model.insert()
    logger.info(f"成功创建蓝图: {blueprint_id}")

    await ActionInstanceService._clear_cache("blueprint", blueprint_id)

    response_data = ActionBlueprintDetailResponseSchema(
        id=blueprint_id,
        name=data.name,
        version=data.version,
        description=data.description,
        target=data.target,
        implementation_period=data.implementation_period,
        resource=data.resource,
        graph=data.graph,
        created_at=blueprint_model.created_at,
        updated_at=blueprint_model.updated_at,
        is_template=blueprint_model.is_template,
        template=data.template
    )

    return ApiResponseSchema.success(data=response_data)


@router.get("/list", response_model=PageResponseSchema[ActionBlueprintBaseInfoResponse], summary="获取蓝图列表")
async def get_blueprints(
    params: PageParamsSchema = Depends()
):
    skip = (params.page - 1) * params.page_size

    query = ActionBlueprintModel.find({"is_deleted": False})
    total = await query.count()
    blueprints = await query.skip(skip).limit(params.page_size).to_list()

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
            branches=branches,
            is_template=blueprint.is_template,
        ))

    return PageResponseSchema.create(results, total, params.page, params.page_size)


@router.get("/detail/{blueprint_id}", response_model=ApiResponseSchema[ActionBlueprintDetailResponseSchema], summary="获取蓝图详情")
async def get_blueprint(blueprint_id: str):
    blueprint = await ActionBlueprintModel.find_one({"_id": blueprint_id})
    if not blueprint:
        return ApiResponseSchema.error(code=240411, message=f"蓝图不存在，ID: {blueprint_id}")

    graph = graph_model2schemas(blueprint.graph)

    response_data = ActionBlueprintDetailResponseSchema(
        id=blueprint.id,
        name=blueprint.name,
        version=blueprint.version,
        description=blueprint.description,
        target=blueprint.target,
        implementation_period=blueprint.implementation_period,
        resource=blueprint.resource,
        graph=graph,
        created_at=blueprint.created_at,
        updated_at=blueprint.updated_at,
        is_template=blueprint.is_template,
        template=TemplateSpecSchema(**blueprint.template) if blueprint.template else None
    )

    return ApiResponseSchema.success(data=response_data)


@router.delete("/{blueprint_id}", response_model=ApiResponseSchema[None], summary="删除蓝图及历史行动")
async def delete_blueprint(blueprint_id: str):
    """删除蓝图，并级联清理其历史行动、节点、组件运行记录和日志。

    Args:
        blueprint_id: 待删除的蓝图 ID。

    Returns:
        删除结果；存在调度计划或未结束行动时返回业务错误。
    """
    blueprint = await ActionBlueprintModel.find_one({"_id": blueprint_id, "is_deleted": False})
    if not blueprint:
        return ApiResponseSchema.error(code=240411, message=f"蓝图不存在，ID: {blueprint_id}")

    schedule = await ActionScheduleModel.find_one({"blueprint_id": blueprint_id, "is_deleted": False})
    if schedule:
        return ApiResponseSchema.error(code=240423, message="该蓝图仍有关联调度计划，请先删除调度计划")

    blueprint.is_deleted = True
    blueprint.updated_at = datetime.now()
    await blueprint.save()
    await ActionInstanceService._clear_cache("blueprint", blueprint_id)

    terminal_statuses = [
        ActionFlowStatusEnum.COMPLETED.value,
        ActionFlowStatusEnum.FAILED.value,
        ActionFlowStatusEnum.CANCELLED.value,
        ActionFlowStatusEnum.TIMEOUT.value,
    ]
    active_action = await ActionInstanceModel.find_one({
        "blueprint_id": blueprint_id,
        "status": {"$nin": terminal_statuses},
    })
    if active_action:
        blueprint.is_deleted = False
        blueprint.updated_at = datetime.now()
        await blueprint.save()
        await ActionInstanceService._clear_cache("blueprint", blueprint_id)
        return ApiResponseSchema.error(code=240423, message="该蓝图仍有未结束的行动，暂时无法删除")

    try:
        action_instances = await ActionInstanceModel.find({"blueprint_id": blueprint_id}).to_list()
        action_ids = [action.id for action in action_instances]

        es = get_es()
        if es is not None and action_ids:
            for offset in range(0, len(action_ids), 10000):
                try:
                    await es.delete_by_query(
                        index=settings.COMPONENT_LOG_DATA_STREAM,
                        query={"terms": {"action_id": action_ids[offset:offset + 10000]}},
                        conflicts="proceed",
                        refresh=True,
                    )
                except ApiError as exc:
                    if getattr(exc, "status_code", None) != 404:
                        raise

        if action_ids:
            await ComponentRunModel.find({"action_id": {"$in": action_ids}}).delete()
            await ActionInstanceNodeModel.find({"action_id": {"$in": action_ids}}).delete()
            await ActionInstanceModel.find({"_id": {"$in": action_ids}}).delete()

        await blueprint.delete()
    except Exception:
        blueprint.is_deleted = False
        blueprint.updated_at = datetime.now()
        await blueprint.save()
        await ActionInstanceService._clear_cache("blueprint", blueprint_id)
        raise

    logger.info(f"成功删除蓝图及其历史行动: {blueprint_id}，历史行动数: {len(action_ids)}")
    return ApiResponseSchema.success(message="蓝图及历史行动已删除")
