import re
from datetime import datetime
from typing import List
from fastapi import APIRouter, BackgroundTasks, Depends, Query, Request
from app.models.action.action import ActionInstanceModel, ActionInstanceNodeModel
from app.models.action.component_run import ComponentRunModel
from app.models.action.node_execution import ActionNodeExecutionModel
from app.models.action.blueprint import ActionBlueprintModel
from app.schemas.action.action import (
    ActionControlResponse,
    ActionDetailResponse,
    ActionHistorySummaryResponse,
    ActionInstanceBaseInfoResponse,
    ActionNodeDetailResponse,
    StartActionRequest,
    StartActionResponse,
)
from app.schemas.general import PageParamsSchema, PageResponseSchema
from app.schemas.action.log import ActionNodeLogPage
from app.schemas.response import ApiResponseSchema
from app.schemas.constants import (
    ActionInstanceNodeStatusEnum,
    ActionFlowStatusEnum,
    ActionSchedulingModeEnum,
    ActionVisibilityEnum,
)
from app.service.action import ActionInstanceService, node_model_to_response
from app.service.action.log import ActionLogService
from app.utils.dict_helper import unpack_dict
from app.utils.workflow import graph_model2schemas

router = APIRouter(tags=["行动实例"])


def _build_history_filters(
    status: ActionFlowStatusEnum | None = None,
    keyword: str | None = None,
    created_from: datetime | None = None,
    created_to: datetime | None = None,
) -> dict:
    """构造普通行动历史的服务端过滤条件。"""
    filters: dict = {}
    if ActionInstanceModel._document_settings is not None:
        filters["visibility"] = {"$ne": ActionVisibilityEnum.EMBEDDED}
    if status is not None:
        filters["status"] = status
    normalized_keyword = (keyword or "").strip()
    if normalized_keyword:
        pattern = re.compile(re.escape(normalized_keyword), re.IGNORECASE)
        filters["$or"] = [
            {"blueprint_snapshot.name": {"$regex": pattern}},
            {"blueprint_snapshot.description": {"$regex": pattern}},
        ]
    if created_from is not None or created_to is not None:
        filters["created_at"] = {}
        if created_from is not None:
            filters["created_at"]["$gte"] = created_from
        if created_to is not None:
            filters["created_at"]["$lte"] = created_to
    return filters


@router.post("/start", response_model=ApiResponseSchema[StartActionResponse], summary="开始行动")
async def start_action(
    data: StartActionRequest,
    background_tasks: BackgroundTasks,
    request: Request,
):
    blueprint = await ActionBlueprintModel.find_one({"_id": data.blueprint_id, "is_deleted": False})
    if not blueprint:
        return ApiResponseSchema.error(code=240411, message=f"蓝图不存在，ID: {data.blueprint_id}")

    user = getattr(getattr(request.state, "auth_context", None), "user", None)
    result, message = await ActionInstanceService.init(
        data.blueprint_id,
        data.params,
        initiator_user_id=getattr(user, "id", None),
        debug=data.debug,
        scheduling_mode=data.scheduling_mode,
    )
    if not result:
        return ApiResponseSchema.error(code=250004, message=message)
    background_tasks.add_task(ActionInstanceService.start, message)
    created_action = await ActionInstanceModel.find_one({"_id": message})
    effective_scheduling_mode = (
        ActionInstanceService._get_scheduling_mode(created_action)
        if created_action is not None
        else data.scheduling_mode
        or getattr(
            blueprint,
            "default_scheduling_mode",
            ActionSchedulingModeEnum.BARRIER,
        )
    )

    return ApiResponseSchema.success(
        data=StartActionResponse(
            action_id=message,
            scheduling_mode=effective_scheduling_mode,
        )
    )


