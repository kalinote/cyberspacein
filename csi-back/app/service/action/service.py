
"""行动实例编排与运行服务。"""

import asyncio
from datetime import datetime, timedelta
import random
from types import SimpleNamespace
from typing import Any
from beanie.operators import In
from beanie.exceptions import CollectionWasNotInitialized
from pymongo.errors import DuplicateKeyError
from app.core.config import settings
from app.models.action.action import ActionConfigIOModel, ActionInstanceModel, ActionInstanceNodeModel
from app.models.action.component_run import ComponentRunModel
from app.models.action.node_execution import ActionNodeExecutionModel
from app.models.action.reference_bridge import (
    ReferenceBridgeDirectionEnum,
    ReferenceBridgeModel,
    ReferenceBridgeStatusEnum,
)
from app.models.action.blueprint_revision import ActionBlueprintRevisionModel
from app.models.runtime_event import RuntimeDomainEventModel
from loguru import logger
from app.models.action.configs import ActionNodesHandleConfigModel
from app.models.action.node import ActionNodeModel
from app.schemas.action.node import (
    ActionNodeHandleResponse,
    ActionNodeInputResponse,
    ActionNodeOption,
    ActionNodeResponse,
)
from app.schemas.action.sdk import SDKResultRequest
from app.schemas.constants import (
    ActionConfigIOTypeEnum,
    ActionFlowStatusEnum,
    ActionInstanceNodeStatusEnum,
    ActionNodeTypeEnum,
    ActionExecutionDriverEnum,
    ActionInvocationModeEnum,
    ActionNodeKindEnum,
    ActionVisibilityEnum,
    ComponentRunStatusEnum,
)
from app.schemas.action.execution import (
    NodeDefinitionContract,
    NodeExecutionContext,
    NodeExecutionOutcome,
    NodeExecutionSpec,
)
from app.schemas.action.reference import (
    ReferenceProducerKindEnum,
    ReferenceProtocolEnum,
    ReferenceQueueBinding,
    ReferenceStreamDescriptor,
)
from app.service.component.service import cancel_component_run
from app.service.action.alert_source import publish_action_status_observation
from app.service.action.compiler import BlueprintCompiler
from app.service.action.log import ActionLogService
from app.service.blueprint_revision import BlueprintRevisionService
from app.service.native_nodes.registry import native_handlers
from app.service.native_nodes.policy_registry import execution_policies
from app.service.node_executors.component import ComponentNodeExecutor
from app.service.node_executors.native import BackendNativeNodeExecutor
from app.service.node_executors.registry import node_executors
from app.service.node_executors.subflow import SubflowNodeExecutor
from app.service.runtime_event import RuntimeDomainEventService
from app.service.reference_bridge import ReferenceBridgeService
from app.utils.dict_helper import pack_dict, unpack_dict
from app.utils.id_lib import generate_id
from app.models.action.blueprint import (
    ActionBlueprintModel,
    ActionBlueprintSnapshotModel,
    create_blueprint_snapshot,
)
from app.db.rabbitmq import delete_queue, publish_reference_control
from app.db.redis import get_redis

logger = logger.bind(name=__name__)


async def node_model_to_response(node: ActionNodeModel) -> ActionNodeResponse:
    handle_ids = [h.handle_config_id or h.id for h in node.handles]
    handle_configs = await ActionNodesHandleConfigModel.find(In(ActionNodesHandleConfigModel.id, handle_ids)).to_list()
    handle_config_map = {c.id: c for c in handle_configs}
    handles_response = []
    for handle in node.handles:
        handle_config = handle_config_map.get(handle.handle_config_id or handle.id)
        custom_style = unpack_dict(handle_config.custom_style) if handle_config else {}
        custom_style = dict(custom_style)
        custom_style.update(unpack_dict(handle.custom_style) or {})
        handles_response.append(ActionNodeHandleResponse(
            id=handle.id,
            port_id=handle.port_id,
            handle_config_id=handle.handle_config_id or (
                handle_config.id if handle_config else None
            ),
            interface_type_id=handle.interface_type_id,
            compatible_interface_type_ids=handle.compatible_interface_type_ids,
            relabel=handle.relabel,
            type=handle.type,
            position=handle.position,
            custom_style=custom_style,
            handle_name=handle.handle_name or (
                handle_config.handle_name if handle_config else ""
            ),
            data_type=handle.data_type or (
                handle_config.type if handle_config else "value"
            ),
            label=handle.label or (
                handle_config.label if handle_config else ""
            ),
            color=handle.color or (
                handle_config.color if handle_config else ""
            ),
            other_compatible_interfaces=handle_config.other_compatible_interfaces if handle_config else [],
        ))
    inputs_response = []
    for input_item in node.inputs:
        options = [ActionNodeOption(**opt) for opt in input_item.options] if input_item.options else None
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
    return ActionNodeResponse(
        id=node.id,
        name=node.name,
        description=node.description,
        type=ActionNodeTypeEnum(node.type),
        node_kind=node.node_kind,
        category=node.category,
        execution=node.execution,
        extension=node.extension,
        definition_origin=node.definition_origin,
        builtin_key=node.builtin_key,
        node_family_id=node.node_family_id,
        definition_version=node.definition_version,
        enabled=node.enabled,
        disabled_at=node.disabled_at,
        disabled_by=node.disabled_by,
        is_latest=node.is_latest,
        source_blueprint_id=node.source_blueprint_id,
        source_revision_id=node.source_revision_id,
        version=node.version,
        handles=handles_response,
        inputs=inputs_response,
        default_configs=unpack_dict(node.default_configs),
        related_components=node.related_components,
        component_timeouts=node.component_timeouts,
        command=node.command,
        command_args=node.command_args
    )


