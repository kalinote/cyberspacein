
import asyncio
from datetime import datetime, timedelta
import random
from typing import Any
from beanie.operators import In
from pymongo.errors import DuplicateKeyError
from app.core.config import settings
from app.models.action.action import ActionConfigIOModel, ActionInstanceModel, ActionInstanceNodeModel
from app.models.action.component_run import ComponentRunModel
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
    ComponentRunStatusEnum,
)
from app.service.component import cancel_component_run, dispatch_component_run
from app.utils.dict_helper import pack_dict, unpack_dict
from app.utils.id_lib import generate_id
from app.service.component_auth import issue_component_bootstrap
from app.utils.workflow import find_start_nodes
from app.models.action.blueprint import (
    ActionBlueprintModel,
    ActionBlueprintSnapshotModel,
    create_blueprint_snapshot,
)
from app.db.rabbitmq import delete_queue
from app.db.redis import get_redis

logger = logger.bind(name=__name__)


async def node_model_to_response(node: ActionNodeModel) -> ActionNodeResponse:
    handle_ids = [h.id for h in node.handles]
    handle_configs = await ActionNodesHandleConfigModel.find(In(ActionNodesHandleConfigModel.id, handle_ids)).to_list()
    handle_config_map = {c.id: c for c in handle_configs}
    handles_response = []
    for handle in node.handles:
        handle_config = handle_config_map.get(handle.id)
        custom_style = unpack_dict(handle_config.custom_style) if handle_config else {}
        custom_style = dict(custom_style)
        custom_style.update(unpack_dict(handle.custom_style) or {})
        handles_response.append(ActionNodeHandleResponse(
            id=handle.id,
            relabel=handle.relabel,
            type=handle.type,
            position=handle.position,
            custom_style=custom_style,
            handle_name=handle_config.handle_name if handle_config else "",
            data_type=handle_config.type if handle_config else "value",
            label=handle_config.label if handle_config else "",
            color=handle_config.color if handle_config else "",
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
    ) -> ActionBlueprintModel | ActionBlueprintSnapshotModel | None:
        """优先返回行动快照，旧行动没有快照时回退读取当前蓝图。"""
        blueprint_snapshot = getattr(action, "blueprint_snapshot", None)
        if blueprint_snapshot is not None:
            return blueprint_snapshot
        return await ActionInstanceService.get_blueprint(action.blueprint_id)
    
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
    async def init(
        blueprint_id: str,
        inject_params: dict[str, Any] | None = None,
        *,
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
        
        param_required_map: dict[str, bool] = {}
        template_bindings: dict[str, dict[str, str]] = {}
        
        if blueprint.is_template:
            if not blueprint.template:
                logger.error(f"模板蓝图缺少模板配置: {blueprint_id}")
                return False, f"模板蓝图缺少模板配置: {blueprint_id}"
            
            template = blueprint.template
            if "params" in template and template["params"]:
                for param in template["params"]:
                    param_name = param.get("name")
                    if param_name:
                        param_required_map[param_name] = param.get("required", False)
            
            if "bindings" in template and template["bindings"]:
                template_bindings = template["bindings"]
        
        action_instance = ActionInstanceModel(
            id=action_id,
            blueprint_id=blueprint_id,
            blueprint_snapshot=create_blueprint_snapshot(blueprint),
            status=ActionFlowStatusEnum.READY,
            implementation_period=blueprint.implementation_period,
            nodes_id=[node.id for node in blueprint.graph.nodes],
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
        
        for node in blueprint.graph.nodes:
            default_configs = []
            node_definition = await ActionInstanceService.get_node_definition(node.data.definition_id)
            if node_definition:
                default_configs = node_definition.default_configs or []
            
            form_data = node.data.form_data or []
            form_data_dict = unpack_dict(form_data) or {}
            fields_to_remove = set()
            
            if blueprint.is_template and node.id in template_bindings:
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
                status=ActionInstanceNodeStatusEnum.PENDING,
                configs=form_data + default_configs,
                definition_id=node.data.definition_id
            )
            await action_instance_node.insert()
        
        start_nodes = find_start_nodes(blueprint)
        if not start_nodes:
            logger.warning(f"没有找到起始节点: {action_id}")
        
        for node in start_nodes:
            await ActionInstanceService.set_node_status(node.id, action_id, ActionInstanceNodeStatusEnum.READY)
        
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
                }
            }
        )
        if not claim or getattr(claim, "modified_count", 0) != 1:
            logger.info(f"行动已启动或不存在，跳过重复启动: {action_id}")
            return
        action = await ActionInstanceModel.find_one({"_id": action_id})

        ready_nodes = await ActionInstanceNodeModel.find({"action_id": action.id, "status": ActionInstanceNodeStatusEnum.READY}).to_list()
        for node in ready_nodes:
            await ActionInstanceService.run_node(node.id, action_id)

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
        for edge in blueprint.graph.edges:
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
            node_definition = await ActionInstanceService.get_node_definition(
                node_instance.definition_id
            )
            if node_definition is not None:
                await ActionInstanceService._dispatch_component_runs(
                    action,
                    node_instance,
                    node_definition,
                    component_runs,
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
        queues_cleaned = await ActionInstanceService.cleanup_action_queues(action_id)
        if not queues_cleaned:
            return True, "行动已停止，但部分引用队列清理失败"
        return True, "行动已停止，引用队列已清理"

    @staticmethod
    async def _dispatch_component_runs(
        action: ActionInstanceModel,
        node_instance: ActionInstanceNodeModel,
        node_definition: ActionNodeModel,
        component_runs: list[ComponentRunModel],
    ) -> bool:
        """派发节点中尚未启动的组件运行。

        暂停发生在派发过程中时保留 CREATED 记录，恢复行动后继续派发；
        调度平台本身拒绝任务时则按既有失败语义收敛整个节点。
        """
        command = node_definition.command
        command_args = [
            "run",
            *node_definition.command_args,
            "--api-base-url",
            settings.api_base_url,
        ]
        dispatch_failed = False
        for component_run in component_runs:
            component_bootstrap = await issue_component_bootstrap(
                action.id,
                node_instance.id,
                component_run.id,
            )
            component_args = command_args + [
                "--component-run-id",
                component_run.id,
                f"--component-bootstrap={component_bootstrap}",
            ]
            accepted = await dispatch_component_run(
                component_run,
                command,
                component_args,
                priority=action.schedule_priority,
            )
            if not accepted:
                current_action = await ActionInstanceModel.find_one(
                    {"_id": action.id}
                )
                if (
                    current_action is None
                    or current_action.status != ActionFlowStatusEnum.RUNNING
                ):
                    return False
                logger.error(
                    "运行组件失败，调度平台无结果返回，Component ID: "
                    f"{component_run.component_id}"
                )
                dispatch_failed = True
                break

        if not dispatch_failed:
            return True

        await ComponentRunModel.find(
            {
                "node_instance_id": node_instance.id,
                "status": ComponentRunStatusEnum.CREATED,
            }
        ).update(
            {
                "$set": {
                    "status": ComponentRunStatusEnum.CANCELLED,
                    "error_message": "同节点组件派发失败，运行已取消",
                    "finished_at": datetime.now(),
                    "updated_at": datetime.now(),
                }
            }
        )
        await ComponentRunModel.find(
            {
                "node_instance_id": node_instance.id,
                "status": {
                    "$in": [
                        ComponentRunStatusEnum.DISPATCHED,
                        ComponentRunStatusEnum.RUNNING,
                    ]
                },
            }
        ).update({"$set": {"cancel_requested": True}})
        node_instance.status = ActionInstanceNodeStatusEnum.FAILED
        node_instance.finalization_claimed = True
        node_instance.error_message = "运行组件失败，调度平台无结果返回"
        node_instance.finished_at = datetime.now()
        node_instance.duration = (
            (datetime.now() - node_instance.start_at).total_seconds()
            if node_instance.start_at
            else 0
        )
        await node_instance.save()
        await ActionInstanceService.cancel_following_nodes(
            action.id, node_instance.node_id
        )
        if await ActionInstanceService.check_action_finished(action.id):
            await ActionInstanceService.finish_action(action.id)
        return False


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
        
        node_definition = await ActionInstanceService.get_node_definition(node_instance.definition_id)
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
        for prev_node in previous_node_instances:
            if prev_node.status != ActionInstanceNodeStatusEnum.COMPLETED:
                logger.info(f"前置节点未完成({prev_node.node_id})，等待中，当前节点: {node_instance.id}，前置节点: {prev_node.id}")
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
        
        for edge in blueprint.graph.edges:
            if edge.source == node_instance.node_id:
                handle_definition = await ActionInstanceService.get_handle_definition(edge.sourceHandle)
                if not handle_definition:
                    # logger.error(f"未找到连接点定义，Handle ID: {edge.sourceHandle}")
                    continue
                
                if handle_definition.type == ActionConfigIOTypeEnum.REFERENCE:
                    if edge.target not in node_instance.reference_queues:
                        queue_name = generate_id(action_id + edge.target + datetime.now().strftime("%Y%m%d%H%M%S") + str(random.randint(1000, 9999)))
                        node_instance.reference_queues[edge.target] = queue_name
                        logger.info(f"为节点 {node_instance.node_id} -> {edge.target} 生成队列: {queue_name}")
        
        if node_instance.reference_queues:
            reference_claim = await ActionInstanceNodeModel.find_one(
                {
                    "_id": node_instance.id,
                    "status": ActionInstanceNodeStatusEnum.QUEUED,
                }
            ).update(
                {"$set": {"reference_queues": node_instance.reference_queues}}
            )
            if not reference_claim or getattr(reference_claim, "modified_count", 0) != 1:
                return False
        
        # 这里是开始运行，在此之前应该做好全部准备工作
        related_components = node_definition.related_components

        if not related_components:
            node_instance.status = ActionInstanceNodeStatusEnum.FAILED
            node_instance.error_message = "节点未关联基础组件"
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

        component_runs: list[ComponentRunModel] = []
        for component in related_components:
            component_run = ComponentRunModel(
                id=generate_id(f"{node_instance.id}:{component}:1"),
                action_id=action.id,
                node_instance_id=node_instance.id,
                component_id=component,
                attempt=1,
                timeout_seconds=(
                    node_definition.component_timeouts.get(
                        component, settings.COMPONENT_RUN_TIMEOUT_SECONDS
                    )
                    if node_definition.component_timeouts
                    else settings.COMPONENT_RUN_TIMEOUT_SECONDS
                ),
            )
            await component_run.insert()
            component_runs.append(component_run)

        return await ActionInstanceService._dispatch_component_runs(
            action,
            node_instance,
            node_definition,
            component_runs,
        )

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
            definition = await ActionInstanceService.get_node_definition(
                node_instance.definition_id
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
                    }
                }
            )
            if not claim or getattr(claim, "modified_count", 0) != 1:
                continue

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
                run.timeout_seconds > 0
                and run.started_at is not None
                and (now - run.started_at).total_seconds() >= run.timeout_seconds
            )
        ]
        expired = 0
        for component_run in stale_runs:
            accepted = await ActionInstanceService.finish_component_run(
                component_run.id,
                SDKResultRequest(
                    result_id=f"timeout:{component_run.id}:{component_run.attempt}",
                    attempt=component_run.attempt,
                    status="timed_out",
                    error="组件心跳租约或运行时限已过期",
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
                handle_definition = await ActionInstanceService.get_handle_definition_by_name(handle_name)
                if not handle_definition:
                    # logger.error(f"未找到连接点定义，Handle Name: {handle_name}")
                    continue
                
                if handle_definition.type == ActionConfigIOTypeEnum.REFERENCE:
                    continue
                
                node_instance.outputs[handle_definition.id] = ActionConfigIOModel(
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
            action.finished_nodes_instance.append(node_instance.id)
            node_instance.progress = 100.0
            await action.save()
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
            
            # 更新行动进度
            action = await ActionInstanceModel.find_one({"_id": node_instance.action_id})
            if action:
                action.progress = round(len(action.finished_nodes_instance) / len(action.nodes_id) * 100, 2) if len(action.nodes_id) > 0 else 0.0
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
            
        node_definition = await ActionInstanceService.get_node_definition(node_instance.definition_id)
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
            
            for source_handle_id, target_handle_id in edge_mappings:
                source_handle_definition = await ActionInstanceService.get_handle_definition(source_handle_id)
                if not source_handle_definition:
                    logger.error(f"未找到源连接点定义，Source Handle ID: {source_handle_id}")
                    continue
                
                target_handle_definition = await ActionInstanceService.get_handle_definition(target_handle_id)
                if not target_handle_definition:
                    logger.error(f"未找到目标连接点定义，Target Handle ID: {target_handle_id}")
                    continue
                
                if source_handle_definition.type == ActionConfigIOTypeEnum.REFERENCE:
                    if next_node_instance.node_id in node_instance.reference_queues:
                        queue_name = node_instance.reference_queues[next_node_instance.node_id]
                        next_node_instance.inputs[target_handle_id] = ActionConfigIOModel(
                            key=target_handle_definition.handle_name,
                            value=queue_name,
                            type=ActionConfigIOTypeEnum.REFERENCE
                        )
                        logger.info(f"传递队列 {queue_name} 给节点 {next_node_instance.node_id}")
                    else:
                        logger.error(f"未找到目标节点的队列映射，Target Node ID: {next_node_instance.node_id}")
                else:
                    if source_handle_id in node_instance.outputs:
                        source_output = node_instance.outputs[source_handle_id]
                        next_node_instance.inputs[target_handle_id] = ActionConfigIOModel(
                            key=target_handle_definition.handle_name,
                            value=source_output.value,
                            type=source_output.type
                        )
                    else:
                        logger.error(f"未找到源连接点的输出数据，Source Handle ID: {source_handle_id}")

            await ActionInstanceNodeModel.find_one(
                {"_id": next_node_instance.id}
            ).update({"$set": {"inputs": next_node_instance.inputs}})

            # 运行下一个节点
            if action.status == ActionFlowStatusEnum.RUNNING:
                await ActionInstanceService.run_node(next_node_instance.id, action.id)
        
        return True
    
    @staticmethod
    async def find_next_node(action_id: str, node_id: str):
        """
        查找下一个节点的实例ID列表以及对应的连接点映射
        返回结构：{目标节点实例ID: [(sourceHandle, targetHandle), ...]}
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
        for edge in blueprint.graph.edges:
            if edge.source == node_id:
                instance_id = generate_id(action_id + edge.target)
                edge_mapping = (edge.sourceHandle, edge.targetHandle)
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
        for edge in blueprint.graph.edges:
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
            for queue_name in node_instance.reference_queues.values():
                queue_names.add(queue_name)
        
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
        return all(cleanup_results)
    
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
                            / len(action.nodes_id)
                            * 100,
                            2,
                        )
                        if action.nodes_id
                        else 0.0
                    ),
                    "updated_at": now,
                }
            }
        )
        if not claim or getattr(claim, "modified_count", 0) != 1:
            return False
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
