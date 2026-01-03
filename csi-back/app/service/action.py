
from datetime import datetime
import random
from typing import Any
from app.core.config import settings
from app.models.action.action import ActionInstanceModel, ActionInstanceNodeModel
import logging
from app.models.action.configs import ActionNodesHandleConfigModel
from app.models.action.node import ActionNodeModel
from app.schemas.action.sdk import SDKResultRequest
from app.schemas.enum import ActionConfigIOTypeEnum, ActionFlowStatusEnum, ActionInstanceNodeStatusEnum
from app.schemas.general import DictModel
from app.service.component import run_component
from app.utils.dict_helper import pack_dict
from app.utils.id_lib import generate_id
from app.utils.workflow import find_start_nodes
from app.models.action.blueprint import ActionBlueprintModel
from app.utils.async_fetch import async_post
from beanie.operators import In

logger = logging.getLogger(__name__)

class ActionInstanceService:
    # TODO: 缓存节点定义和蓝图，使用缓存避免重复查询数据库
    # TODO: 后续换成redis缓存，设置10分钟过期时间，同时在数据库更新时清理缓存
    blueprints: dict[str, ActionBlueprintModel] = {}
    node_definitions: dict[str, ActionNodeModel] = {}
    handle_definitions: dict[str, ActionNodesHandleConfigModel] = {}
    handle_name_to_id: dict[str, str] = {}
    

    @staticmethod
    async def get_blueprint(blueprint_id: str) -> ActionBlueprintModel:
        if blueprint_id not in ActionInstanceService.blueprints:
            ActionInstanceService.blueprints[blueprint_id] = await ActionBlueprintModel.find_one({"_id": blueprint_id})
        return ActionInstanceService.blueprints[blueprint_id]
    
    @staticmethod
    async def get_node_definition(node_definition_id: str) -> ActionNodeModel:
        if node_definition_id not in ActionInstanceService.node_definitions:
            ActionInstanceService.node_definitions[node_definition_id] = await ActionNodeModel.find_one({"_id": node_definition_id})
        return ActionInstanceService.node_definitions[node_definition_id]

    @staticmethod
    async def get_handle_definition(handle_definition_id: str) -> ActionNodesHandleConfigModel:
        if handle_definition_id not in ActionInstanceService.handle_definitions:
            ActionInstanceService.handle_definitions[handle_definition_id] = await ActionNodesHandleConfigModel.find_one({"_id": handle_definition_id})
        
        return ActionInstanceService.handle_definitions[handle_definition_id]

    @staticmethod
    async def get_handle_definition_by_name(handle_name: str) -> ActionNodesHandleConfigModel:
        if handle_name in ActionInstanceService.handle_name_to_id:
            handle_id = ActionInstanceService.handle_name_to_id[handle_name]
            return await ActionInstanceService.get_handle_definition(handle_id)
        
        handle = await ActionNodesHandleConfigModel.find_one({"handle_name": handle_name})
        if handle:
            ActionInstanceService.handle_name_to_id[handle_name] = handle.id
            ActionInstanceService.handle_definitions[handle.id] = handle
        
        return handle


    
    @staticmethod
    async def init(blueprint_id: str) -> tuple[bool, str]:
        """
        初始化行动实例
        
        return: tuple[bool, str] - 返回初始化是否成功和行动实例ID
        """
        action_id = generate_id(blueprint_id + datetime.now().strftime("%Y%m%d%H%M%S") + str(random.randint(1000, 9999)))
        
        blueprint = await ActionInstanceService.get_blueprint(blueprint_id)
        if not blueprint:
            logger.error(f"行动实例初始化失败，蓝图不存在: {blueprint_id}")
            return False, f"行动实例初始化失败，蓝图不存在: {blueprint_id}"
        action_instance = ActionInstanceModel(
            id=action_id,
            blueprint_id=blueprint_id,
            status=ActionFlowStatusEnum.READY,
            nodes_id=[node.id for node in blueprint.graph.nodes]
        )
        await action_instance.insert()
        
        for node in blueprint.graph.nodes:
            default_configs = []
            node_definition = await ActionInstanceService.get_node_definition(node.data.definition_id)
            if node_definition:
                default_configs = node_definition.default_configs or []
                
            action_instance_node = ActionInstanceNodeModel(
                id=generate_id(action_id + node.id),
                action_id=action_id,
                node_id=node.id,
                status=ActionInstanceNodeStatusEnum.PENDING,
                configs=(node.data.form_data or []) + default_configs,
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
        action = await ActionInstanceModel.find_one({"_id": action_id})
        if not action:
            logger.error(f"行动启动失败，ID不存在: {action_id}")
            return
        action.status = ActionFlowStatusEnum.RUNNING
        action.start_at = datetime.now()
        await action.save()

        ready_nodes = await ActionInstanceNodeModel.find({"action_id": action.id, "status": ActionInstanceNodeStatusEnum.READY}).to_list()
        for node in ready_nodes:
            await ActionInstanceService.run_node(node.id, action_id)


    @staticmethod
    async def run_node(node_instance_id: str, action_id: str):
        """
        运行指定行动的指定节点
        
        TODO: 检查前置节点是否运行完成，如果未完成则设置状态为unready
        """
        logger.info(f"运行节点: {node_instance_id}")
        node_instance = await ActionInstanceNodeModel.find_one({"_id": node_instance_id})
        if not node_instance:
            logger.error(f"未找到节点，Action ID: {action_id}，Node Instance ID: {node_instance_id}")
            return False
        
        node_instance.status = ActionInstanceNodeStatusEnum.RUNNING
        node_instance.start_at = datetime.now()
        await node_instance.save()
        
        node_definition = await ActionInstanceService.get_node_definition(node_instance.definition_id)
        if not node_definition:
            logger.error(f"未找到节点定义，Node Instance ID: {node_instance_id}")
            return False
        
        command = node_definition.command
        command_args = ["--api-base-url", settings.api_base_url, "--action-node-id", node_instance.id] + node_definition.command_args
        related_components = node_definition.related_components
        
        for component in related_components:
            result = await run_component(component, command, command_args)
            if not result:
                logger.error(f"运行组件失败，Component ID: {component}")
                # TODO: 做运行失败的处理

        return True

    @staticmethod
    async def finish_node(node_instance_id: str, result: SDKResultRequest):
        """
        TODO: 完成指定行动的指定节点，并检查和准备运行下一个节点
        """
        node_instance = await ActionInstanceNodeModel.find_one({"_id": node_instance_id})
        if not node_instance:
            logger.error(f"上报节点实例不存在，ID: {node_instance_id}")
            return False
        
        if result.status == "success":
            node_instance.status = ActionInstanceNodeStatusEnum.COMPLETED
            node_instance.finished_at = datetime.now()
            node_instance.duration = (datetime.now() - node_instance.start_at).total_seconds()
            for handle_name, value in result.outputs.items():
                handle_definition = await ActionInstanceService.get_handle_definition_by_name(handle_name)
                if not handle_definition:
                    logger.error(f"未找到连接点定义，Handle Name: {handle_name}")
                    continue
                node_instance.outputs[handle_definition.id] = DictModel(key=handle_name, value=value)
            await node_instance.save()
        elif result.status == "failed":
            node_instance.status = ActionInstanceNodeStatusEnum.FAILED
            node_instance.error_message = result.error
            node_instance.finished_at = datetime.now()
            node_instance.duration = (datetime.now() - node_instance.start_at).total_seconds()
            await node_instance.save()
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
            
        # TODO: 设置下游节点的inputs，需要合并已存在的(其他节点设置的)inputs
        # TODO: 需要判断该节点的结果是值还是引用
        node_definition = await ActionInstanceService.get_node_definition(node_instance.definition_id)
        if not node_definition:
            logger.error(f"未找到节点定义，Node Instance ID: {node_instance.id}")
            return False
        
        next_nodes = await ActionInstanceService.find_next_node(action.id, node_instance.node_id)
        if not next_nodes:
            logger.error(f"未找到下一个节点，Action ID: {action.id}，Node ID: {node_instance.node_id}，行动中断")
            return False
        
        # 1. 搬运数据 2. 检查下一个节点是否全部就绪
        for target_node_id, handle_ids in next_nodes.items():
            next_node_instance = await ActionInstanceNodeModel.find_one({"_id": target_node_id})
            if not next_node_instance:
                logger.error(f"未找到下一个节点实例，Node Instance ID: {target_node_id}")
                continue
            
            for handle_id in handle_ids:
                handle_definition = await ActionInstanceService.get_handle_definition(handle_id)
                if not handle_definition:
                    logger.error(f"未找到连接点定义，Handle ID: {handle_id}")
                    continue
                
                if handle_definition.type == ActionConfigIOTypeEnum.VALUE:
                    pass
                elif handle_definition.type == ActionConfigIOTypeEnum.REFERENCE:
                    pass
            await next_node_instance.save()
        
        return True
    
    @staticmethod
    async def check_node_instance_dependencies(node_instance_id: str):
        """
        检查所有前置节点是否全部完成
        """
    
    @staticmethod
    async def find_next_node(action_id: str, node_id: str):
        """
        查找下一个节点的实例ID列表以及对应的连接点ID列表
        """
        action = await ActionInstanceModel.find_one({"_id": action_id})
        if not action:
            logger.error(f"未找到行动，Action ID: {action_id}")
            return False
        
        blueprint = await ActionInstanceService.get_blueprint(action.blueprint_id)
        if not blueprint:
            logger.error(f"未找到蓝图，Blueprint ID: {action.blueprint_id}")
            return False
        
        # 键是目标节点ID，值是连接点ID列表
        next_nodes = {}
        for edge in blueprint.graph.edges:
            if edge.source == node_id:
                instance_id = generate_id(action_id + edge.target)
                next_nodes[instance_id] = next_nodes.get(edge.target, []) + [edge.targetHandle]
        
        return next_nodes

    @staticmethod
    async def set_node_status(node_id: str, action_id: str, status: ActionInstanceNodeStatusEnum):
        node_instance = await ActionInstanceNodeModel.find_one({"node_id": node_id, "action_id": action_id})
        if not node_instance:
            logger.error(f"未找到节点，Action ID: {action_id}，Node ID: {node_id}")
            return False
        
        node_instance.status = status
        await node_instance.save()
        return True