class ActionInstanceService:
    @staticmethod
    def _build_reference_queue_bindings(
        action_id: str,
        execution_plan,
        graph,
        definitions: dict[str, ActionNodeModel],
    ) -> dict[str, dict[str, ReferenceQueueBinding]]:
        """按执行边预分配 Reference 队列，并冻结队列所有权和生产者。"""
        graph_nodes = {node.id: node for node in graph.nodes}
        bindings_by_source: dict[str, dict[str, ReferenceQueueBinding]] = {}
        for edge in execution_plan.edges:
            if edge.data_type != "reference":
                continue
            source_node = graph_nodes.get(edge.source)
            definition = (
                definitions.get(source_node.data.definition_id)
                if source_node is not None
                else None
            )
            node_instance_id = generate_id(action_id + edge.source)
            producer_kind = ReferenceProducerKindEnum.COMPONENT
            producer_ids: list[str] = []
            if definition is not None:
                if definition.builtin_key == "blueprint.input":
                    producer_kind = ReferenceProducerKindEnum.INPUT_BRIDGE
                    producer_ids = [node_instance_id]
                elif definition.node_kind == ActionNodeKindEnum.ENCAPSULATED:
                    producer_kind = ReferenceProducerKindEnum.OUTPUT_BRIDGE
                    producer_ids = [node_instance_id]
                elif definition.node_kind == ActionNodeKindEnum.BACKEND_NATIVE:
                    producer_kind = ReferenceProducerKindEnum.NATIVE
                    producer_ids = [node_instance_id]
                else:
                    producer_ids = [
                        generate_id(f"{node_instance_id}:{component_id}:1")
                        for component_id in definition.related_components
                    ]
            stream_id = generate_id(f"reference_stream:{action_id}:{edge.id}")
            queue_name = generate_id(f"reference_queue:{action_id}:{edge.id}")
            bindings_by_source.setdefault(edge.source, {})[edge.id] = (
                ReferenceQueueBinding(
                    edge_id=edge.id,
                    stream_id=stream_id,
                    queue_name=queue_name,
                    owner_action_id=action_id,
                    source_node_id=edge.source,
                    source_port_id=edge.source_port_id,
                    target_node_id=edge.target,
                    target_port_id=edge.target_port_id,
                    protocol_version=ReferenceProtocolEnum.EOS_V1,
                    producer_kind=producer_kind,
                    expected_producer_ids=producer_ids,
                )
            )
        return bindings_by_source

    @staticmethod
    def _get_cache_key(cache_type: str, cache_id: str) -> str:
        return f"action:cache:{cache_type}:{cache_id}"
    
    @staticmethod
    def _serialize_model(model: Any) -> str:
        return model.model_dump_json()
    
    @staticmethod
    async def _clear_cache(cache_type: str, cache_id: str):
        try:
            redis_client = get_redis()
            if redis_client:
                cache_key = ActionInstanceService._get_cache_key(cache_type, cache_id)
                await redis_client.delete(cache_key)
                logger.info(f"已清理缓存: {cache_key}")
        except Exception as e:
            logger.warning(f"清理缓存失败: {e}")
    
    @staticmethod
    async def get_blueprint(blueprint_id: str) -> ActionBlueprintModel:
        try:
            redis_client = get_redis()
            if redis_client:
                cache_key = ActionInstanceService._get_cache_key("blueprint", blueprint_id)
                cached_data = await redis_client.get(cache_key)
                if cached_data:
                    return ActionBlueprintModel.model_validate_json(cached_data)
        except Exception as e:
            logger.warning(f"从Redis读取蓝图缓存失败: {e}")
        
        blueprint = await ActionBlueprintModel.find_one({"_id": blueprint_id, "is_deleted": False})
        if blueprint:
            try:
                redis_client = get_redis()
                if redis_client:
                    cache_key = ActionInstanceService._get_cache_key("blueprint", blueprint_id)
                    await redis_client.setex(
                        cache_key,
                        settings.ACTION_CACHE_TTL,
                        ActionInstanceService._serialize_model(blueprint)
                    )
            except Exception as e:
                logger.warning(f"写入Redis蓝图缓存失败: {e}")
        
        return blueprint

    @staticmethod
    async def get_action_blueprint(
        action: ActionInstanceModel,
    ) -> ActionBlueprintSnapshotModel:
        """返回行动创建时冻结的蓝图快照。"""
        return action.blueprint_snapshot
    
    @staticmethod
    async def get_node_definition(node_definition_id: str) -> ActionNodeModel:
        try:
            redis_client = get_redis()
            if redis_client:
                cache_key = ActionInstanceService._get_cache_key("node", node_definition_id)
                cached_data = await redis_client.get(cache_key)
                if cached_data:
                    return ActionNodeModel.model_validate_json(cached_data)
        except Exception as e:
            logger.warning(f"从Redis读取节点定义缓存失败: {e}")
        
        node_definition = await ActionNodeModel.find_one({"_id": node_definition_id, "is_deleted": False})
        if node_definition:
            try:
                redis_client = get_redis()
                if redis_client:
                    cache_key = ActionInstanceService._get_cache_key("node", node_definition_id)
                    await redis_client.setex(
                        cache_key,
                        settings.ACTION_CACHE_TTL,
                        ActionInstanceService._serialize_model(node_definition)
                    )
            except Exception as e:
                logger.warning(f"写入Redis节点定义缓存失败: {e}")
        
        return node_definition

    @staticmethod
    async def get_instance_node_definition(
        node_instance: ActionInstanceNodeModel,
    ) -> ActionNodeModel:
        """恢复行动节点创建时冻结的节点定义快照。"""
        return ActionNodeModel.model_validate(node_instance.definition_snapshot)

    @staticmethod
    async def get_handle_definition(handle_definition_id: str) -> ActionNodesHandleConfigModel:
        try:
            redis_client = get_redis()
            if redis_client:
                cache_key = ActionInstanceService._get_cache_key("handle", handle_definition_id)
                cached_data = await redis_client.get(cache_key)
                if cached_data:
                    return ActionNodesHandleConfigModel.model_validate_json(cached_data)
        except Exception as e:
            logger.warning(f"从Redis读取handle定义缓存失败: {e}")
        
        handle_definition = await ActionNodesHandleConfigModel.find_one({"_id": handle_definition_id})
        if handle_definition:
            try:
                redis_client = get_redis()
                if redis_client:
                    cache_key = ActionInstanceService._get_cache_key("handle", handle_definition_id)
                    await redis_client.setex(
                        cache_key,
                        settings.ACTION_CACHE_TTL,
                        ActionInstanceService._serialize_model(handle_definition)
                    )
            except Exception as e:
                logger.warning(f"写入Redis handle定义缓存失败: {e}")
        
        return handle_definition

    @staticmethod
    async def get_handle_definition_by_name(handle_name: str) -> ActionNodesHandleConfigModel:
        handle_id = None
        try:
            redis_client = get_redis()
            if redis_client:
                cache_key = ActionInstanceService._get_cache_key("handle_name", handle_name)
                cached_id = await redis_client.get(cache_key)
                if cached_id:
                    handle_id = cached_id
        except Exception as e:
            logger.warning(f"从Redis读取handle名称映射缓存失败: {e}")
        
        if not handle_id:
            handle = await ActionNodesHandleConfigModel.find_one({"handle_name": handle_name})
            if handle:
                handle_id = handle.id
                try:
                    redis_client = get_redis()
                    if redis_client:
                        cache_key = ActionInstanceService._get_cache_key("handle_name", handle_name)
                        await redis_client.setex(
                            cache_key,
                            settings.ACTION_CACHE_TTL,
                            handle_id
                        )
                except Exception as e:
                    logger.warning(f"写入Redis handle名称映射缓存失败: {e}")
                return handle
            return None
        
        return await ActionInstanceService.get_handle_definition(handle_id)

    @staticmethod
    async def resolve_node_handle_definition(
        node_definition: ActionNodeModel | None,
        handle_id: str,
    ):
        """解析节点端口及其共享或内联Handle配置。"""
        handle = next(
            (
                item
                for item in (node_definition.handles if node_definition else [])
                if handle_id in {item.id, item.port_id}
            ),
            None,
        )
        config_id = handle.handle_config_id or handle.id if handle else handle_id
        handle_definition = await ActionInstanceService.get_handle_definition(
            config_id
        )
        if handle_definition is not None or handle is None:
            return handle, handle_definition
        return handle, SimpleNamespace(
            id=config_id,
            handle_name=(
                handle.handle_name
                or handle.relabel
                or handle.port_id
                or handle.id
            ),
            type=ActionConfigIOTypeEnum(handle.data_type or "value"),
            label=handle.label or handle.relabel or handle.id,
            color=handle.color or "",
            other_compatible_interfaces=handle.compatible_interface_type_ids,
        )
    
    @staticmethod
    async def init(
        blueprint_id: str,
        inject_params: dict[str, Any] | None = None,
        *,
        blueprint_revision_id: str | None = None,
        invocation_mode: ActionInvocationModeEnum = ActionInvocationModeEnum.STANDALONE,
        visibility: ActionVisibilityEnum = ActionVisibilityEnum.NORMAL,
        root_action_id: str | None = None,
        parent_action_id: str | None = None,
        parent_node_instance_id: str | None = None,
        parent_node_execution_id: str | None = None,
        nesting_depth: int = 0,
        invocation_inputs: dict[str, Any] | None = None,
        invocation_reference_inputs: (
            dict[str, list[ReferenceStreamDescriptor]] | None
        ) = None,
        invocation_reference_outputs: (
            dict[str, list[ReferenceStreamDescriptor]] | None
        ) = None,
        initiator_user_id: str | None = None,
        trigger_type=None,
        trigger_key: str | None = None,
        scheduled_for: datetime | None = None,
        schedule_id: str | None = None,
        schedule_name: str | None = None,
        schedule_priority: int = 5,
    ) -> tuple[bool, str]:
        """
        初始化行动实例
        
        return: tuple[bool, str] - 返回初始化是否成功和行动实例ID
        """
        if trigger_key:
            existing = await ActionInstanceModel.find_one({"trigger_key": trigger_key})
            if existing:
                return True, existing.id
        action_id = generate_id(blueprint_id + datetime.now().strftime("%Y%m%d%H%M%S") + str(random.randint(1000, 9999)))
        
        blueprint = await ActionInstanceService.get_blueprint(blueprint_id)
        if not blueprint:
            logger.error(f"行动实例初始化失败，蓝图不存在: {blueprint_id}")
            return False, f"行动实例初始化失败，蓝图不存在: {blueprint_id}"

        revision = None
        graph = blueprint.graph
        if blueprint_revision_id:
            revision = await ActionBlueprintRevisionModel.find_one(
                {
                    "_id": blueprint_revision_id,
                    "blueprint_id": blueprint_id,
                    "is_active": True,
                }
            )
            if revision is None:
                return False, f"蓝图Revision不存在: {blueprint_revision_id}"
            graph = revision.graph_snapshot
        try:
            definitions = (
                await BlueprintRevisionService.load_revision_definitions(revision)
                if revision is not None
                else await BlueprintCompiler.load_definitions(graph)
            )
            if revision is None:
                await BlueprintCompiler.hydrate_interface_handle_selections(
                    graph,
                    definitions,
                )
            execution_plan = BlueprintCompiler.compile(
                graph,
                definitions,
                invocation_mode,
                revision_id=blueprint_revision_id,
            )
            await BlueprintCompiler.validate_encapsulated_dependencies(
                definitions
            )
        except ValueError as exc:
            logger.error(f"行动实例初始化失败，蓝图编译错误: {exc}")
            return False, f"蓝图编译失败: {exc}"
        
        param_required_map: dict[str, bool] = {}
        template_bindings: dict[str, dict[str, str]] = {}
        
        template_snapshot = (
            revision.template_snapshot
            if revision is not None
            else blueprint.template
        )
        is_template = bool(template_snapshot)
        if is_template:
            if not template_snapshot:
                logger.error(f"模板蓝图缺少模板配置: {blueprint_id}")
                return False, f"模板蓝图缺少模板配置: {blueprint_id}"
            
            template = template_snapshot
            if "params" in template and template["params"]:
                for param in template["params"]:
                    param_name = param.get("name")
                    if param_name:
                        param_required_map[param_name] = param.get("required", False)
            
            if "bindings" in template and template["bindings"]:
                template_bindings = template["bindings"]
        
        blueprint_snapshot = (
            revision.blueprint_snapshot.model_copy(deep=True)
            if revision is not None
            else create_blueprint_snapshot(blueprint)
        )
        action_instance = ActionInstanceModel(
            id=action_id,
            blueprint_id=blueprint_id,
            blueprint_snapshot=blueprint_snapshot,
            blueprint_revision_id=blueprint_revision_id,
            execution_plan_snapshot=execution_plan,
            invocation_mode=invocation_mode,
            visibility=visibility,
            root_action_id=root_action_id or action_id,
            parent_action_id=parent_action_id,
            parent_node_instance_id=parent_node_instance_id,
            parent_node_execution_id=parent_node_execution_id,
            nesting_depth=nesting_depth,
            invocation_inputs=invocation_inputs or {},
            invocation_reference_inputs=invocation_reference_inputs or {},
            invocation_reference_outputs=invocation_reference_outputs or {},
            initiator_user_id=initiator_user_id,
            status=ActionFlowStatusEnum.READY,
            implementation_period=blueprint_snapshot.implementation_period,
            nodes_id=[node.id for node in graph.nodes],
            trigger_type=trigger_type or "manual",
            trigger_key=trigger_key,
            scheduled_for=scheduled_for,
            schedule_id=schedule_id,
            schedule_name=schedule_name,
            schedule_priority=schedule_priority,
        )
        try:
            await action_instance.insert()
        except DuplicateKeyError:
            if not trigger_key:
                raise
            existing = await ActionInstanceModel.find_one({"trigger_key": trigger_key})
            if existing:
                return True, existing.id
            raise
        await publish_action_status_observation(
            action_instance,
            ActionFlowStatusEnum.READY,
            getattr(action_instance, "updated_at", datetime.now()),
        )
        
        plan_node_by_id = {node.id: node for node in execution_plan.nodes}
        reference_bindings_by_source = (
            ActionInstanceService._build_reference_queue_bindings(
                action_id,
                execution_plan,
                graph,
                definitions,
            )
        )
        skipped_by_id = {
            node.node_id: node.reason for node in execution_plan.skipped_nodes
        }
        for node in graph.nodes:
            node_definition = definitions[node.data.definition_id]
            default_configs = node_definition.default_configs or []
            
            form_data = node.data.form_data or []
            form_data_dict = unpack_dict(form_data) or {}
            fields_to_remove = set()
            
            if is_template and node.id in template_bindings:
                node_bindings = template_bindings[node.id]
                
                for field_name, param_name in node_bindings.items():
                    if field_name not in form_data_dict:
                        continue
                    
                    if inject_params and param_name in inject_params:
                        form_data_dict[field_name] = inject_params[param_name]
                    elif param_name in param_required_map:
                        if param_required_map[param_name]:
                            logger.error(f"行动实例初始化失败，缺少必需参数: {param_name}")
                            return False, f"行动实例初始化失败，缺少必需参数: {param_name}"
                        else:
                            fields_to_remove.add(field_name)
                    else:
                        fields_to_remove.add(field_name)
                
                for field_name in fields_to_remove:
                    form_data_dict.pop(field_name, None)
                
                form_data = pack_dict(form_data_dict) or []
                
            action_instance_node = ActionInstanceNodeModel(
                id=generate_id(action_id + node.id),
                action_id=action_id,
                node_id=node.id,
                status=(
                    ActionInstanceNodeStatusEnum.SKIPPED
                    if node.id in skipped_by_id
                    else ActionInstanceNodeStatusEnum.PENDING
                ),
                configs=form_data + default_configs,
                reference_queue_bindings=reference_bindings_by_source.get(
                    node.id,
                    {},
                ),
                definition_id=node.data.definition_id,
                definition_snapshot=node_definition.model_dump(
                    mode="python",
                    by_alias=True,
                ),
                execution_spec_snapshot=(
                    plan_node_by_id[node.id].execution
                    if node.id in plan_node_by_id
                    else node_definition.execution
                ),
                extension_spec_snapshot=(
                    plan_node_by_id[node.id].extension_spec
                    if node.id in plan_node_by_id
                    else node_definition.extension
                ),
                node_definition_version=node_definition.definition_version,
                extension_contract_version=(
                    node_definition.extension.contract_version
                    if node_definition.extension
                    else None
                ),
                skip_reason=skipped_by_id.get(node.id),
                effective_in_degree=(
                    plan_node_by_id[node.id].effective_in_degree
                    if node.id in plan_node_by_id
                    else 0
                ),
                effective_out_degree=(
                    plan_node_by_id[node.id].effective_out_degree
                    if node.id in plan_node_by_id
                    else 0
                ),
                instance_config=(
                    plan_node_by_id[node.id].instance_config
                    if node.id in plan_node_by_id
                    else {
                        **form_data_dict,
                        **node.data.instance_config,
                    }
                ),
                finished_at=datetime.now() if node.id in skipped_by_id else None,
                finalization_claimed=node.id in skipped_by_id,
            )
            await action_instance_node.insert()
        
        start_node_ids = [
            node.id for node in execution_plan.nodes if node.effective_in_degree == 0
        ]
        if not start_node_ids:
            logger.warning(f"没有找到起始节点: {action_id}")
        
        for node_id in start_node_ids:
            await ActionInstanceService.set_node_status(
                node_id,
                action_id,
                ActionInstanceNodeStatusEnum.READY,
            )
        
        return True, action_id

    @staticmethod
    async def start(action_id: str):
        """
        开始某个行动
        """
        action = await ActionInstanceModel.find_one(
            {"_id": action_id, "status": ActionFlowStatusEnum.READY}
        )
        if action is None:
            logger.info(f"行动已启动或不存在，跳过重复启动: {action_id}")
            return
        now = datetime.now()
        claim = await ActionInstanceModel.find_one(
            {"_id": action_id, "status": ActionFlowStatusEnum.READY}
        ).update(
            {
                "$set": {
                    "status": ActionFlowStatusEnum.RUNNING,
                    "start_at": now,
                    "deadline_at": (
                        now + timedelta(seconds=action.implementation_period)
                        if action.implementation_period > 0
                        else None
                    ),
                    "updated_at": now,
                }
            }
        )
        if not claim or getattr(claim, "modified_count", 0) != 1:
            logger.info(f"行动已启动或不存在，跳过重复启动: {action_id}")
            return
        action = await ActionInstanceModel.find_one({"_id": action_id})
        if action is None:
            return
        await publish_action_status_observation(
            action,
            ActionFlowStatusEnum.RUNNING,
            now,
        )

        ready_nodes = await ActionInstanceNodeModel.find({"action_id": action.id, "status": ActionInstanceNodeStatusEnum.READY}).to_list()
        for node in ready_nodes:
            await ActionInstanceService.run_node(node.id, action_id)
        if not ready_nodes and await ActionInstanceService.check_action_finished(action_id):
            await ActionInstanceService.finish_action(action_id)

    @staticmethod
    async def pause(action_id: str) -> tuple[bool, str]:
        """暂停运行中的行动，并保留其引用队列和当前组件运行。"""
        action = await ActionInstanceModel.find_one({"_id": action_id})
        if action is None:
            return False, f"行动不存在，ID: {action_id}"
        if action.status == ActionFlowStatusEnum.PAUSED:
            return True, "行动已处于暂停状态"
        if action.status != ActionFlowStatusEnum.RUNNING:
            return False, f"当前状态不允许暂停: {action.status.value}"

        now = datetime.now()
        claim = await ActionInstanceModel.find_one(
            {"_id": action_id, "status": ActionFlowStatusEnum.RUNNING}
        ).update(
            {
                "$set": {
                    "status": ActionFlowStatusEnum.PAUSED,
                    "paused_at": now,
                    "updated_at": now,
                }
            }
        )
        if not claim or getattr(claim, "modified_count", 0) != 1:
            return False, "行动状态已变化，暂停失败"
        await publish_action_status_observation(
            action,
            ActionFlowStatusEnum.PAUSED,
            now,
        )

        await ActionInstanceNodeModel.find(
            {
                "action_id": action_id,
                "status": {
                    "$in": [
                        ActionInstanceNodeStatusEnum.PENDING,
                        ActionInstanceNodeStatusEnum.UNREADY,
                        ActionInstanceNodeStatusEnum.READY,
                        ActionInstanceNodeStatusEnum.QUEUED,
                        ActionInstanceNodeStatusEnum.UNKNOWN,
                    ]
                },
            }
        ).update({"$set": {"status": ActionInstanceNodeStatusEnum.PAUSED}})
        return True, "行动已暂停，引用队列将持续保留"

    @staticmethod
    async def resume(action_id: str) -> tuple[bool, str]:
        """恢复暂停行动，重新派发未启动组件并继续执行就绪节点。"""
        action = await ActionInstanceModel.find_one({"_id": action_id})
        if action is None:
            return False, f"行动不存在，ID: {action_id}"
        if action.status == ActionFlowStatusEnum.STOPPED:
            return False, "已停止的行动无法恢复"
        if action.status != ActionFlowStatusEnum.PAUSED:
            return False, f"当前状态不允许恢复: {action.status.value}"

        now = datetime.now()
        paused_seconds = (
            max((now - action.paused_at).total_seconds(), 0)
            if action.paused_at
            else 0
        )
        update_fields = {
            "status": ActionFlowStatusEnum.RUNNING,
            "paused_at": None,
            "paused_duration": getattr(action, "paused_duration", 0) + paused_seconds,
            "updated_at": now,
        }
        if action.deadline_at is not None:
            update_fields["deadline_at"] = action.deadline_at + timedelta(
                seconds=paused_seconds
            )
        claim = await ActionInstanceModel.find_one(
            {"_id": action_id, "status": ActionFlowStatusEnum.PAUSED}
        ).update({"$set": update_fields})
        if not claim or getattr(claim, "modified_count", 0) != 1:
            return False, "行动状态已变化，恢复失败"

        action = await ActionInstanceModel.find_one({"_id": action_id})
        if action is None:
            return False, "行动在恢复过程中被删除"
        blueprint = await ActionInstanceService.get_action_blueprint(action)
        if blueprint is None:
            await ActionInstanceModel.find_one(
                {"_id": action_id, "status": ActionFlowStatusEnum.RUNNING}
            ).update(
                {
                    "$set": {
                        "status": ActionFlowStatusEnum.PAUSED,
                        "paused_at": now,
                        "updated_at": now,
                    }
                }
            )
            return False, "行动蓝图不存在，无法恢复"

        node_instances = await ActionInstanceNodeModel.find(
            {"action_id": action_id}
        ).to_list()
        node_by_id = {node.node_id: node for node in node_instances}
        previous_by_node: dict[str, list[str]] = {}
        execution_edges = action.execution_plan_snapshot.edges
        for edge in execution_edges:
            previous_by_node.setdefault(edge.target, []).append(edge.source)

        for node_instance in node_instances:
            if node_instance.status != ActionInstanceNodeStatusEnum.PAUSED:
                continue
            previous_nodes = [
                node_by_id[node_id]
                for node_id in previous_by_node.get(node_instance.node_id, [])
                if node_id in node_by_id
            ]
            failed_previous = next(
                (
                    node
                    for node in previous_nodes
                    if node.status
                    in {
                        ActionInstanceNodeStatusEnum.FAILED,
                        ActionInstanceNodeStatusEnum.CANCELLED,
                        ActionInstanceNodeStatusEnum.TIMEOUT,
                    }
                ),
                None,
            )
            if failed_previous is not None:
                node_status = ActionInstanceNodeStatusEnum.CANCELLED
                node_update = {
                    "status": node_status,
                    "error_message": "前置节点未成功完成，节点不再运行",
                    "finished_at": now,
                    "finalization_claimed": True,
                }
            else:
                node_status = (
                    ActionInstanceNodeStatusEnum.READY
                    if all(
                        node.status == ActionInstanceNodeStatusEnum.COMPLETED
                        for node in previous_nodes
                    )
                    else ActionInstanceNodeStatusEnum.UNREADY
                )
                node_update = {
                    "status": node_status,
                    "start_at": None,
                }
            await ActionInstanceNodeModel.find_one(
                {
                    "_id": node_instance.id,
                    "status": ActionInstanceNodeStatusEnum.PAUSED,
                }
            ).update({"$set": node_update})

        action = await ActionInstanceModel.find_one(
            {"_id": action_id, "status": ActionFlowStatusEnum.RUNNING}
        )
        if action is None:
            return False, "行动恢复过程中状态已变化"

        running_nodes = await ActionInstanceNodeModel.find(
            {
                "action_id": action_id,
                "status": ActionInstanceNodeStatusEnum.RUNNING,
            }
        ).to_list()
        for node_instance in running_nodes:
            component_runs = await ComponentRunModel.find(
                {
                    "node_instance_id": node_instance.id,
                    "status": ComponentRunStatusEnum.CREATED,
                    "cancel_requested": False,
                }
            ).to_list()
            if not component_runs:
                continue
            try:
                await node_executors.require(
                    ActionExecutionDriverEnum.COMPONENT.value
                ).start(
                    NodeExecutionContext(
                        action_id=action.id,
                        node_instance_id=node_instance.id,
                        node_id=node_instance.node_id,
                        invocation_mode=action.invocation_mode,
                        instance_config=node_instance.instance_config,
                        initiator_user_id=action.initiator_user_id,
                    ),
                    node_instance.execution_spec_snapshot,
                )
            except Exception as exc:
                logger.error(
                    f"恢复普通节点组件派发失败，节点 {node_instance.id}: {exc}"
                )

        ready_nodes = await ActionInstanceNodeModel.find(
            {
                "action_id": action_id,
                "status": ActionInstanceNodeStatusEnum.READY,
            }
        ).to_list()
        for node_instance in ready_nodes:
            await ActionInstanceService.run_node(node_instance.id, action_id)

        current_action = await ActionInstanceModel.find_one({"_id": action_id})
        if (
            current_action is not None
            and current_action.status == ActionFlowStatusEnum.RUNNING
        ):
            await publish_action_status_observation(
                current_action,
                ActionFlowStatusEnum.RUNNING,
                now,
            )
        if (
            current_action is not None
            and current_action.status == ActionFlowStatusEnum.RUNNING
            and await ActionInstanceService.check_action_finished(action_id)
        ):
            await ActionInstanceService.finish_action(action_id)
        return True, "行动已恢复运行"

    @staticmethod
    async def stop(action_id: str) -> tuple[bool, str]:
        """不可逆地停止行动、终止活动组件并立即清理引用队列。"""
        action = await ActionInstanceModel.find_one({"_id": action_id})
        if action is None:
            return False, f"行动不存在，ID: {action_id}"
        if action.status == ActionFlowStatusEnum.STOPPED:
            await ActionInstanceService.cancel_reference_bridges(
                action_id,
                "行动已停止",
            )
            queues_cleaned = await ActionInstanceService.cleanup_action_queues(
                action_id
            )
            if not queues_cleaned:
                return True, "行动已停止，但部分引用队列清理仍然失败"
            return True, "行动已处于停止状态，引用队列已清理"

        stoppable_statuses = {
            ActionFlowStatusEnum.UNKNOWN,
            ActionFlowStatusEnum.UNREADY,
            ActionFlowStatusEnum.READY,
            ActionFlowStatusEnum.RUNNING,
            ActionFlowStatusEnum.PAUSED,
        }
        if action.status not in stoppable_statuses:
            return False, f"当前状态不允许停止: {action.status.value}"

        now = datetime.now()
        current_pause_seconds = (
            max((now - action.paused_at).total_seconds(), 0)
            if action.status == ActionFlowStatusEnum.PAUSED and action.paused_at
            else 0
        )
        paused_duration = getattr(action, "paused_duration", 0) + current_pause_seconds
        duration = (
            max((now - action.start_at).total_seconds() - paused_duration, 0)
            if action.start_at
            else 0
        )
        claim = await ActionInstanceModel.find_one(
            {"_id": action_id, "status": {"$in": list(stoppable_statuses)}}
        ).update(
            {
                "$set": {
                    "status": ActionFlowStatusEnum.STOPPED,
                    "paused_at": None,
                    "paused_duration": paused_duration,
                    "finished_at": now,
                    "duration": duration,
                    "updated_at": now,
                }
            }
        )
        if not claim or getattr(claim, "modified_count", 0) != 1:
            return False, "行动状态已变化，停止失败"
        await RuntimeDomainEventService.publish_action_terminal(
            action,
            ActionFlowStatusEnum.STOPPED.value,
        )
        await publish_action_status_observation(
            action,
            ActionFlowStatusEnum.STOPPED,
            now,
        )

        active_runs = await ComponentRunModel.find(
            {
                "action_id": action_id,
                "status": {
                    "$in": [
                        ComponentRunStatusEnum.DISPATCHED,
                        ComponentRunStatusEnum.RUNNING,
                    ]
                },
            }
        ).to_list()
        await ComponentRunModel.find(
            {
                "action_id": action_id,
                "status": {
                    "$in": [
                        ComponentRunStatusEnum.CREATED,
                        ComponentRunStatusEnum.DISPATCHED,
                        ComponentRunStatusEnum.RUNNING,
                    ]
                },
            }
        ).update(
            {
                "$set": {
                    "status": ComponentRunStatusEnum.CANCELLED,
                    "cancel_requested": True,
                    "error_message": "行动已停止",
                    "finished_at": now,
                    "updated_at": now,
                }
            }
        )
        await ActionInstanceNodeModel.find(
            {
                "action_id": action_id,
                "status": {
                    "$in": [
                        ActionInstanceNodeStatusEnum.PENDING,
                        ActionInstanceNodeStatusEnum.UNREADY,
                        ActionInstanceNodeStatusEnum.READY,
                        ActionInstanceNodeStatusEnum.QUEUED,
                        ActionInstanceNodeStatusEnum.RUNNING,
                        ActionInstanceNodeStatusEnum.WAITING,
                        ActionInstanceNodeStatusEnum.AWAITING_APPROVAL,
                        ActionInstanceNodeStatusEnum.UNKNOWN,
                        ActionInstanceNodeStatusEnum.PAUSED,
                    ]
                },
            }
        ).update(
            {
                "$set": {
                    "status": ActionInstanceNodeStatusEnum.CANCELLED,
                    "error_message": "行动已停止",
                    "finished_at": now,
                    "finalization_claimed": True,
                }
            }
        )
        if active_runs:
            await asyncio.gather(
                *(cancel_component_run(run) for run in active_runs),
                return_exceptions=True,
            )
        await ActionInstanceService.cancel_node_executions(
            action_id,
            "行动已停止",
        )
        await ActionInstanceService.cancel_reference_bridges(
            action_id,
            "行动已停止",
        )
        queues_cleaned = await ActionInstanceService.cleanup_action_queues(action_id)
        if not queues_cleaned:
            return True, "行动已停止，但部分引用队列清理失败"
        return True, "行动已停止，引用队列已清理"

    @staticmethod
    async def run_node(node_instance_id: str, action_id: str):
        """
        运行指定行动的指定节点
        """
        logger.info(f"运行节点: {node_instance_id}")
        node_instance = await ActionInstanceNodeModel.find_one({"_id": node_instance_id})
        if not node_instance:
            logger.error(f"未找到节点，Action ID: {action_id}，Node Instance ID: {node_instance_id}")
            return False
        
        node_definition = await (
            ActionInstanceService.get_instance_node_definition(node_instance)
        )
        if not node_definition:
            logger.error(f"未找到节点定义，Node Instance ID: {node_instance_id}")
            return False

        action = await ActionInstanceModel.find_one({"_id": action_id})
        if action is None:
            logger.error(f"未找到行动，Action ID: {action_id}")
            return False
        if action.status != ActionFlowStatusEnum.RUNNING:
            target_status = (
                ActionInstanceNodeStatusEnum.PAUSED
                if action.status == ActionFlowStatusEnum.PAUSED
                else ActionInstanceNodeStatusEnum.CANCELLED
            )
            await ActionInstanceNodeModel.find_one(
                {
                    "_id": node_instance_id,
                    "status": {
                        "$in": [
                            ActionInstanceNodeStatusEnum.PENDING,
                            ActionInstanceNodeStatusEnum.UNKNOWN,
                            ActionInstanceNodeStatusEnum.UNREADY,
                            ActionInstanceNodeStatusEnum.READY,
                        ]
                    },
                }
            ).update({"$set": {"status": target_status}})
            return False
        
        # 检查前置节点是否全部完成
        all_previous_nodes = await ActionInstanceService.find_all_previous_nodes(action_id, node_instance.node_id)
        previous_node_instances = await ActionInstanceNodeModel.find({
            "action_id": action_id,
            "node_id": {"$in": all_previous_nodes}
        }).to_list()
        completed_dependencies = sum(
            previous.status == ActionInstanceNodeStatusEnum.COMPLETED
            and previous.node_id
            in getattr(node_instance, "delivered_dependencies", [])
            for previous in previous_node_instances
        )
        plan_node = next(
            (
                item
                for item in action.execution_plan_snapshot.nodes
                if item.id == node_instance.node_id
            ),
            None,
        )
        if plan_node is None:
            logger.error(
                f"执行计划中不存在节点，Node Instance ID: {node_instance_id}"
            )
            return False
        policy_key = (
            plan_node.extension_spec.execution_policy
            if plan_node.extension_spec
            else "default"
        )
        policy_version = (
            plan_node.extension_spec.contract_version
            if plan_node.extension_spec
            else 1
        )
        policy = execution_policies.require(policy_key, policy_version)
        is_ready = policy.is_ready(plan_node, completed_dependencies)
        if not is_ready:
            logger.info(
                f"前置依赖尚未满足执行策略，等待中，当前节点: {node_instance.id}"
            )
            await ActionInstanceNodeModel.find_one(
                {
                    "_id": node_instance.id,
                    "status": {
                        "$in": [
                            ActionInstanceNodeStatusEnum.PENDING,
                            ActionInstanceNodeStatusEnum.UNKNOWN,
                            ActionInstanceNodeStatusEnum.READY,
                            ActionInstanceNodeStatusEnum.UNREADY,
                        ]
                    },
                }
            ).update({"$set": {"status": ActionInstanceNodeStatusEnum.UNREADY}})
            return False
        
        # 原子声明节点派发权，避免多个并行前置节点同时完成时重复派发。
        claim = await ActionInstanceNodeModel.find_one(
            {
                "_id": node_instance_id,
                "status": {
                    "$in": [
                        ActionInstanceNodeStatusEnum.PENDING,
                        ActionInstanceNodeStatusEnum.UNKNOWN,
                        ActionInstanceNodeStatusEnum.UNREADY,
                        ActionInstanceNodeStatusEnum.READY,
                    ]
                },
            }
        ).update(
            {
                "$set": {
                    "status": ActionInstanceNodeStatusEnum.QUEUED,
                    "start_at": datetime.now(),
                }
            }
        )
        if not claim or getattr(claim, "modified_count", 0) != 1:
            logger.info(f"节点已被其他任务派发，跳过重复启动: {node_instance_id}")
            return False
        node_instance = await ActionInstanceNodeModel.find_one({"_id": node_instance_id})
            
        action = await ActionInstanceModel.find_one({"_id": action_id})
        if not action:
            logger.error(f"未找到行动，Action ID: {action_id}")
            return False
        if action.status != ActionFlowStatusEnum.RUNNING:
            target_status = (
                ActionInstanceNodeStatusEnum.PAUSED
                if action.status == ActionFlowStatusEnum.PAUSED
                else ActionInstanceNodeStatusEnum.CANCELLED
            )
            node_update = {"status": target_status}
            if target_status == ActionInstanceNodeStatusEnum.PAUSED:
                node_update["start_at"] = None
            else:
                node_update["finished_at"] = datetime.now()
            await ActionInstanceNodeModel.find_one(
                {
                    "_id": node_instance.id,
                    "status": ActionInstanceNodeStatusEnum.QUEUED,
                }
            ).update({"$set": node_update})
            return False
        blueprint = await ActionInstanceService.get_action_blueprint(action)
        if not blueprint:
            logger.error(f"未找到蓝图，Blueprint ID: {action.blueprint_id}")
            return False
        
        execution_spec = node_instance.execution_spec_snapshot
        node_kind = getattr(
            node_definition,
            "node_kind",
            ActionNodeKindEnum.ORDINARY,
        )
        extension_spec = (
            node_instance.extension_spec_snapshot
        )
        try:
            NodeDefinitionContract(
                node_kind=node_kind,
                execution=execution_spec,
                extension=extension_spec,
            )
        except ValueError as exc:
            node_instance.status = ActionInstanceNodeStatusEnum.FAILED
            node_instance.error_message = str(exc)
            node_instance.finished_at = datetime.now()
            node_instance.duration = (datetime.now() - node_instance.start_at).total_seconds()
            await node_instance.save()
            await ActionInstanceService.cancel_following_nodes(action.id, node_instance.node_id)
            if await ActionInstanceService.check_action_finished(action.id):
                await ActionInstanceService.finish_action(action.id)
            return False

        # 这里是开始运行，在此之前应该做好全部准备工作
        related_components = (
            execution_spec.config.get("component", {}).get("component_ids")
            or getattr(node_definition, "related_components", [])
        )
        if (
            execution_spec.driver == ActionExecutionDriverEnum.COMPONENT
            and not related_components
        ):
            node_instance.status = ActionInstanceNodeStatusEnum.FAILED
            node_instance.error_message = "普通节点未关联基础组件"
            node_instance.finished_at = datetime.now()
            node_instance.duration = (datetime.now() - node_instance.start_at).total_seconds()
            await node_instance.save()
            await ActionInstanceService.cancel_following_nodes(action.id, node_instance.node_id)
            if await ActionInstanceService.check_action_finished(action.id):
                await ActionInstanceService.finish_action(action.id)
            return False

        running_claim = await ActionInstanceNodeModel.find_one(
            {
                "_id": node_instance.id,
                "status": ActionInstanceNodeStatusEnum.QUEUED,
                "finalization_claimed": False,
            }
        ).update({"$set": {"status": ActionInstanceNodeStatusEnum.RUNNING}})
        if not running_claim or getattr(running_claim, "modified_count", 0) != 1:
            return False

        execution_keys = policy.execution_keys(plan_node) if plan_node else ["default"]
        if not execution_keys or len(execution_keys) != len(set(execution_keys)):
            return await ActionInstanceService.finish_node(
                node_instance.id,
                SDKResultRequest(
                    result_id=generate_id(f"invalid-policy:{node_instance.id}"),
                    attempt=1,
                    status="failed",
                    error="Execution Policy 必须返回非空且唯一的 execution_key",
                ),
            )

        input_values: dict[str, Any] = {}
        input_groups: dict[str, list[Any]] = {}
        for handle_id, item in getattr(node_instance, "inputs", {}).items():
            input_values[handle_id] = item.value
            input_values[item.key] = item.value
            input_groups.setdefault(item.key, []).append(item.value)
        executor = node_executors.require(execution_spec.driver.value)
        for execution_key in execution_keys:
            execution = await ActionInstanceService._ensure_node_execution(
                action,
                node_instance,
                execution_spec,
                execution_key=execution_key,
            )
            if execution.status in {
                ActionInstanceNodeStatusEnum.RUNNING,
                ActionInstanceNodeStatusEnum.WAITING,
                ActionInstanceNodeStatusEnum.AWAITING_APPROVAL,
                ActionInstanceNodeStatusEnum.COMPLETED,
            } and execution.provider_run_id:
                continue
            context = NodeExecutionContext(
                action_id=action.id,
                node_instance_id=node_instance.id,
                node_id=node_instance.node_id,
                execution_key=execution_key,
                invocation_mode=action.invocation_mode,
                inputs=input_values,
                input_groups=input_groups,
                invocation_inputs=action.invocation_inputs,
                instance_config=node_instance.instance_config,
                initiator_user_id=action.initiator_user_id,
            )
            try:
                result = await executor.start(context, execution_spec)
            except Exception as exc:
                if execution_spec.driver == ActionExecutionDriverEnum.SUBFLOW:
                    children = await ActionInstanceModel.find(
                        {
                            "parent_node_execution_id": execution.id,
                            "status": {
                                "$in": [
                                    ActionFlowStatusEnum.UNKNOWN,
                                    ActionFlowStatusEnum.UNREADY,
                                    ActionFlowStatusEnum.READY,
                                    ActionFlowStatusEnum.RUNNING,
                                    ActionFlowStatusEnum.PAUSED,
                                ]
                            },
                        }
                    ).to_list()
                    await asyncio.gather(
                        *(
                            ActionInstanceService.stop(child.id)
                            for child in children
                        ),
                        return_exceptions=True,
                    )
                await execution.update(
                    {
                        "$set": {
                            "status": ActionInstanceNodeStatusEnum.FAILED,
                            "error_message": str(exc),
                            "finished_at": datetime.now(),
                            "updated_at": datetime.now(),
                        }
                    }
                )
                current_node = await ActionInstanceNodeModel.find_one(
                    {"_id": node_instance.id}
                )
                if (
                    current_node is not None
                    and current_node.status
                    in {
                        ActionInstanceNodeStatusEnum.FAILED,
                        ActionInstanceNodeStatusEnum.CANCELLED,
                        ActionInstanceNodeStatusEnum.TIMEOUT,
                    }
                ):
                    return False
                return await ActionInstanceService._finalize_execution_group(
                    node_instance.id
                )

            update_fields = {
                "provider_run_id": result.provider_run_id,
                "progress": result.progress,
                "outputs": result.outputs,
                "extension_state": result.extension_state,
                "extension_result": result.extension_result,
                "status": (
                    ActionInstanceNodeStatusEnum.COMPLETED
                    if result.state == "completed"
                    else ActionInstanceNodeStatusEnum.RUNNING
                ),
                "finished_at": (
                    datetime.now() if result.state == "completed" else None
                ),
                "updated_at": datetime.now(),
            }
            if execution_spec.driver == ActionExecutionDriverEnum.SUBFLOW:
                update_fields["child_action_id"] = result.provider_run_id
            await execution.update({"$set": update_fields})
            execution.provider_run_id = result.provider_run_id
            await ActionLogService.ingest_node_event(
                execution,
                event_key="started",
                level="INFO",
                source=(
                    "subflow"
                    if execution_spec.driver == ActionExecutionDriverEnum.SUBFLOW
                    else "native"
                    if execution_spec.driver
                    == ActionExecutionDriverEnum.BACKEND_NATIVE
                    else "orchestrator"
                ),
                message=(
                    "节点已立即完成"
                    if result.state == "completed"
                    else "节点执行已启动"
                ),
                fields={"execution_key": execution_key},
                root_action_id=action.root_action_id,
                parent_action_id=action.parent_action_id,
            )

        return await ActionInstanceService._finalize_execution_group(
            node_instance.id
        )

    @staticmethod
    async def _ensure_node_execution(
        action: ActionInstanceModel,
        node_instance: ActionInstanceNodeModel,
        execution_spec: NodeExecutionSpec,
        *,
        execution_key: str = "default",
    ) -> ActionNodeExecutionModel:
        """幂等创建实际节点尝试的通用执行记录。"""
        attempt = 1
        idempotency_key = (
            f"{action.id}:{node_instance.id}:{execution_key}:{attempt}"
        )
        execution = await ActionNodeExecutionModel.find_one(
            {"idempotency_key": idempotency_key}
        )
        if execution is None:
            timeout_seconds = int(
                node_instance.instance_config.get(
                    "timeout_seconds",
                    execution_spec.config.get("timeout_seconds", 0),
                )
                or 0
            )
            started_at = datetime.now()
            execution = ActionNodeExecutionModel(
                id=generate_id(f"node_execution:{idempotency_key}"),
                action_id=action.id,
                node_instance_id=node_instance.id,
                execution_key=execution_key,
                driver=execution_spec.driver.value,
                handler=execution_spec.handler,
                schema_version=execution_spec.schema_version,
                extension_contract_version=getattr(
                    node_instance,
                    "extension_contract_version",
                    None,
                ),
                attempt=attempt,
                status=ActionInstanceNodeStatusEnum.RUNNING,
                idempotency_key=idempotency_key,
                timeout_seconds=timeout_seconds,
                deadline_at=(
                    started_at + timedelta(seconds=timeout_seconds)
                    if timeout_seconds > 0
                    else None
                ),
                started_at=started_at,
            )
            try:
                await execution.insert()
            except DuplicateKeyError:
                execution = await ActionNodeExecutionModel.find_one(
                    {"idempotency_key": idempotency_key}
                )
        await ActionInstanceNodeModel.find_one(
            {"_id": node_instance.id}
        ).update(
            {
                "$set": {"current_execution_id": execution.id},
                "$addToSet": {"execution_ids": execution.id},
            }
        )
        return execution

    @staticmethod
    async def _start_subflow_attempt(
        context: NodeExecutionContext,
        execution_spec: NodeExecutionSpec,
    ) -> str:
        """幂等创建并启动封装节点的嵌入式子行动。"""
        action = await ActionInstanceModel.find_one({"_id": context.action_id})
        node_instance = await ActionInstanceNodeModel.find_one(
            {"_id": context.node_instance_id}
        )
        if action is None or node_instance is None:
            raise ValueError("封装节点所属行动或节点实例不存在")
        revision_id = str(execution_spec.config.get("revision_id") or "")
        blueprint_id = str(execution_spec.config.get("blueprint_id") or "")
        if not revision_id or not blueprint_id:
            raise ValueError("封装节点缺少 blueprint_id 或 revision_id")
        if action.nesting_depth >= 8:
            raise ValueError("封装节点超过最大嵌套深度 8")

        node_definition = await (
            ActionInstanceService.get_instance_node_definition(node_instance)
        )
        if node_definition is None:
            raise ValueError("封装节点定义不存在")
        handle_by_id = {}
        for handle in node_definition.handles:
            handle_by_id[handle.id] = handle
            if handle.port_id:
                handle_by_id[handle.port_id] = handle
        invocation_inputs = {}
        invocation_reference_inputs: dict[
            str,
            list[ReferenceStreamDescriptor],
        ] = {}
        for handle_id, item in node_instance.inputs.items():
            handle = handle_by_id.get(handle_id)
            public_port_id = (
                handle.port_id if handle and handle.port_id else handle_id
            )
            if item.type != ActionConfigIOTypeEnum.REFERENCE:
                invocation_inputs[public_port_id] = item.value

        parent_plan = action.execution_plan_snapshot
        if parent_plan is not None:
            parent_nodes = await ActionInstanceNodeModel.find(
                {"action_id": action.id}
            ).to_list()
            parent_node_by_design_id = {
                item.node_id: item for item in parent_nodes
            }
            for edge in parent_plan.edges:
                if (
                    edge.target != node_instance.node_id
                    or edge.data_type != "reference"
                ):
                    continue
                source_instance = parent_node_by_design_id.get(edge.source)
                binding = (
                    source_instance.reference_queue_bindings.get(edge.id)
                    if source_instance
                    else None
                )
                if binding is None:
                    raise ValueError(
                        f"封装节点Reference输入缺少执行边队列: {edge.id}"
                    )
                invocation_reference_inputs.setdefault(
                    edge.target_port_id,
                    [],
                ).append(
                    ReferenceStreamDescriptor(
                        stream_id=binding.stream_id,
                        queue_name=binding.queue_name,
                        owner_action_id=binding.owner_action_id,
                        protocol_version=binding.protocol_version,
                        expected_producer_ids=binding.expected_producer_ids,
                        termination="eos",
                    )
                )
        revision = await ActionBlueprintRevisionModel.find_one(
            {
                "_id": revision_id,
                "blueprint_id": blueprint_id,
                "is_active": True,
            }
        )
        if revision is None:
            raise ValueError(f"蓝图Revision不存在: {revision_id}")
        for public_input in revision.interface_snapshot.inputs:
            if (
                public_input.data_type == ActionConfigIOTypeEnum.REFERENCE.value
                and public_input.required
                and not invocation_reference_inputs.get(public_input.id)
            ):
                raise ValueError(
                    f"封装节点缺少必填Reference输入: {public_input.id}"
                )
        execution = await ActionNodeExecutionModel.find_one(
            {
                "action_id": action.id,
                "node_instance_id": node_instance.id,
                "execution_key": context.execution_key,
                "attempt": 1,
            }
        )
        if execution is None:
            raise ValueError("封装节点通用执行记录不存在")
        success, child_action_id = await ActionInstanceService.init(
            blueprint_id,
            {
                key: value
                for key, value in node_instance.instance_config.items()
                if not key.startswith("_")
            },
            blueprint_revision_id=revision_id,
            invocation_mode=ActionInvocationModeEnum.SUBFLOW,
            visibility=ActionVisibilityEnum.EMBEDDED,
            root_action_id=action.root_action_id or action.id,
            parent_action_id=action.id,
            parent_node_instance_id=node_instance.id,
            parent_node_execution_id=execution.id,
            nesting_depth=action.nesting_depth + 1,
            invocation_inputs=invocation_inputs,
            invocation_reference_inputs=invocation_reference_inputs,
            initiator_user_id=action.initiator_user_id,
            trigger_key=f"subflow:{execution.id}",
            trigger_type="api",
        )
        if not success:
            raise ValueError(child_action_id)

        child = await ActionInstanceModel.find_one({"_id": child_action_id})
        if child is None:
            raise ValueError("封装节点子行动初始化结果不存在")
        child_nodes = await ActionInstanceNodeModel.find(
            {"action_id": child_action_id}
        ).to_list()
        child_node_by_design_id = {item.node_id: item for item in child_nodes}
        boundary_by_node_id = {}
        for plan_node in child.execution_plan_snapshot.nodes:
            boundary = (plan_node.extension or {}).get("boundary", {})
            direction = boundary.get("direction")
            public_port_id = boundary.get("interface_port_id")
            if direction and public_port_id:
                boundary_by_node_id[plan_node.id] = (
                    direction,
                    public_port_id,
                )

        child_input_destinations: dict[
            str,
            list[tuple[ActionInstanceNodeModel, ReferenceQueueBinding]],
        ] = {}
        child_output_sources: dict[
            str,
            list[ReferenceQueueBinding],
        ] = {}
        for edge in child.execution_plan_snapshot.edges:
            if edge.data_type != "reference":
                continue
            source_boundary = boundary_by_node_id.get(edge.source)
            if source_boundary and source_boundary[0] == "input":
                source_instance = child_node_by_design_id.get(edge.source)
                binding = (
                    source_instance.reference_queue_bindings.get(edge.id)
                    if source_instance
                    else None
                )
                if binding is None:
                    raise ValueError(
                        f"子行动Reference输入缺少执行边队列: {edge.id}"
                    )
                child_input_destinations.setdefault(
                    source_boundary[1],
                    [],
                ).append((source_instance, binding))
            target_boundary = boundary_by_node_id.get(edge.target)
            if target_boundary and target_boundary[0] == "output":
                source_instance = child_node_by_design_id.get(edge.source)
                binding = (
                    source_instance.reference_queue_bindings.get(edge.id)
                    if source_instance
                    else None
                )
                if binding is None:
                    raise ValueError(
                        f"子行动Reference输出缺少执行边队列: {edge.id}"
                    )
                child_output_sources.setdefault(
                    target_boundary[1],
                    [],
                ).append(binding)

        parent_output_destinations: dict[
            str,
            list[ReferenceQueueBinding],
        ] = {}
        for binding in node_instance.reference_queue_bindings.values():
            parent_output_destinations.setdefault(
                binding.source_port_id,
                [],
            ).append(binding)

        child.invocation_reference_outputs = {
            public_port_id: [
                ReferenceStreamDescriptor(
                    stream_id=binding.stream_id,
                    queue_name=binding.queue_name,
                    owner_action_id=binding.owner_action_id,
                    protocol_version=binding.protocol_version,
                    expected_producer_ids=binding.expected_producer_ids,
                    termination="eos",
                )
                for binding in bindings
            ]
            for public_port_id, bindings in child_output_sources.items()
        }

        created_bridges = 0
        for public_port_id, destinations_with_nodes in (
            child_input_destinations.items()
        ):
            sources = invocation_reference_inputs.get(public_port_id, [])
            if not sources:
                interface = (
                    child.execution_plan_snapshot.public_interface_snapshot
                    or {}
                )
                public_input = next(
                    (
                        item
                        for item in interface.get("inputs", [])
                        if item.get("id") == public_port_id
                    ),
                    {},
                )
                if public_input.get("required"):
                    raise ValueError(
                        f"封装节点缺少必填Reference输入: {public_port_id}"
                    )
                producer_id = f"bridge:empty:{child_action_id}:{public_port_id}"
                for destination_node, destination in destinations_with_nodes:
                    destination.expected_producer_ids = [producer_id]
                    await publish_reference_control(
                        queue_names=[destination.queue_name],
                        stream_id=destination.stream_id,
                        producer_id=producer_id,
                        action_id=child_action_id,
                        status="eos",
                    )
                    await destination_node.save()
                continue
            bridge_id = generate_id(
                f"reference-bridge:{action.id}:{child_action_id}:"
                f"{node_instance.id}:{public_port_id}:ingress"
            )
            producer_id = f"bridge:{bridge_id}"
            destination_descriptors = []
            for destination_node, destination in destinations_with_nodes:
                destination.expected_producer_ids = [producer_id]
                destination_descriptors.append(
                    ReferenceStreamDescriptor(
                        stream_id=destination.stream_id,
                        queue_name=destination.queue_name,
                        owner_action_id=destination.owner_action_id,
                        protocol_version=destination.protocol_version,
                        expected_producer_ids=[producer_id],
                        termination="eos",
                    )
                )
                await destination_node.save()
            await ReferenceBridgeService.create(
                parent_action_id=action.id,
                child_action_id=child_action_id,
                parent_node_instance_id=node_instance.id,
                public_port_id=public_port_id,
                direction=ReferenceBridgeDirectionEnum.INGRESS,
                sources=sources,
                destinations=destination_descriptors,
                bridge_id=bridge_id,
            )
            created_bridges += 1

        for public_port_id, source_bindings in child_output_sources.items():
            destinations = parent_output_destinations.get(public_port_id, [])
            if not destinations:
                continue
            bridge_id = generate_id(
                f"reference-bridge:{action.id}:{child_action_id}:"
                f"{node_instance.id}:{public_port_id}:egress"
            )
            producer_id = f"bridge:{bridge_id}"
            for destination in destinations:
                destination.expected_producer_ids = [producer_id]
            await node_instance.save()
            await ReferenceBridgeService.create(
                parent_action_id=action.id,
                child_action_id=child_action_id,
                parent_node_instance_id=node_instance.id,
                public_port_id=public_port_id,
                direction=ReferenceBridgeDirectionEnum.EGRESS,
                sources=[
                    ReferenceStreamDescriptor(
                        stream_id=binding.stream_id,
                        queue_name=binding.queue_name,
                        owner_action_id=binding.owner_action_id,
                        protocol_version=binding.protocol_version,
                        expected_producer_ids=binding.expected_producer_ids,
                        termination="eos",
                    )
                    for binding in source_bindings
                ],
                destinations=[
                    ReferenceStreamDescriptor(
                        stream_id=binding.stream_id,
                        queue_name=binding.queue_name,
                        owner_action_id=binding.owner_action_id,
                        protocol_version=binding.protocol_version,
                        expected_producer_ids=[producer_id],
                        termination="eos",
                    )
                    for binding in destinations
                ],
                bridge_id=bridge_id,
            )
            created_bridges += 1

        child.reference_finalization_state = (
            "bridging" if created_bridges else "none"
        )
        await child.save()
        await ActionInstanceService.start(child_action_id)
        return child_action_id

    @staticmethod
    async def _reconcile_subflow(
        child_action_id: str,
    ) -> NodeExecutionOutcome | None:
        """把嵌入式子行动持久化状态映射为父节点执行结果。"""
        child = await ActionInstanceModel.find_one({"_id": child_action_id})
        if child is None:
            return None
        child_status_map = {
            ActionFlowStatusEnum.READY: "queued",
            ActionFlowStatusEnum.RUNNING: "running",
            ActionFlowStatusEnum.PAUSED: "paused",
            ActionFlowStatusEnum.COMPLETED: "completed",
            ActionFlowStatusEnum.FAILED: "failed",
            ActionFlowStatusEnum.CANCELLED: "cancelled",
            ActionFlowStatusEnum.TIMEOUT: "timeout",
            ActionFlowStatusEnum.STOPPED: "cancelled",
        }
        terminal_error_statuses = {
            ActionFlowStatusEnum.FAILED,
            ActionFlowStatusEnum.CANCELLED,
            ActionFlowStatusEnum.TIMEOUT,
            ActionFlowStatusEnum.STOPPED,
        }
        return NodeExecutionOutcome(
            status=child_status_map.get(child.status, "running"),
            outputs=child.invocation_outputs,
            progress=child.progress,
            error_message=(
                f"嵌入式子行动状态: {child.status.value}"
                if child.status in terminal_error_statuses
                else None
            )
        )

    @staticmethod
    async def _cancel_subflow(child_action_id: str, reason: str) -> bool:
        """停止嵌入式子行动。"""
        accepted, _ = await ActionInstanceService.stop(child_action_id)
        return accepted

    @staticmethod
    async def _close_native_reference_outputs(
        node_instance: ActionInstanceNodeModel,
        *,
        status: str,
        reason: str | None = None,
    ) -> bool:
        """为不经过组件 SDK 的原生生产者发布 Reference 终止帧。"""
        for binding in node_instance.reference_queue_bindings.values():
            if (
                binding.producer_kind != ReferenceProducerKindEnum.NATIVE
                or binding.control_status != "open"
            ):
                continue
            try:
                await publish_reference_control(
                    queue_names=[binding.queue_name],
                    stream_id=binding.stream_id,
                    producer_id=(
                        binding.expected_producer_ids[0]
                        if binding.expected_producer_ids
                        else node_instance.id
                    ),
                    action_id=binding.owner_action_id,
                    status=status,
                    reason=reason,
                )
            except Exception as exc:
                logger.error(
                    f"原生节点Reference终止帧发布失败，节点 {node_instance.id}: {exc}"
                )
                return False
            binding.control_status = status
            await node_instance.save()
        return True

    @staticmethod
    async def _finalize_execution_group(node_instance_id: str) -> bool:
        """按 execution_key 聚合通用执行记录并幂等收敛节点终态。"""
        executions = await ActionNodeExecutionModel.find(
            {"node_instance_id": node_instance_id}
        ).sort("execution_key").to_list()
        if not executions:
            return False
        active_statuses = {
            ActionInstanceNodeStatusEnum.QUEUED,
            ActionInstanceNodeStatusEnum.RUNNING,
            ActionInstanceNodeStatusEnum.WAITING,
            ActionInstanceNodeStatusEnum.AWAITING_APPROVAL,
            ActionInstanceNodeStatusEnum.PAUSED,
        }
        active = [item for item in executions if item.status in active_statuses]
        if active:
            await ActionInstanceNodeModel.find_one(
                {"_id": node_instance_id}
            ).update(
                {
                    "$set": {
                        "status": (
                            ActionInstanceNodeStatusEnum.AWAITING_APPROVAL
                            if any(
                                item.status
                                == ActionInstanceNodeStatusEnum.AWAITING_APPROVAL
                                for item in active
                            )
                            else ActionInstanceNodeStatusEnum.WAITING
                            if any(
                                item.status == ActionInstanceNodeStatusEnum.WAITING
                                for item in active
                            )
                            else ActionInstanceNodeStatusEnum.RUNNING
                        ),
                        "progress": round(
                            sum(item.progress for item in executions)
                            / len(executions),
                            2,
                        ),
                    }
                }
            )
            return True

        failure_priority = [
            ActionInstanceNodeStatusEnum.TIMEOUT,
            ActionInstanceNodeStatusEnum.FAILED,
            ActionInstanceNodeStatusEnum.CANCELLED,
        ]
        for failure_status in failure_priority:
            failed = next(
                (
                    item
                    for item in executions
                    if item.status == failure_status
                ),
                None,
            )
            if failed is None:
                continue
            node_instance = await ActionInstanceNodeModel.find_one(
                {"_id": node_instance_id}
            )
            if node_instance is not None:
                await ActionInstanceService._close_native_reference_outputs(
                    node_instance,
                    status="abort",
                    reason=failed.error_message or "原生节点执行失败",
                )
            sdk_status = {
                ActionInstanceNodeStatusEnum.TIMEOUT: "timed_out",
                ActionInstanceNodeStatusEnum.CANCELLED: "cancelled",
            }.get(failure_status, "failed")
            return await ActionInstanceService.finish_node(
                node_instance_id,
                SDKResultRequest(
                    result_id=failed.id,
                    attempt=failed.attempt,
                    status=sdk_status,
                    error=failed.error_message,
                ),
            )

        if not all(
            item.status == ActionInstanceNodeStatusEnum.COMPLETED
            for item in executions
        ):
            return False
        merged_outputs = {}
        for execution in executions:
            merged_outputs.update(execution.outputs)
        node_instance = await ActionInstanceNodeModel.find_one(
            {"_id": node_instance_id}
        )
        if (
            node_instance is not None
            and not await ActionInstanceService._close_native_reference_outputs(
                node_instance,
                status="eos",
            )
        ):
            return await ActionInstanceService.finish_node(
                node_instance_id,
                SDKResultRequest(
                    result_id=executions[-1].id,
                    attempt=max(item.attempt for item in executions),
                    status="failed",
                    error="原生节点Reference EOS发布失败",
                    exit_code=1,
                ),
            )
        return await ActionInstanceService.finish_node(
            node_instance_id,
            SDKResultRequest(
                result_id=executions[-1].id,
                attempt=max(item.attempt for item in executions),
                status="success",
                outputs=merged_outputs,
                exit_code=0,
            ),
        )

    @staticmethod
    async def _reconcile_node_execution(
        execution: ActionNodeExecutionModel,
    ) -> bool:
        """对账一个通用节点执行，并使用统一终态写回逻辑。"""
        node_instance = await ActionInstanceNodeModel.find_one(
            {"_id": execution.node_instance_id}
        )
        if node_instance is None:
            return False
        executor = node_executors.require(execution.driver)
        try:
            if (
                execution.deadline_at is not None
                and execution.deadline_at <= datetime.now()
            ):
                await executor.cancel(execution, "节点执行超时")
                outcome = NodeExecutionOutcome(
                    status="timeout",
                    progress=execution.progress,
                    extension_state=execution.extension_state,
                    extension_result=execution.extension_result,
                    error_message="节点执行超时",
                )
            else:
                outcome = await executor.reconcile(execution)
        except Exception as exc:
            logger.error(f"节点执行对账失败，Execution ID: {execution.id}: {exc}")
            outcome = NodeExecutionOutcome(
                status="failed",
                progress=execution.progress,
                extension_state=execution.extension_state,
                extension_result=execution.extension_result,
                error_message=str(exc),
            )
        if outcome is None:
            return False
        status = ActionInstanceNodeStatusEnum(outcome.status)
        active_statuses = [
            ActionInstanceNodeStatusEnum.QUEUED,
            ActionInstanceNodeStatusEnum.RUNNING,
            ActionInstanceNodeStatusEnum.WAITING,
            ActionInstanceNodeStatusEnum.AWAITING_APPROVAL,
            ActionInstanceNodeStatusEnum.PAUSED,
        ]
        claim = await ActionNodeExecutionModel.find_one(
            {
                "_id": execution.id,
                "status": {"$in": active_statuses},
            }
        ).update(
            {
                "$set": {
                    "status": status,
                    "progress": outcome.progress,
                    "outputs": outcome.outputs,
                    "extension_state": (
                        outcome.extension_state or execution.extension_state
                    ),
                    "extension_result": (
                        outcome.extension_result or execution.extension_result
                    ),
                    "error_message": outcome.error_message,
                    "finished_at": (
                        datetime.now()
                        if status
                        in {
                            ActionInstanceNodeStatusEnum.COMPLETED,
                            ActionInstanceNodeStatusEnum.FAILED,
                            ActionInstanceNodeStatusEnum.CANCELLED,
                            ActionInstanceNodeStatusEnum.TIMEOUT,
                        }
                        else None
                    ),
                    "updated_at": datetime.now(),
                }
            }
        )
        if not claim or getattr(claim, "modified_count", 0) != 1:
            return False
        action = await ActionInstanceModel.find_one({"_id": execution.action_id})
        await ActionLogService.ingest_node_event(
            execution,
            event_key=f"status:{status.value}",
            level=(
                "ERROR"
                if status
                in {
                    ActionInstanceNodeStatusEnum.FAILED,
                    ActionInstanceNodeStatusEnum.TIMEOUT,
                }
                else "INFO"
            ),
            source=(
                "subflow"
                if execution.driver == ActionExecutionDriverEnum.SUBFLOW.value
                else "native"
            ),
            message=f"节点执行状态更新为 {status.value}",
            fields={"progress": outcome.progress},
            exception=outcome.error_message,
            root_action_id=action.root_action_id if action else None,
            parent_action_id=action.parent_action_id if action else None,
        )
        await ActionInstanceService._finalize_execution_group(node_instance.id)
        return True

    @staticmethod
    async def consume_runtime_events(limit: int = 100) -> int:
        """消费分析与子行动终态事件，加速父节点状态收敛。"""
        consumer = "action-node-executor"
        events = await RuntimeDomainEventModel.find(
            {
                "topic": {
                    "$in": [
                        RuntimeDomainEventService.ANALYSIS_RUN_TERMINAL,
                        RuntimeDomainEventService.ACTION_TERMINAL,
                    ]
                },
                "processed_by": {"$ne": consumer},
            }
        ).sort("+occurred_at").limit(limit).to_list()
        consumed = 0
        active_statuses = {
            ActionInstanceNodeStatusEnum.QUEUED,
            ActionInstanceNodeStatusEnum.RUNNING,
            ActionInstanceNodeStatusEnum.WAITING,
            ActionInstanceNodeStatusEnum.AWAITING_APPROVAL,
            ActionInstanceNodeStatusEnum.PAUSED,
        }
        for event in events:
            if event.topic == RuntimeDomainEventService.ACTION_TERMINAL:
                parent_execution_id = str(
                    event.payload.get("parent_node_execution_id") or ""
                )
                execution = (
                    await ActionNodeExecutionModel.find_one(
                        {
                            "_id": parent_execution_id,
                            "driver": ActionExecutionDriverEnum.SUBFLOW.value,
                        }
                    )
                    if parent_execution_id
                    else None
                )
                executions = [execution] if execution else []
            else:
                source_ref = event.payload.get("source_ref") or {}
                node_instance_id = str(
                    source_ref.get("node_instance_id") or ""
                )
                if not node_instance_id:
                    await event.update(
                        {"$addToSet": {"processed_by": consumer}}
                    )
                    consumed += 1
                    continue
                executions = await ActionNodeExecutionModel.find(
                    {
                        "node_instance_id": node_instance_id,
                        "provider_run_id": event.aggregate_id,
                    }
                ).to_list()
            if not executions:
                continue
            settled = True
            for execution in executions:
                if execution.status not in active_statuses:
                    continue
                settled = (
                    await ActionInstanceService._reconcile_node_execution(execution)
                    and settled
                )
            if not settled:
                continue
            await event.update({"$addToSet": {"processed_by": consumer}})
            consumed += 1
        return consumed

    @staticmethod
    async def reconcile_node_executions() -> int:
        """轮询异步原生节点和封装节点，修复事件漏失。"""
        executions = await ActionNodeExecutionModel.find(
            {
                "status": {
                    "$in": [
                        ActionInstanceNodeStatusEnum.QUEUED,
                        ActionInstanceNodeStatusEnum.RUNNING,
                        ActionInstanceNodeStatusEnum.WAITING,
                        ActionInstanceNodeStatusEnum.AWAITING_APPROVAL,
                        ActionInstanceNodeStatusEnum.PAUSED,
                    ]
                },
                "driver": {
                    "$in": [
                        ActionExecutionDriverEnum.BACKEND_NATIVE.value,
                        ActionExecutionDriverEnum.SUBFLOW.value,
                    ]
                },
            }
        ).to_list()
        reconciled = 0
        for execution in executions:
            if await ActionInstanceService._reconcile_node_execution(execution):
                reconciled += 1
        return reconciled

    @staticmethod
    async def finalize_reference_actions(limit: int = 100) -> int:
        """在桥接进入终态后继续收敛等待中的嵌入式行动。"""
        actions = await ActionInstanceModel.find(
            {
                "status": ActionFlowStatusEnum.RUNNING,
                "reference_finalization_state": "bridging",
            }
        ).limit(limit).to_list()
        finalized = 0
        for action in actions:
            if not await ActionInstanceService.check_action_finished(action.id):
                continue
            before = action.status
            await ActionInstanceService.finish_action(action.id)
            current = await ActionInstanceModel.find_one({"_id": action.id})
            if current is not None and current.status != before:
                finalized += 1
        return finalized

    @staticmethod
    async def cancel_node_executions(action_id: str, reason: str) -> int:
        """通过统一执行器取消行动中的全部活动节点尝试。"""
        try:
            executions = await ActionNodeExecutionModel.find(
                {
                    "action_id": action_id,
                    "status": {
                        "$in": [
                            ActionInstanceNodeStatusEnum.QUEUED,
                            ActionInstanceNodeStatusEnum.RUNNING,
                            ActionInstanceNodeStatusEnum.WAITING,
                            ActionInstanceNodeStatusEnum.AWAITING_APPROVAL,
                            ActionInstanceNodeStatusEnum.PAUSED,
                        ]
                    },
                }
            ).to_list()
        except CollectionWasNotInitialized:
            return 0
        cancelled = 0
        for execution in executions:
            try:
                accepted = await node_executors.require(execution.driver).cancel(
                    execution,
                    reason,
                )
            except Exception as exc:
                logger.error(
                    f"取消节点执行失败，Execution ID: {execution.id}: {exc}"
                )
                accepted = False
            if not accepted:
                continue
            cancelled += 1
            await execution.update(
                {
                    "$set": {
                        "status": ActionInstanceNodeStatusEnum.CANCELLED,
                        "error_message": reason,
                        "finished_at": datetime.now(),
                        "updated_at": datetime.now(),
                    }
                }
            )
        return cancelled

    @staticmethod
    async def cancel_following_nodes(action_id: str, node_id: str):
        """
        递归取消后续节点
        """
        next_nodes = await ActionInstanceService.find_next_node(action_id, node_id)
        if not next_nodes:
            return

        for target_node_instance_id in next_nodes.keys():
            node_instance = await ActionInstanceNodeModel.find_one({"_id": target_node_instance_id})
            if not node_instance:
                continue

            if node_instance.status in [
                ActionInstanceNodeStatusEnum.PENDING,
                ActionInstanceNodeStatusEnum.UNREADY,
                ActionInstanceNodeStatusEnum.READY,
                ActionInstanceNodeStatusEnum.QUEUED,
                ActionInstanceNodeStatusEnum.UNKNOWN,
                ActionInstanceNodeStatusEnum.PAUSED,
            ]:
                node_instance.status = ActionInstanceNodeStatusEnum.CANCELLED
                node_instance.finished_at = datetime.now()
                await node_instance.save()

                await ActionInstanceService.cancel_following_nodes(action_id, node_instance.node_id)

    @staticmethod
    async def finish_component_run(
        component_run_id: str,
        result: SDKResultRequest,
    ) -> bool:
        component_run = await ComponentRunModel.find_one({"_id": component_run_id})
        if component_run is None or component_run.attempt != result.attempt:
            return False
        if component_run.result_id == result.result_id:
            return True
        if component_run.result_id is not None:
            return False

        terminal_status = {
            "success": ComponentRunStatusEnum.SUCCEEDED,
            "failed": ComponentRunStatusEnum.FAILED,
            "cancelled": ComponentRunStatusEnum.CANCELLED,
            "timed_out": ComponentRunStatusEnum.TIMED_OUT,
        }[result.status]
        now = datetime.now()
        claim = await ComponentRunModel.find_one(
            {
                "_id": component_run_id,
                "result_id": None,
                "status": {
                    "$in": [
                        ComponentRunStatusEnum.DISPATCHED,
                        ComponentRunStatusEnum.RUNNING,
                    ]
                },
            }
        ).update(
            {
                "$set": {
                    "status": terminal_status,
                    "result_id": result.result_id,
                    "outputs": result.outputs,
                    "error_message": result.error,
                    "exit_code": result.exit_code,
                    "finished_at": now,
                    "updated_at": now,
                    "progress": 100 if result.status == "success" else component_run.progress,
                }
            }
        )
        if not claim or getattr(claim, "modified_count", 0) != 1:
            current = await ComponentRunModel.find_one({"_id": component_run_id})
            return bool(current and current.result_id == result.result_id)

        component_run = await ComponentRunModel.find_one({"_id": component_run_id})
        if component_run is None:
            return False
        node_instance = await ActionInstanceNodeModel.find_one(
            {"_id": component_run.node_instance_id}
        )
        if node_instance is None:
            return False

        component_runs = await ComponentRunModel.find(
            {"node_instance_id": node_instance.id}
        ).to_list()
        active_statuses = {
            ComponentRunStatusEnum.CREATED,
            ComponentRunStatusEnum.DISPATCHED,
            ComponentRunStatusEnum.RUNNING,
        }
        has_active_runs = any(run.status in active_statuses for run in component_runs)
        timed_out_run = next(
            (
                run
                for run in component_runs
                if run.status == ComponentRunStatusEnum.TIMED_OUT
            ),
            None,
        )
        failed_run = next(
            (
                run
                for run in component_runs
                if run.status
                in {
                    ComponentRunStatusEnum.FAILED,
                    ComponentRunStatusEnum.CANCELLED,
                }
            ),
            None,
        )
        if has_active_runs and (timed_out_run is not None or failed_run is None):
            return True
        failed = timed_out_run or failed_run
        all_succeeded = bool(component_runs) and all(
            run.status == ComponentRunStatusEnum.SUCCEEDED for run in component_runs
        )
        if not failed and not all_succeeded:
            return True

        finalize_claim = await ActionInstanceNodeModel.find_one(
            {"_id": node_instance.id, "finalization_claimed": False}
        ).update({"$set": {"finalization_claimed": True}})
        if not finalize_claim or getattr(finalize_claim, "modified_count", 0) != 1:
            return True

        if failed:
            if failed.status != ComponentRunStatusEnum.TIMED_OUT:
                await ComponentRunModel.find(
                    {
                        "node_instance_id": node_instance.id,
                        "status": {"$in": list(active_statuses)},
                    }
                ).update({"$set": {"cancel_requested": True}})
            failed_status = {
                ComponentRunStatusEnum.CANCELLED: "cancelled",
                ComponentRunStatusEnum.TIMED_OUT: "timed_out",
            }.get(failed.status, "failed")
            node_result = SDKResultRequest(
                result_id=result.result_id,
                attempt=result.attempt,
                status=failed_status,
                error=failed.error_message or "组件运行失败",
                exit_code=failed.exit_code,
            )
        else:
            definition = await (
                ActionInstanceService.get_instance_node_definition(node_instance)
            )
            ordered = {run.component_id: run for run in component_runs}
            merged_outputs: dict[str, Any] = {}
            if definition:
                for component_id in definition.related_components:
                    run = ordered.get(component_id)
                    if run:
                        merged_outputs.update(run.outputs)
            node_result = SDKResultRequest(
                result_id=result.result_id,
                attempt=result.attempt,
                status="success",
                outputs=merged_outputs,
                exit_code=0,
            )
        await ActionInstanceService.finish_node(node_instance.id, node_result)
        return True

    @staticmethod
    async def expire_stale_actions() -> int:
        """将超过整体执行期限的行动收敛到超时，并停止其全部活动组件。"""
        now = datetime.now()
        running_actions = await ActionInstanceModel.find(
            {
                "status": ActionFlowStatusEnum.RUNNING,
                "implementation_period": {"$gt": 0},
            }
        ).to_list()
        expired = 0
        for action in running_actions:
            deadline_at = action.deadline_at
            if deadline_at is None and action.start_at is not None:
                deadline_at = action.start_at + timedelta(
                    seconds=action.implementation_period
                )
            if deadline_at is None or deadline_at > now:
                continue

            claim = await ActionInstanceModel.find_one(
                {"_id": action.id, "status": ActionFlowStatusEnum.RUNNING}
            ).update(
                {
                    "$set": {
                        "status": ActionFlowStatusEnum.TIMEOUT,
                        "deadline_at": deadline_at,
                        "finished_at": now,
                        "duration": (
                            max(
                                (now - action.start_at).total_seconds()
                                - getattr(action, "paused_duration", 0),
                                0,
                            )
                            if action.start_at
                            else 0
                        ),
                        "updated_at": now,
                    }
                }
            )
            if not claim or getattr(claim, "modified_count", 0) != 1:
                continue
            await RuntimeDomainEventService.publish_action_terminal(
                action,
                ActionFlowStatusEnum.TIMEOUT.value,
            )
            await publish_action_status_observation(
                action,
                ActionFlowStatusEnum.TIMEOUT,
                now,
            )

            active_runs = await ComponentRunModel.find(
                {
                    "action_id": action.id,
                    "status": {
                        "$in": [
                            ComponentRunStatusEnum.DISPATCHED,
                            ComponentRunStatusEnum.RUNNING,
                        ]
                    },
                }
            ).to_list()
            await ComponentRunModel.find(
                {
                    "action_id": action.id,
                    "status": {
                        "$in": [
                            ComponentRunStatusEnum.CREATED,
                            ComponentRunStatusEnum.DISPATCHED,
                            ComponentRunStatusEnum.RUNNING,
                        ]
                    },
                }
            ).update(
                {
                    "$set": {
                        "status": ComponentRunStatusEnum.CANCELLED,
                        "cancel_requested": True,
                        "error_message": "行动整体执行超时",
                        "finished_at": now,
                        "updated_at": now,
                    }
                }
            )
            await ActionInstanceNodeModel.find(
                {
                    "action_id": action.id,
                    "status": {
                        "$in": [
                            ActionInstanceNodeStatusEnum.QUEUED,
                            ActionInstanceNodeStatusEnum.RUNNING,
                            ActionInstanceNodeStatusEnum.WAITING,
                            ActionInstanceNodeStatusEnum.AWAITING_APPROVAL,
                        ]
                    },
                }
            ).update(
                {
                    "$set": {
                        "status": ActionInstanceNodeStatusEnum.TIMEOUT,
                        "error_message": "行动整体执行超时",
                        "finished_at": now,
                        "finalization_claimed": True,
                    }
                }
            )
            await ActionInstanceNodeModel.find(
                {
                    "action_id": action.id,
                    "status": {
                        "$in": [
                            ActionInstanceNodeStatusEnum.PENDING,
                            ActionInstanceNodeStatusEnum.UNREADY,
                            ActionInstanceNodeStatusEnum.READY,
                            ActionInstanceNodeStatusEnum.UNKNOWN,
                            ActionInstanceNodeStatusEnum.PAUSED,
                        ]
                    },
                }
            ).update(
                {
                    "$set": {
                        "status": ActionInstanceNodeStatusEnum.CANCELLED,
                        "error_message": "行动整体执行超时，节点未再运行",
                        "finished_at": now,
                        "finalization_claimed": True,
                    }
                }
            )
            if active_runs:
                await asyncio.gather(
                    *(cancel_component_run(run) for run in active_runs),
                    return_exceptions=True,
                )
            await ActionInstanceService.cancel_node_executions(
                action.id,
                "行动整体执行超时",
            )
            await ActionInstanceService.cancel_reference_bridges(
                action.id,
                "行动整体执行超时",
            )
            await ActionInstanceService.cleanup_action_queues(action.id)
            expired += 1
        return expired

    @staticmethod
    async def expire_stale_component_runs() -> int:
        """将心跳租约或最大运行时限已过期的 ComponentRun 收敛到超时终态。"""
        now = datetime.now()
        active_runs = await ComponentRunModel.find(
            {
                "status": {
                    "$in": [
                        ComponentRunStatusEnum.DISPATCHED,
                        ComponentRunStatusEnum.RUNNING,
                    ]
                }
            }
        ).to_list()
        stale_runs = [
            run
            for run in active_runs
            if (
                run.lease_expires_at is not None
                and run.lease_expires_at <= now
            )
            or (
                run.status == ComponentRunStatusEnum.DISPATCHED
                and run.lease_expires_at is None
                and (
                    now - run.updated_at
                ).total_seconds()
                >= settings.COMPONENT_BOOTSTRAP_EXPIRE_SECONDS
            )
            or (
                run.timeout_seconds > 0
                and run.started_at is not None
                and (now - run.started_at).total_seconds() >= run.timeout_seconds
            )
        ]
        expired = 0
        for component_run in stale_runs:
            error_message = (
                "组件启动超时，未在引导凭证有效期内完成初始化"
                if (
                    component_run.status == ComponentRunStatusEnum.DISPATCHED
                    and component_run.started_at is None
                )
                else "组件心跳租约或运行时限已过期"
            )
            accepted = await ActionInstanceService.finish_component_run(
                component_run.id,
                SDKResultRequest(
                    result_id=f"timeout:{component_run.id}:{component_run.attempt}",
                    attempt=component_run.attempt,
                    status="timed_out",
                    error=error_message,
                    exit_code=1,
                ),
            )
            expired += int(accepted)
        if stale_runs:
            await asyncio.gather(
                *(cancel_component_run(run) for run in stale_runs),
                return_exceptions=True,
            )
        return expired

    @staticmethod
    async def finish_node(node_instance_id: str, result: SDKResultRequest):
        node_instance = await ActionInstanceNodeModel.find_one({"_id": node_instance_id})
        if not node_instance:
            logger.error(f"上报节点实例不存在，ID: {node_instance_id}")
            return False
        current_action = await ActionInstanceModel.find_one(
            {"_id": node_instance.action_id}
        )
        if (
            current_action is None
            or current_action.status
            not in {
                ActionFlowStatusEnum.RUNNING,
                ActionFlowStatusEnum.PAUSED,
            }
        ):
            return False

        public_output_ids = set()
        public_output_types: dict[str, str] = {}
        public_interface = (
            current_action.execution_plan_snapshot.public_interface_snapshot or {}
        )
        for item in public_interface.get("outputs", []):
            output_id = item.get("id")
            if not output_id:
                continue
            public_output_ids.add(output_id)
            data_type = item.get("data_type", "value")
            public_output_types[output_id] = getattr(
                data_type,
                "value",
                data_type,
            )
        node_definition = await (
            ActionInstanceService.get_instance_node_definition(node_instance)
        )
        
        if result.status == "success":
            node_instance.status = ActionInstanceNodeStatusEnum.COMPLETED
            node_instance.progress = 100.0
            node_instance.finished_at = datetime.now()
            node_instance.duration = (
                (datetime.now() - node_instance.start_at).total_seconds()
                if node_instance.start_at
                else 0
            )
            for handle_name, value in result.outputs.items():
                output_handle = None
                handle_definition = await ActionInstanceService.get_handle_definition_by_name(handle_name)
                if not handle_definition and node_definition:
                    output_handle = next(
                        (
                            handle
                            for handle in node_definition.handles
                            if handle.type == "source"
                            and handle_name in {handle.id, handle.port_id}
                        ),
                        None,
                    )
                    if output_handle:
                        _, handle_definition = await (
                            ActionInstanceService.resolve_node_handle_definition(
                                node_definition,
                                output_handle.id,
                            )
                        )
                elif handle_definition and node_definition:
                    output_handle = next(
                        (
                            handle
                            for handle in node_definition.handles
                            if handle.type == "source"
                            and handle_definition.id
                            == (handle.handle_config_id or handle.id)
                        ),
                        None,
                    )
                if not handle_definition:
                    if handle_name in public_output_ids:
                        if public_output_types.get(handle_name) == "reference":
                            continue
                        node_instance.outputs[handle_name] = ActionConfigIOModel(
                            key=handle_name,
                            value=value,
                            type=ActionConfigIOTypeEnum.VALUE,
                        )
                    continue
                
                if handle_definition.type == ActionConfigIOTypeEnum.REFERENCE:
                    continue
                
                output_key = (
                    output_handle.port_id
                    if output_handle and output_handle.port_id
                    else handle_definition.id
                )
                node_instance.outputs[output_key] = ActionConfigIOModel(
                    key=handle_name, 
                    value=value,
                    type=handle_definition.type
                )
                
            await node_instance.save()

            action = await ActionInstanceModel.find_one({"_id": node_instance.action_id})
            if action is None or action.status not in {
                ActionFlowStatusEnum.RUNNING,
                ActionFlowStatusEnum.PAUSED,
            }:
                return False
            if node_instance.id not in action.finished_nodes_instance:
                action.finished_nodes_instance.append(node_instance.id)
            for output_id in public_output_ids:
                if (
                    public_output_types.get(output_id) != "reference"
                    and output_id in result.outputs
                ):
                    action.invocation_outputs[output_id] = result.outputs[output_id]
            node_instance.progress = 100.0
            await action.save()
            current_execution_id = getattr(
                node_instance,
                "current_execution_id",
                None,
            )
            if current_execution_id:
                await ActionNodeExecutionModel.find_one(
                    {"_id": current_execution_id}
                ).update(
                    {
                        "$set": {
                            "status": ActionInstanceNodeStatusEnum.COMPLETED,
                            "outputs": result.outputs,
                            "progress": 100,
                            "finished_at": datetime.now(),
                            "updated_at": datetime.now(),
                        }
                    }
                )
        elif result.status in {"failed", "cancelled", "timed_out"}:
            node_instance.status = {
                "failed": ActionInstanceNodeStatusEnum.FAILED,
                "cancelled": ActionInstanceNodeStatusEnum.CANCELLED,
                "timed_out": ActionInstanceNodeStatusEnum.TIMEOUT,
            }[result.status]
            node_instance.error_message = result.error
            node_instance.finished_at = datetime.now()
            node_instance.duration = (
                (datetime.now() - node_instance.start_at).total_seconds()
                if node_instance.start_at
                else 0
            )
            await node_instance.save()
            current_execution_id = getattr(
                node_instance,
                "current_execution_id",
                None,
            )
            if current_execution_id:
                await ActionNodeExecutionModel.find_one(
                    {"_id": current_execution_id}
                ).update(
                    {
                        "$set": {
                            "status": node_instance.status,
                            "error_message": result.error,
                            "finished_at": datetime.now(),
                            "updated_at": datetime.now(),
                        }
                    }
                )
            
            # 更新行动进度
            action = await ActionInstanceModel.find_one({"_id": node_instance.action_id})
            if action:
                if node_instance.id not in action.finished_nodes_instance:
                    action.finished_nodes_instance.append(node_instance.id)
                executable_node_count = len(action.execution_plan_snapshot.nodes)
                action.progress = (
                    round(
                        len(action.finished_nodes_instance)
                        / executable_node_count
                        * 100,
                        2,
                    )
                    if executable_node_count > 0
                    else 100.0
                )
                await action.save()
            
            # 取消后续节点
            await ActionInstanceService.cancel_following_nodes(node_instance.action_id, node_instance.node_id)

            # 检查行动是否完成
            action = await ActionInstanceModel.find_one(
                {"_id": node_instance.action_id}
            )
            if (
                action is not None
                and action.status == ActionFlowStatusEnum.RUNNING
                and await ActionInstanceService.check_action_finished(
                    node_instance.action_id
                )
            ):
                await ActionInstanceService.finish_action(node_instance.action_id)
            
            return False
        else:
            node_instance.status = ActionInstanceNodeStatusEnum.UNKNOWN
            node_instance.finished_at = datetime.now()
            node_instance.duration = (datetime.now() - node_instance.start_at).total_seconds()
            await node_instance.save()
            return False
        
        action = await ActionInstanceModel.find_one({"_id": node_instance.action_id})
        if not action:
            logger.error(f"未找到行动，Action ID: {node_instance.action_id}")
            return False
        if action.status not in {
            ActionFlowStatusEnum.RUNNING,
            ActionFlowStatusEnum.PAUSED,
        }:
            return False
            
        if not node_definition:
            logger.error(f"未找到节点定义，Node Instance ID: {node_instance.id}")
            return False
        
        next_nodes = await ActionInstanceService.find_next_node(action.id, node_instance.node_id)
        if not next_nodes:
            if (
                action.status == ActionFlowStatusEnum.RUNNING
                and await ActionInstanceService.check_action_finished(action.id)
            ):
                await ActionInstanceService.finish_action(action.id)
                return True
            if action.status == ActionFlowStatusEnum.PAUSED:
                return True
            else:
                logger.warning(f"行动未完成，但无法找到下一个节点，Action ID: {action.id}, Node Instance ID: {node_instance.id}")
            return False
        
        # 1. 搬运数据 2. 运行下一个节点
        for target_node_id, edge_mappings in next_nodes.items():
            next_node_instance = await ActionInstanceNodeModel.find_one({"_id": target_node_id})
            if not next_node_instance:
                logger.error(f"未找到下一个节点实例，Node Instance ID: {target_node_id}")
                continue
            target_node_definition = await (
                ActionInstanceService.get_instance_node_definition(
                    next_node_instance
                )
            )
            allow_multiple_inputs = bool(
                (
                    target_node_definition.extension.config.get("compiler", {})
                    if target_node_definition
                    and target_node_definition.extension
                    else {}
                ).get("allow_multiple_inputs", False)
            )
            multi_input_updates = {}
            
            for source_handle_id, target_handle_id in edge_mappings:
                reference_binding = next(
                    (
                        binding
                        for binding in node_instance.reference_queue_bindings.values()
                        if binding.target_node_id == next_node_instance.node_id
                        and binding.source_port_id == source_handle_id
                        and binding.target_port_id == target_handle_id
                    ),
                    None,
                )
                target_handle, target_handle_definition = await (
                    ActionInstanceService.resolve_node_handle_definition(
                        target_node_definition,
                        target_handle_id,
                    )
                )
                if not target_handle_definition:
                    logger.error(f"未找到目标连接点定义，Target Handle ID: {target_handle_id}")
                    continue
                
                if reference_binding is not None:
                    queue_name = reference_binding.queue_name
                    input_slot = (
                        generate_id(
                            f"multi-input:{next_node_instance.id}:"
                            f"{target_handle_id}:{node_instance.node_id}:"
                            f"{source_handle_id}"
                        )
                        if allow_multiple_inputs
                        else target_handle_id
                    )
                    next_node_instance.inputs[input_slot] = ActionConfigIOModel(
                        key=target_handle_definition.handle_name,
                        value=queue_name,
                        type=ActionConfigIOTypeEnum.REFERENCE,
                    )
                    if allow_multiple_inputs:
                        multi_input_updates[f"inputs.{input_slot}"] = (
                            next_node_instance.inputs[input_slot].model_dump(
                                mode="python"
                            )
                        )
                    logger.info(
                        f"按执行边 {reference_binding.edge_id} 传递队列 "
                        f"{queue_name} 给节点 {next_node_instance.node_id}"
                    )
                    continue

                _, source_handle_definition = await (
                    ActionInstanceService.resolve_node_handle_definition(
                        node_definition,
                        source_handle_id,
                    )
                )
                if not source_handle_definition:
                    logger.error(
                        f"未找到源连接点定义，Source Handle ID: {source_handle_id}"
                    )
                    continue

                if source_handle_definition.type == ActionConfigIOTypeEnum.REFERENCE:
                    logger.error(
                        f"REFERENCE 执行边缺少队列绑定，Edge: "
                        f"{node_instance.node_id}:{source_handle_id} -> "
                        f"{next_node_instance.node_id}:{target_handle_id}"
                    )
                else:
                    if source_handle_id in node_instance.outputs:
                        source_output = node_instance.outputs[source_handle_id]
                        input_slot = (
                            generate_id(
                                f"multi-input:{next_node_instance.id}:"
                                f"{target_handle_id}:{node_instance.node_id}:"
                                f"{source_handle_id}"
                            )
                            if allow_multiple_inputs
                            else target_handle_id
                        )
                        next_node_instance.inputs[input_slot] = ActionConfigIOModel(
                            key=target_handle_definition.handle_name,
                            value=source_output.value,
                            type=source_output.type
                        )
                        if allow_multiple_inputs:
                            multi_input_updates[f"inputs.{input_slot}"] = (
                                next_node_instance.inputs[input_slot].model_dump(
                                    mode="python"
                                )
                            )
                    else:
                        logger.error(f"未找到源连接点的输出数据，Source Handle ID: {source_handle_id}")

            delivery_update = {
                "$addToSet": {
                    "delivered_dependencies": node_instance.node_id,
                }
            }
            if multi_input_updates or not allow_multiple_inputs:
                delivery_update["$set"] = (
                    multi_input_updates
                    if allow_multiple_inputs
                    else {"inputs": next_node_instance.inputs}
                )
            await ActionInstanceNodeModel.find_one(
                {"_id": next_node_instance.id}
            ).update(delivery_update)

            # 运行下一个节点
            if action.status == ActionFlowStatusEnum.RUNNING:
                await ActionInstanceService.run_node(next_node_instance.id, action.id)
        
        return True
    
    @staticmethod
    async def find_next_node(action_id: str, node_id: str):
        """
        查找下一个节点的实例ID列表以及对应的连接点映射
        返回结构：{目标节点实例ID: [(source_port_id, target_port_id), ...]}
        """
        action = await ActionInstanceModel.find_one({"_id": action_id})
        if not action:
            logger.error(f"未找到行动，Action ID: {action_id}")
            return {}
        
        blueprint = await ActionInstanceService.get_action_blueprint(action)
        if not blueprint:
            logger.error(f"未找到蓝图，Blueprint ID: {action.blueprint_id}")
            return {}
        
        next_nodes = {}
        execution_edges = action.execution_plan_snapshot.edges
        for edge in execution_edges:
            if edge.source == node_id:
                instance_id = generate_id(action_id + edge.target)
                edge_mapping = (
                    edge.source_port_id,
                    edge.target_port_id,
                )
                if instance_id in next_nodes:
                    next_nodes[instance_id].append(edge_mapping)
                else:
                    next_nodes[instance_id] = [edge_mapping]
        
        return next_nodes

    @staticmethod
    async def find_all_previous_nodes(action_id: str, node_id: str):
        """
        获取所有前置节点实例ID列表
        """
        action = await ActionInstanceModel.find_one({"_id": action_id})
        if not action:
            logger.error(f"未找到行动，Action ID: {action_id}")
            return False
        
        blueprint = await ActionInstanceService.get_action_blueprint(action)
        if not blueprint:
            logger.error(f"未找到蓝图，Blueprint ID: {action.blueprint_id}")
            return False
        
        previous_nodes = []
        execution_edges = action.execution_plan_snapshot.edges
        for edge in execution_edges:
            if edge.target == node_id:
                previous_nodes.append(edge.source)
        
        return previous_nodes

    @staticmethod
    async def set_node_status(node_id: str, action_id: str, status: ActionInstanceNodeStatusEnum):
        node_instance = await ActionInstanceNodeModel.find_one({"node_id": node_id, "action_id": action_id})
        if not node_instance:
            logger.error(f"未找到节点，Action ID: {action_id}，Node ID: {node_id}")
            return False
        
        node_instance.status = status
        await node_instance.save()
        return True

    @staticmethod
    async def cleanup_action_queues(action_id: str) -> bool:
        """
        清理行动相关的所有临时队列
        """
        queue_names = set()
        node_instances = await ActionInstanceNodeModel.find({"action_id": action_id}).to_list()
        for node_instance in node_instances:
            for binding in node_instance.reference_queue_bindings.values():
                if binding.owner_action_id == action_id:
                    queue_names.add(binding.queue_name)
        
        cleanup_results = []
        for queue_name in queue_names:
            try:
                deleted = await delete_queue(queue_name)
                cleanup_results.append(deleted)
                if deleted:
                    logger.info(f"已清理队列: {queue_name}")
            except Exception as e:
                cleanup_results.append(False)
                logger.error(f"清理队列失败，队列名: {queue_name}, 错误: {str(e)}")
        cleaned = all(cleanup_results)
        await ActionInstanceModel.find_one({"_id": action_id}).update(
            {
                "$set": {
                    "queue_cleanup_state": (
                        "completed" if cleaned else "failed"
                    ),
                    "updated_at": datetime.now(),
                }
            }
        )
        return cleaned

    @staticmethod
    async def retry_failed_queue_cleanup(limit: int = 100) -> int:
        """重试终态 Action 上次失败的自有 Reference 队列清理。"""
        terminal_statuses = [
            ActionFlowStatusEnum.COMPLETED,
            ActionFlowStatusEnum.FAILED,
            ActionFlowStatusEnum.CANCELLED,
            ActionFlowStatusEnum.TIMEOUT,
            ActionFlowStatusEnum.STOPPED,
        ]
        actions = await ActionInstanceModel.find(
            {
                "status": {"$in": terminal_statuses},
                "queue_cleanup_state": "failed",
            }
        ).limit(limit).to_list()
        cleaned = 0
        for action in actions:
            cleaned += int(
                await ActionInstanceService.cleanup_action_queues(action.id)
            )
        return cleaned

    @staticmethod
    async def cancel_reference_bridges(action_id: str, reason: str) -> int:
        """取消以指定 Action 作为父级或子级的活动 Reference 桥接。"""
        try:
            bridges = await ReferenceBridgeModel.find(
                {
                    "$or": [
                        {"parent_action_id": action_id},
                        {"child_action_id": action_id},
                    ],
                    "status": {
                        "$in": [
                            ReferenceBridgeStatusEnum.PENDING,
                            ReferenceBridgeStatusEnum.RUNNING,
                        ]
                    },
                }
            ).to_list()
        except CollectionWasNotInitialized:
            return 0
        if not bridges:
            return 0
        results = await asyncio.gather(
            *(
                ReferenceBridgeService.cancel(bridge.id, reason)
                for bridge in bridges
            ),
            return_exceptions=True,
        )
        return sum(result is True for result in results)
    
    @staticmethod
    async def finish_action(action_id: str):
        """
        完成行动
        """
        action = await ActionInstanceModel.find_one({"_id": action_id})
        if not action:
            logger.error(f"未找到行动，Action ID: {action_id}")
            return False
        if action.status == ActionFlowStatusEnum.TIMEOUT:
            return True

        timeout_count = await ActionInstanceNodeModel.find({
            "action_id": action_id,
            "status": ActionInstanceNodeStatusEnum.TIMEOUT,
        }).count()
        failed_count = await ActionInstanceNodeModel.find({
            "action_id": action_id,
            "status": {
                "$in": [
                    ActionInstanceNodeStatusEnum.FAILED,
                    ActionInstanceNodeStatusEnum.CANCELLED,
                ]
            }
        }).count()

        status = (
            ActionFlowStatusEnum.TIMEOUT
            if timeout_count > 0
            else ActionFlowStatusEnum.FAILED
            if failed_count > 0
            else ActionFlowStatusEnum.COMPLETED
        )
        reference_finalization_state = getattr(
            action,
            "reference_finalization_state",
            "none",
        )
        if (
            status == ActionFlowStatusEnum.COMPLETED
            and reference_finalization_state == "bridging"
        ):
            bridges = await ReferenceBridgeModel.find(
                {"child_action_id": action_id}
            ).to_list()
            failed_bridge = next(
                (
                    bridge
                    for bridge in bridges
                    if bridge.status
                    in {
                        ReferenceBridgeStatusEnum.FAILED,
                        ReferenceBridgeStatusEnum.CANCELLED,
                    }
                ),
                None,
            )
            active_bridges = [
                bridge
                for bridge in bridges
                if bridge.status
                in {
                    ReferenceBridgeStatusEnum.PENDING,
                    ReferenceBridgeStatusEnum.RUNNING,
                }
            ]
            if failed_bridge is not None:
                status = ActionFlowStatusEnum.FAILED
                reference_finalization_state = "failed"
            elif active_bridges:
                await ActionInstanceModel.find_one(
                    {
                        "_id": action_id,
                        "status": ActionFlowStatusEnum.RUNNING,
                    }
                ).update(
                    {
                        "$set": {
                            "reference_finalization_state": "bridging",
                            "progress": 100.0,
                            "updated_at": datetime.now(),
                        }
                    }
                )
                return True
            else:
                reference_finalization_state = "completed"
        executable_node_count = len(action.execution_plan_snapshot.nodes)
        now = datetime.now()
        claim = await ActionInstanceModel.find_one(
            {"_id": action_id, "status": ActionFlowStatusEnum.RUNNING}
        ).update(
            {
                "$set": {
                    "status": status,
                    "finished_at": now,
                    "duration": (
                        max(
                            (now - action.start_at).total_seconds()
                            - getattr(action, "paused_duration", 0),
                            0,
                        )
                        if action.start_at
                        else 0
                    ),
                    "progress": (
                        round(
                            len(action.finished_nodes_instance)
                            / executable_node_count
                            * 100,
                            2,
                        )
                        if executable_node_count
                        else 100.0
                    ),
                    "updated_at": now,
                    "reference_finalization_state": reference_finalization_state,
                }
            }
        )
        if not claim or getattr(claim, "modified_count", 0) != 1:
            return False
        await RuntimeDomainEventService.publish_action_terminal(
            action,
            status.value,
        )
        await publish_action_status_observation(
            action,
            status,
            now,
        )
        if status != ActionFlowStatusEnum.COMPLETED:
            await ActionInstanceService.cancel_reference_bridges(
                action_id,
                f"行动以 {status.value} 状态结束",
            )
        await ActionInstanceService.cleanup_action_queues(action_id)
        return True

    @staticmethod
    async def check_action_finished(action_id: str):
        """
        判断行动是否所有节点全部完成(包括成功、失败、取消)
        """
        count = await ActionInstanceNodeModel.find({
            "action_id": action_id,
            "status": {
                "$in": [
                    ActionInstanceNodeStatusEnum.PENDING,
                    ActionInstanceNodeStatusEnum.UNREADY,
                    ActionInstanceNodeStatusEnum.READY,
                    ActionInstanceNodeStatusEnum.QUEUED,
                    ActionInstanceNodeStatusEnum.RUNNING,
                    ActionInstanceNodeStatusEnum.WAITING,
                    ActionInstanceNodeStatusEnum.AWAITING_APPROVAL,
                    ActionInstanceNodeStatusEnum.UNKNOWN,
                    ActionInstanceNodeStatusEnum.PAUSED
                ]
            }
        }).count()
        
        return count == 0
    
    @staticmethod
    async def update_progress(node_instance_id: str, progress: float):
        """
        更新节点运行进度
        """
        if progress > 100:
            progress = 100.0
        if progress < 0:
            progress = 0.0
        
        progress = round(progress, 2)
        
        node_instance = await ActionInstanceNodeModel.find_one({"_id": node_instance_id})
        if not node_instance:
            logger.error(f"未找到节点实例，Node Instance ID: {node_instance_id}")
            return False
        
        node_instance.progress = progress
        await node_instance.save()
        return True


_COMPONENT_NODE_EXECUTOR = ComponentNodeExecutor(
    ActionInstanceService.get_node_definition,
)
_BACKEND_NATIVE_NODE_EXECUTOR = BackendNativeNodeExecutor(native_handlers)
_SUBFLOW_NODE_EXECUTOR = SubflowNodeExecutor(
    ActionInstanceService._start_subflow_attempt,
    ActionInstanceService._reconcile_subflow,
    ActionInstanceService._cancel_subflow,
)
node_executors.register(
    ActionExecutionDriverEnum.COMPONENT.value,
    _COMPONENT_NODE_EXECUTOR,
)
node_executors.register(
    ActionExecutionDriverEnum.BACKEND_NATIVE.value,
    _BACKEND_NATIVE_NODE_EXECUTOR,
)
node_executors.register(
    ActionExecutionDriverEnum.SUBFLOW.value,
    _SUBFLOW_NODE_EXECUTOR,
)
