from datetime import datetime, timezone

from elasticsearch import ApiError
from loguru import logger
from fastapi import APIRouter, Depends
from fastapi import Request
from app.core.config import settings
from app.core.exceptions import ForbiddenException
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
from app.models.action.node_execution import ActionNodeExecutionModel
from app.models.action.schedule import ActionScheduleModel
from app.schemas.action.blueprint import (
    ActionBlueprintSchema,
    ActionBlueprintBaseInfoResponse,
    ActionBlueprintDetailResponseSchema,
    ActionBlueprintUpdateResponseSchema,
    BlueprintEncapsulateRequest,
    BlueprintEncapsulateResponse,
    BlueprintPublishResponse,
    BlueprintRevisionResponse,
    BlueprintScheduleImpactSchema,
    BlueprintValidateResponse,
    TemplateSpecSchema,
)
from app.schemas.general import PageParamsSchema, PageResponseSchema
from app.schemas.response import ApiResponseSchema
from app.schemas.constants import (
    ActionFlowStatusEnum,
    ActionInstanceNodeStatusEnum,
    ActionSchedulingModeEnum,
)
from app.service.action import ActionInstanceService, node_model_to_response
from app.service.action.compiler import BlueprintCompiler
from app.service.action.schedule import validate_blueprint_params
from app.service.auth.service import has_backend_permissions
from app.service.blueprint_revision import BlueprintRevisionService
from app.service.boundary_binding_validator import (
    BlueprintBindingValidationError,
)
from app.models.action.blueprint_revision import ActionBlueprintRevisionModel
from app.models.action.node import ActionNodeModel
from app.schemas.action.interface import BlueprintInterfaceSpec
from app.schemas.constants import ActionInvocationModeEnum
from app.utils.id_lib import generate_id
from app.utils.dict_helper import pack_dict
from app.utils.workflow import count_workflow_paths, graph_model2schemas

logger = logger.bind(name=__name__)

router = APIRouter(prefix="/blueprint", tags=["行动蓝图"])


def _validate_template(data: ActionBlueprintSchema) -> str | None:
    """校验模板参数唯一性和绑定引用。"""
    if not data.is_template:
        return None
    if data.template is None:
        return "模板蓝图必须提供模板配置"

    param_names = [param.name for param in data.template.params]
    if len(param_names) != len(set(param_names)):
        return "参数名称必须唯一"

    for node_bindings in data.template.bindings.values():
        for binding_param in node_bindings.values():
            if binding_param not in param_names:
                return f"绑定引用的参数 '{binding_param}' 不存在"
    return None


def _graph_schema_to_model(data: ActionBlueprintSchema) -> GraphModel:
    """将蓝图请求中的图结构转换为数据库模型。"""
    nodes = [
        GraphNodeModel(
            id=node.id,
            type=node.type,
            position=PositionModel(x=node.position.x, y=node.position.y),
            data=NodeDataModel(
                definition_id=node.data.definition_id,
                version=node.data.version,
                form_data=pack_dict(node.data.form_data),
                node_definition_version=node.data.node_definition_version,
                instance_config=node.data.instance_config,
                interface_port_id=node.data.interface_port_id,
                boundary_binding=node.data.boundary_binding,
            ),
        )
        for node in data.graph.nodes
    ]
    edges = [
        GraphEdgeModel(
            id=edge.id,
            source=edge.source,
            sourceHandle=edge.sourceHandle,
            source_port_id=edge.source_port_id,
            target=edge.target,
            targetHandle=edge.targetHandle,
            target_port_id=edge.target_port_id,
        )
        for edge in data.graph.edges
    ]
    return GraphModel(
        nodes=nodes,
        edges=edges,
        viewport=ViewportModel(
            x=data.graph.viewport.x,
            y=data.graph.viewport.y,
            zoom=data.graph.viewport.zoom,
        ),
    )