@router.get("/list", response_model=PageResponseSchema[ActionInstanceBaseInfoResponse], summary="获取行动列表")
async def get_action_instances(
    params: PageParamsSchema = Depends(),
    status: ActionFlowStatusEnum | None = None,
    keyword: str | None = None,
    created_from: datetime | None = None,
    created_to: datetime | None = None,
):
    skip = (params.page - 1) * params.page_size
    filters = _build_history_filters(
        status=status,
        keyword=keyword,
        created_from=created_from,
        created_to=created_to,
    )
    if not filters:
        query = ActionInstanceModel.find_all()
    else:
        query = ActionInstanceModel.find(filters)
    total = await query.count()
    action_instances = await query.sort("-created_at").skip(skip).limit(params.page_size).to_list()

    results: List[ActionInstanceBaseInfoResponse] = []
    for action_instance in action_instances:
        blueprint = await ActionInstanceService.get_action_blueprint(action_instance)
        completed_steps = len(action_instance.finished_nodes_instance) if action_instance.finished_nodes_instance else 0
        total_steps = len(action_instance.execution_plan_snapshot.nodes)

        results.append(ActionInstanceBaseInfoResponse(
            id=action_instance.id,
            name=blueprint.name,
            description=blueprint.description,
            status=action_instance.status,
            debug=getattr(action_instance, "debug", False),
            scheduling_mode=getattr(
                action_instance.execution_plan_snapshot,
                "scheduling_mode",
                ActionSchedulingModeEnum.BARRIER,
            ),
            start_at=action_instance.start_at,
            paused_at=action_instance.paused_at,
            finished_at=action_instance.finished_at,
            duration=action_instance.duration,
            progress=action_instance.progress,
            completed_steps=completed_steps,
            total_steps=total_steps,
            schedule_id=action_instance.schedule_id,
            schedule_name=action_instance.schedule_name,
            schedule_priority=action_instance.schedule_priority,
            scheduled_for=action_instance.scheduled_for,
            created_at=action_instance.created_at,
        ))

    return PageResponseSchema.create(results, total, params.page, params.page_size)


@router.get(
    "/summary",
    response_model=ApiResponseSchema[ActionHistorySummaryResponse],
    summary="获取行动历史全量统计",
)
async def get_action_history_summary():
    base_filter = _build_history_filters()

    def with_status(status_filter):
        """在普通行动过滤条件上增加状态条件。"""
        return {**base_filter, "status": status_filter}

    total = await ActionInstanceModel.find(base_filter).count()
    completed = await ActionInstanceModel.find(
        with_status(ActionFlowStatusEnum.COMPLETED)
    ).count()
    partially_completed = await ActionInstanceModel.find(
        with_status(ActionFlowStatusEnum.PARTIALLY_COMPLETED)
    ).count()
    running = await ActionInstanceModel.find(
        with_status(ActionFlowStatusEnum.RUNNING)
    ).count()
    failed = await ActionInstanceModel.find(
        with_status(
            {
                "$in": [
                    ActionFlowStatusEnum.FAILED,
                    ActionFlowStatusEnum.TIMEOUT,
                ]
            }
        )
    ).count()
    return ApiResponseSchema.success(
        data=ActionHistorySummaryResponse(
            total=total,
            completed=completed,
            partially_completed=partially_completed,
            running=running,
            failed=failed,
        )
    )