async def _compile_blueprint_graph(graph: GraphModel):
    """校验蓝图两种调用模式并返回公开接口。"""
    definitions = await BlueprintCompiler.load_definitions(graph)
    await BlueprintCompiler.hydrate_interface_handle_selections(
        graph,
        definitions,
    )
    BlueprintCompiler.compile(
        graph,
        definitions,
        ActionInvocationModeEnum.STANDALONE,
    )
    subflow_plan = BlueprintCompiler.compile(
        graph,
        definitions,
        ActionInvocationModeEnum.SUBFLOW,
    )
    return BlueprintInterfaceSpec.model_validate(
        subflow_plan.public_interface_snapshot
    )


def _revision_response(
    revision: ActionBlueprintRevisionModel,
) -> BlueprintRevisionResponse:
    """转换不可变Revision响应。"""
    return BlueprintRevisionResponse(
        id=revision.id,
        blueprint_id=revision.blueprint_id,
        version=revision.version,
        revision_number=revision.revision_number,
        content_hash=revision.content_hash,
        interface_snapshot=revision.interface_snapshot,
        published_at=revision.published_at,
        published_by=revision.published_by,
    )


def _blueprint_detail(
    blueprint: ActionBlueprintModel,
) -> ActionBlueprintDetailResponseSchema:
    """将蓝图数据库模型转换为详情响应。"""
    return ActionBlueprintDetailResponseSchema(
        id=blueprint.id,
        name=blueprint.name,
        version=blueprint.version,
        description=blueprint.description,
        target=blueprint.target,
        implementation_period=blueprint.implementation_period,
        default_scheduling_mode=getattr(
            blueprint,
            "default_scheduling_mode",
            ActionSchedulingModeEnum.BARRIER,
        ),
        resource=blueprint.resource,
        graph=graph_model2schemas(blueprint.graph),
        created_at=blueprint.created_at,
        updated_at=blueprint.updated_at,
        is_template=blueprint.is_template,
        template=TemplateSpecSchema(**blueprint.template) if blueprint.template else None,
        interface=getattr(blueprint, "interface", BlueprintInterfaceSpec()),
    )


@router.post("", response_model=ApiResponseSchema[ActionBlueprintDetailResponseSchema], summary="创建蓝图")
async def create_blueprint(data: ActionBlueprintSchema):
    validation_error = _validate_template(data)
    if validation_error:
        return ApiResponseSchema.error(code=240001, message=validation_error)

    graph = _graph_schema_to_model(data)
    try:
        interface = await _compile_blueprint_graph(graph)
    except ValueError as exc:
        return ApiResponseSchema.error(code=240001, message=str(exc))

    blueprint_id = generate_id(data.name + data.version + str(len(data.graph.nodes)) + str(len(data.graph.edges)))

    existing_blueprint = await ActionBlueprintModel.find_one({"_id": blueprint_id})
    if existing_blueprint:
        return ApiResponseSchema.error(code=240901, message=f"蓝图已存在，ID: {blueprint_id}")

    blueprint_model = ActionBlueprintModel(
        id=blueprint_id,
        name=data.name,
        version=data.version,
        description=data.description,
        target=data.target,
        implementation_period=data.implementation_period,
        default_scheduling_mode=data.default_scheduling_mode,
        resource=data.resource,
        graph=graph,
        is_template=data.is_template,
        template=data.template.model_dump() if data.is_template and data.template else None,
        interface=interface,
    )

    await blueprint_model.insert()
    logger.info(f"成功创建蓝图: {blueprint_id}")

    await ActionInstanceService._clear_cache("blueprint", blueprint_id)

    return ApiResponseSchema.success(data=_blueprint_detail(blueprint_model))


@router.get("/list", response_model=PageResponseSchema[ActionBlueprintBaseInfoResponse], summary="获取蓝图列表")
async def get_blueprints(
    params: PageParamsSchema = Depends()
):
    skip = (params.page - 1) * params.page_size

    query = ActionBlueprintModel.find({"is_deleted": False})
    total = await query.count()
    blueprints = await query.sort("-created_at").skip(skip).limit(params.page_size).to_list()

    results = []
    for blueprint in blueprints:
        steps = len(blueprint.graph.nodes)
        branches = count_workflow_paths(blueprint)
        latest_revision = await ActionBlueprintRevisionModel.find(
            {"blueprint_id": blueprint.id, "is_active": True}
        ).sort("-revision_number").first_or_none()
        encapsulated_node_count = await ActionNodeModel.find(
            {
                "source_blueprint_id": blueprint.id,
                "node_kind": "encapsulated",
                "is_deleted": False,
            }
        ).count()

        results.append(ActionBlueprintBaseInfoResponse(
            id=blueprint.id,
            name=blueprint.name,
            version=blueprint.version,
            description=blueprint.description,
            target=blueprint.target,
            implementation_period=blueprint.implementation_period,
            default_scheduling_mode=getattr(
                blueprint,
                "default_scheduling_mode",
                ActionSchedulingModeEnum.BARRIER,
            ),
            created_at=blueprint.created_at,
            updated_at=blueprint.updated_at,
            steps=steps,
            branches=branches,
            is_template=blueprint.is_template,
            latest_revision_number=(
                latest_revision.revision_number if latest_revision else None
            ),
            encapsulated_node_count=encapsulated_node_count,
        ))

    return PageResponseSchema.create(results, total, params.page, params.page_size)


@router.get("/detail/{blueprint_id}", response_model=ApiResponseSchema[ActionBlueprintDetailResponseSchema], summary="获取蓝图详情")
async def get_blueprint(blueprint_id: str):
    blueprint = await ActionBlueprintModel.find_one({"_id": blueprint_id, "is_deleted": False})
    if not blueprint:
        return ApiResponseSchema.error(code=240411, message=f"蓝图不存在，ID: {blueprint_id}")

    return ApiResponseSchema.success(data=_blueprint_detail(blueprint))


@router.put(
    "/{blueprint_id}",
    response_model=ApiResponseSchema[ActionBlueprintUpdateResponseSchema],
    summary="更新蓝图",
)
async def update_blueprint(blueprint_id: str, data: ActionBlueprintSchema):
    """原地更新蓝图，并保护已有行动和调度计划。"""
    blueprint = await ActionBlueprintModel.find_one(
        {"_id": blueprint_id, "is_deleted": False}
    )
    if not blueprint:
        return ApiResponseSchema.error(
            code=240411,
            message=f"蓝图不存在，ID: {blueprint_id}",
        )

    validation_error = _validate_template(data)
    if validation_error:
        return ApiResponseSchema.error(code=240001, message=validation_error)

    new_graph = _graph_schema_to_model(data)
    try:
        interface = await _compile_blueprint_graph(new_graph)
    except ValueError as exc:
        return ApiResponseSchema.error(code=240001, message=str(exc))

    blueprint.name = data.name
    blueprint.version = data.version
    blueprint.description = data.description
    blueprint.target = data.target
    blueprint.implementation_period = data.implementation_period
    blueprint.default_scheduling_mode = data.default_scheduling_mode
    blueprint.resource = data.resource
    blueprint.graph = new_graph
    blueprint.is_template = data.is_template
    blueprint.template = (
        data.template.model_dump()
        if data.is_template and data.template
        else None
    )
    blueprint.interface = interface
    blueprint.updated_at = datetime.now()

    incompatible_schedules = []
    schedules = await ActionScheduleModel.find(
        {
            "blueprint_id": blueprint_id,
            "is_deleted": False,
            "enabled": True,
        }
    ).to_list()
    for schedule in schedules:
        try:
            validate_blueprint_params(blueprint, schedule.params or {})
        except ValueError as exc:
            incompatible_schedules.append((schedule, str(exc)))

    await blueprint.save()
    await ActionInstanceService._clear_cache("blueprint", blueprint_id)

    disabled_schedules = []
    for schedule, reason in incompatible_schedules:
        schedule.enabled = False
        schedule.next_run_at = None
        schedule.last_trigger_status = "invalid"
        schedule.last_error = f"蓝图更新后参数不兼容：{reason}"
        schedule.updated_at = datetime.now(timezone.utc)
        await schedule.save()
        disabled_schedules.append(
            BlueprintScheduleImpactSchema(
                id=schedule.id,
                name=schedule.name,
                reason=reason,
            )
        )

    logger.info(
        f"成功更新蓝图: {blueprint_id}，停用调度计划: {len(disabled_schedules)}"
    )
    message = "蓝图更新成功"
    if disabled_schedules:
        message += f"，已停用 {len(disabled_schedules)} 个参数不兼容的调度计划"
    return ApiResponseSchema.success(
        message=message,
        data=ActionBlueprintUpdateResponseSchema(
            blueprint=_blueprint_detail(blueprint),
            disabled_schedules=disabled_schedules,
        ),
    )