@router.get("/detail/{action_id}", response_model=ApiResponseSchema[ActionDetailResponse], summary="获取行动详情")
async def get_action_detail(action_id: str):
    action_instance = await ActionInstanceModel.find_one({"_id": action_id})
    if not action_instance:
        return ApiResponseSchema.error(code=240412, message=f"行动不存在，ID: {action_id}")

    blueprint = await ActionInstanceService.get_action_blueprint(action_instance)
    completed_steps = len(action_instance.finished_nodes_instance) if action_instance.finished_nodes_instance else 0
    total_steps = len(action_instance.execution_plan_snapshot.nodes)

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
    plan_node_map = {
        node.id: node
        for node in action_instance.execution_plan_snapshot.nodes
    }
    for node_id in action_instance.nodes_id:
        if node_id not in node_instance_map:
            node_details[node_id] = ActionNodeDetailResponse(
                status=ActionInstanceNodeStatusEnum.UNKNOWN,
            )
            continue

        node_instance = node_instance_map[node_id]
        node_definition = await ActionInstanceService.get_instance_node_definition(
            node_instance
        )
        plan_node = plan_node_map.get(node_id)
        component_runs = await ComponentRunModel.find(
            {"node_instance_id": node_instance.id}
        ).to_list()
        execution = (
            await ActionNodeExecutionModel.find_one(
                {"_id": getattr(node_instance, "current_execution_id", None)}
            )
            if getattr(node_instance, "current_execution_id", None)
            else None
        )
        child_action = (
            await ActionInstanceModel.find_one({"_id": execution.child_action_id})
            if execution and execution.child_action_id
            else None
        )

        combined_outputs = dict(node_instance.outputs)
        reference_outputs: dict[str, list[str]] = {}
        for binding in node_instance.reference_queue_bindings.values():
            reference_outputs.setdefault(binding.source_port_id, []).append(
                binding.queue_name
            )
        for source_port_id, queue_names in reference_outputs.items():
            _, handle_config = await (
                ActionInstanceService.resolve_node_handle_definition(
                    node_definition,
                    source_port_id,
                )
            )
            if handle_config:
                combined_outputs[source_port_id] = {
                    "type": "reference",
                    "key": handle_config.handle_name,
                    "value": queue_names,
                }

        node_details[node_id] = ActionNodeDetailResponse(
            node_instance_id=node_instance.id,
            status=node_instance.status,
            progress=node_instance.progress,
            start_at=node_instance.start_at,
            finished_at=node_instance.finished_at,
            duration=node_instance.duration,
            inputs=node_instance.inputs,
            outputs=combined_outputs,
            error_message=node_instance.error_message,
            component_runs=[
                {
                    "component_run_id": run.id,
                    "component_id": run.component_id,
                    "attempt": run.attempt,
                    "status": run.status.value,
                    "progress": run.progress,
                }
                for run in component_runs
            ],
            log_count=sum(run.log_count for run in component_runs),
            error_log_count=sum(run.error_log_count for run in component_runs),
            dropped_log_count=sum(run.dropped_log_count for run in component_runs),
            driver=(
                execution.driver
                if execution
                else node_instance.execution_spec_snapshot.driver.value
            ),
            handler=(
                execution.handler
                if execution
                else node_instance.execution_spec_snapshot.handler
            ),
            node_kind=(
                plan_node.node_kind
                if plan_node
                else node_definition.node_kind
                if node_definition
                else None
            ),
            definition_origin=(
                node_definition.definition_origin if node_definition else None
            ),
            definition=(
                (
                    await node_model_to_response(node_definition)
                ).model_dump(mode="json")
                if node_definition
                else None
            ),
            current_execution_id=getattr(node_instance, "current_execution_id", None),
            execution_ids=getattr(node_instance, "execution_ids", []),
            provider_run_id=execution.provider_run_id if execution else None,
            extension_state=execution.extension_state if execution else {},
            extension_result=execution.extension_result if execution else {},
            skip_reason=getattr(node_instance, "skip_reason", None),
            embedded_action_id=execution.child_action_id if execution else None,
            source_blueprint_id=(
                node_definition.source_blueprint_id
                if node_definition
                else (
                    plan_node.execution.config.get("blueprint_id")
                    if plan_node
                    else None
                )
            ),
            source_revision_id=(
                node_definition.source_revision_id
                if node_definition
                else (
                    plan_node.execution.config.get("revision_id")
                    if plan_node
                    else None
                )
            ),
            child_status=child_action.status.value if child_action else None,
            child_progress=child_action.progress if child_action else None,
        )

    return ApiResponseSchema.success(data=ActionDetailResponse(
        id=action_instance.id,
        name=blueprint.name,
        description=blueprint.description,
        status=action_instance.status,
        debug=getattr(action_instance, "debug", False),
        scheduling_mode=getattr(
            action_instance.execution_plan_snapshot,
            "scheduling_mode",
            ActionSchedulingModeEnum.BARRIER,
        ),
        resource=blueprint.resource,
        implementation_period=action_instance.implementation_period,
        start_at=action_instance.start_at,
        paused_at=action_instance.paused_at,
        finished_at=action_instance.finished_at,
        duration=action_instance.duration,
        progress=action_instance.progress,
        completed_steps=completed_steps,
        total_steps=total_steps,
        schedule_id=action_instance.schedule_id,
        schedule_name=action_instance.schedule_name,
        schedule_priority=action_instance.schedule_priority,
        scheduled_for=action_instance.scheduled_for,
        created_at=action_instance.created_at,
        graph=graph,
        node_details=node_details
    ))


@router.get(
    "/instances/{action_id}/nodes/{node_id}/embedded",
    response_model=ApiResponseSchema[ActionDetailResponse],
    summary="获取封装节点嵌入式行动详情",
)
async def get_embedded_action_detail(action_id: str, node_id: str):
    parent_node = await ActionInstanceNodeModel.find_one(
        {"action_id": action_id, "node_id": node_id}
    )
    if parent_node is None or not parent_node.current_execution_id:
        return ApiResponseSchema.error(code=240417, message="封装节点执行记录不存在")
    execution = await ActionNodeExecutionModel.find_one(
        {
            "_id": parent_node.current_execution_id,
            "action_id": action_id,
            "node_instance_id": parent_node.id,
        }
    )
    if execution is None or not execution.child_action_id:
        return ApiResponseSchema.error(code=240412, message="嵌入式行动不存在")
    child = await ActionInstanceModel.find_one(
        {
            "_id": execution.child_action_id,
            "visibility": ActionVisibilityEnum.EMBEDDED,
            "parent_action_id": action_id,
            "parent_node_instance_id": parent_node.id,
        }
    )
    if child is None:
        return ApiResponseSchema.error(code=240412, message="嵌入式行动关系无效")
    return await get_action_detail(child.id)