@router.post(
    "/{blueprint_id}/validate",
    response_model=ApiResponseSchema[BlueprintValidateResponse],
    summary="校验蓝图执行图",
)
async def validate_blueprint(blueprint_id: str):
    blueprint = await ActionBlueprintModel.find_one(
        {"_id": blueprint_id, "is_deleted": False}
    )
    if not blueprint:
        return ApiResponseSchema.error(
            code=240411,
            message=f"蓝图不存在，ID: {blueprint_id}",
        )
    try:
        _, subflow, _ = await BlueprintRevisionService.validate(blueprint)
    except BlueprintBindingValidationError as exc:
        return ApiResponseSchema.success(
            data=BlueprintValidateResponse(
                valid=False,
                errors=[
                    issue.model_dump(mode="python")
                    for issue in exc.issues
                ],
            )
        )
    except ValueError as exc:
        return ApiResponseSchema.success(
            data=BlueprintValidateResponse(
                valid=False,
                errors=[{"code": "blueprint_invalid", "message": str(exc)}],
            )
        )
    return ApiResponseSchema.success(
        data=BlueprintValidateResponse(
            valid=True,
            interface=BlueprintInterfaceSpec.model_validate(
                subflow.public_interface_snapshot
            ),
        )
    )


@router.post(
    "/{blueprint_id}/publish",
    response_model=ApiResponseSchema[BlueprintPublishResponse],
    summary="发布不可变蓝图Revision",
)
async def publish_blueprint(blueprint_id: str, request: Request):
    blueprint = await ActionBlueprintModel.find_one(
        {"_id": blueprint_id, "is_deleted": False}
    )
    if not blueprint:
        return ApiResponseSchema.error(
            code=240411,
            message=f"蓝图不存在，ID: {blueprint_id}",
        )
    user = getattr(getattr(request.state, "auth_context", None), "user", None)
    try:
        revision = await BlueprintRevisionService.publish(
            blueprint,
            published_by=getattr(user, "id", None),
        )
    except ValueError as exc:
        return ApiResponseSchema.error(code=240001, message=str(exc))
    await ActionInstanceService._clear_cache("blueprint", blueprint_id)
    return ApiResponseSchema.success(
        data=BlueprintPublishResponse(
            revision=_revision_response(revision),
        )
    )


@router.post(
    "/{blueprint_id}/encapsulate",
    response_model=ApiResponseSchema[BlueprintEncapsulateResponse],
    summary="封装蓝图为节点",
)
async def encapsulate_blueprint(
    blueprint_id: str,
    data: BlueprintEncapsulateRequest,
    request: Request,
):
    blueprint = await ActionBlueprintModel.find_one(
        {"_id": blueprint_id, "is_deleted": False}
    )
    if not blueprint:
        return ApiResponseSchema.error(
            code=240411,
            message=f"蓝图不存在，ID: {blueprint_id}",
        )
    user = getattr(getattr(request.state, "auth_context", None), "user", None)
    if user is None or not await has_backend_permissions(
        user,
        [
            "operation:action:blueprint:read",
            "operation:action:node:create",
        ],
    ):
        raise ForbiddenException("封装蓝图需要蓝图读取和节点创建权限")
    try:
        revision = await BlueprintRevisionService.publish(
            blueprint,
            published_by=getattr(user, "id", None),
        )
        node = await BlueprintRevisionService.encapsulate(
            blueprint,
            revision,
            node_name=data.node_name,
            description=data.description,
            category=data.category.value,
            mode=data.mode,
            target_encapsulated_node_id=data.target_encapsulated_node_id,
        )
    except ValueError as exc:
        return ApiResponseSchema.error(code=240001, message=str(exc))
    node_response = await node_model_to_response(node)
    return ApiResponseSchema.success(
        data=BlueprintEncapsulateResponse(
            revision=_revision_response(revision),
            encapsulated_node=node_response.model_dump(mode="python"),
            generated_handles=[
                handle.model_dump(mode="python")
                for handle in node_response.handles
            ],
            generated_inputs=[
                input_item.model_dump(mode="python")
                for input_item in node_response.inputs
            ],
        )
    )


@router.get(
    "/{blueprint_id}/revisions",
    response_model=ApiResponseSchema[list[BlueprintRevisionResponse]],
    summary="获取蓝图Revision列表",
)
async def get_blueprint_revisions(blueprint_id: str):
    revisions = await ActionBlueprintRevisionModel.find(
        {"blueprint_id": blueprint_id, "is_active": True}
    ).sort("-revision_number").to_list()
    return ApiResponseSchema.success(
        data=[_revision_response(revision) for revision in revisions]
    )


@router.get(
    "/revisions/{revision_id}",
    response_model=ApiResponseSchema[BlueprintRevisionResponse],
    summary="获取蓝图Revision详情",
)
async def get_blueprint_revision(revision_id: str):
    revision = await ActionBlueprintRevisionModel.find_one(
        {"_id": revision_id, "is_active": True}
    )
    if not revision:
        return ApiResponseSchema.error(
            code=240411,
            message=f"蓝图Revision不存在，ID: {revision_id}",
        )
    return ApiResponseSchema.success(data=_revision_response(revision))


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
        ActionFlowStatusEnum.PARTIALLY_COMPLETED.value,
        ActionFlowStatusEnum.FAILED.value,
        ActionFlowStatusEnum.CANCELLED.value,
        ActionFlowStatusEnum.TIMEOUT.value,
        ActionFlowStatusEnum.STOPPED.value,
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

    pending_queue_cleanup = await ActionInstanceModel.find_one(
        {
            "blueprint_id": blueprint_id,
            "queue_cleanup_state": {"$exists": True, "$ne": "completed"},
        }
    )
    if pending_queue_cleanup:
        blueprint.is_deleted = False
        blueprint.updated_at = datetime.now()
        await blueprint.save()
        await ActionInstanceService._clear_cache("blueprint", blueprint_id)
        return ApiResponseSchema.error(
            code=240423,
            message="该蓝图仍有行动队列等待清理，暂时无法删除",
        )

    try:
        action_instances = await ActionInstanceModel.find({"blueprint_id": blueprint_id}).to_list()
        action_ids = [action.id for action in action_instances]

        pending_subflow_reconciliation = (
            await ActionNodeExecutionModel.find_one(
                {
                    "child_action_id": {"$in": action_ids},
                    "status": {
                        "$nin": [
                            ActionInstanceNodeStatusEnum.COMPLETED.value,
                            ActionInstanceNodeStatusEnum.FAILED.value,
                            ActionInstanceNodeStatusEnum.CANCELLED.value,
                            ActionInstanceNodeStatusEnum.TIMEOUT.value,
                        ]
                    },
                }
            )
            if action_ids
            else None
        )
        if pending_subflow_reconciliation:
            blueprint.is_deleted = False
            blueprint.updated_at = datetime.now()
            await blueprint.save()
            await ActionInstanceService._clear_cache("blueprint", blueprint_id)
            return ApiResponseSchema.error(
                code=240423,
                message="该蓝图仍有嵌入式行动等待父流程对账，暂时无法删除",
            )

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