@router.get(
    "/instances/{action_id}/nodes/{node_id}/embedded/logs",
    response_model=ApiResponseSchema[ActionNodeLogPage],
    summary="聚合查询封装节点内部日志",
)
async def get_embedded_action_logs(
    action_id: str,
    node_id: str,
    cursor: str | None = None,
    before_cursor: str | None = None,
    limit: int = Query(default=200, ge=1, le=500),
    levels: list[str] | None = Query(default=None),
    sources: list[str] | None = Query(default=None),
    component_run_id: str | None = None,
    keyword: str | None = Query(default=None, max_length=256),
):
    parent_node = await ActionInstanceNodeModel.find_one(
        {"action_id": action_id, "node_id": node_id}
    )
    execution = (
        await ActionNodeExecutionModel.find_one(
            {"_id": parent_node.current_execution_id}
        )
        if parent_node and parent_node.current_execution_id
        else None
    )
    child = (
        await ActionInstanceModel.find_one(
            {
                "_id": execution.child_action_id,
                "visibility": ActionVisibilityEnum.EMBEDDED,
                "parent_action_id": action_id,
                "parent_node_instance_id": parent_node.id,
            }
        )
        if execution and execution.child_action_id
        else None
    )
    if child is None:
        return ApiResponseSchema.error(code=240412, message="嵌入式行动不存在")
    try:
        page = await ActionLogService.query_action(
            child.id,
            cursor=cursor,
            before_cursor=before_cursor,
            limit=limit,
            levels=levels,
            sources=sources,
            component_run_id=component_run_id,
            keyword=keyword,
        )
    except ValueError as exc:
        return ApiResponseSchema.error(code=240420, message=str(exc))
    return ApiResponseSchema.success(data=page)


@router.post(
    "/{action_id}/retry",
    response_model=ApiResponseSchema[StartActionResponse],
    summary="重试或重新执行行动",
)
async def retry_action(
    action_id: str,
    background_tasks: BackgroundTasks,
    request: Request,
):
    """以失败、超时、已完成或部分完成行动的冻结上下文创建全新行动。"""
    user = getattr(getattr(request.state, "auth_context", None), "user", None)
    success, message = await ActionInstanceService.retry(
        action_id,
        initiator_user_id=getattr(user, "id", None),
    )
    if not success:
        return ApiResponseSchema.error(code=240424, message=message)
    created_action = await ActionInstanceModel.find_one({"_id": message})
    if created_action is None:
        return ApiResponseSchema.error(
            code=250004,
            message="重试或重新执行行动的创建结果不存在",
        )
    background_tasks.add_task(ActionInstanceService.start, message)
    return ApiResponseSchema.success(
        data=StartActionResponse(
            action_id=message,
            scheduling_mode=ActionInstanceService._get_scheduling_mode(
                created_action
            ),
        )
    )


async def _control_action(
    action_id: str,
    operation: str,
) -> ApiResponseSchema[ActionControlResponse]:
    """执行行动控制操作并统一返回状态。"""
    handlers = {
        "pause": ActionInstanceService.pause,
        "resume": ActionInstanceService.resume,
        "stop": ActionInstanceService.stop,
    }
    success, message = await handlers[operation](action_id)
    action = await ActionInstanceModel.find_one({"_id": action_id})
    if not success or action is None:
        return ApiResponseSchema.error(code=240424, message=message)
    return ApiResponseSchema.success(
        data=ActionControlResponse(action_id=action_id, status=action.status),
        message=message,
    )


@router.post(
    "/{action_id}/pause",
    response_model=ApiResponseSchema[ActionControlResponse],
    summary="暂停行动",
)
async def pause_action(action_id: str):
    return await _control_action(action_id, "pause")


@router.post(
    "/{action_id}/resume",
    response_model=ApiResponseSchema[ActionControlResponse],
    summary="恢复行动",
)
async def resume_action(action_id: str):
    return await _control_action(action_id, "resume")


@router.post(
    "/{action_id}/stop",
    response_model=ApiResponseSchema[ActionControlResponse],
    summary="停止行动",
)
async def stop_action(action_id: str):
    return await _control_action(action_id, "stop")
