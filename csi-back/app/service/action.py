
from datetime import datetime
import random
from typing import Any
from app.core.config import settings
from app.models.action.action import ActionInstanceModel, ActionInstanceNodeModel
import logging
from app.models.action.node import ActionNodeModel
from app.schemas.enum import ActionFlowStatusEnum, ActionInstanceNodeStatusEnum
from app.service.component import run_component
from app.utils.id_lib import generate_id
from app.utils.workflow import find_start_nodes
from app.models.action.blueprint import ActionBlueprintModel
from app.utils.async_fetch import async_post
from beanie.operators import In

logger = logging.getLogger(__name__)

class ActionInstanceService:
    def __init__(self, action_id: str | None = None, blueprint_id: str | None = None, new: bool = False):
        if new and blueprint_id:
            self.blueprint_id = blueprint_id
            self.action_id = generate_id(self.blueprint_id + datetime.now().strftime("%Y%m%d%H%M%S") + str(random.randint(1000, 9999)))
            self.is_initialized = False
        elif action_id:
            self.blueprint_id = blueprint_id
            self.action_id = action_id
            self.is_initialized = True
        else:
            logger.error(f"行动实例初始化失败，参数错误，新建实例必须提供蓝图id，已创建实例必须提供行动id")

    async def init(self):
        """
        初始化行动实例
        """
        if self.is_initialized:
            if not self.blueprint_id:
                action = await ActionInstanceModel.find_one({"_id": self.action_id})
                if not action:
                    logger.error(f"行动实例初始化失败，行动不存在: {self.action_id}")
                    return False
                self.blueprint_id = action.blueprint_id
            return True, f"行动实例已初始化，ID: {self.action_id}"
        blueprint = await ActionBlueprintModel.find_one({"_id": self.blueprint_id})
        if not blueprint:
            logger.error(f"行动实例初始化失败，蓝图不存在: {self.blueprint_id}")
            return False, f"行动实例初始化失败，蓝图不存在: {self.blueprint_id}"
        action_instance = ActionInstanceModel(
            id=self.action_id,
            blueprint_id=self.blueprint_id,
            status=ActionFlowStatusEnum.READY,
            nodes_id=[node.id for node in blueprint.graph.nodes]
        )
        await action_instance.insert()
        
        definition_ids = [node.data.definition_id for node in blueprint.graph.nodes]
        
        node_definitions = await ActionNodeModel.find(In(ActionNodeModel.id, definition_ids)).to_list()
        node_definition_map = {node.id: node for node in node_definitions}
        
        for node in blueprint.graph.nodes:
            default_configs = []
            node_definition = node_definition_map.get(node.data.definition_id)
            if node_definition:
                default_configs = node_definition.default_configs or []
                
            action_instance_node = ActionInstanceNodeModel(
                id=generate_id(self.action_id + node.id),
                action_id=self.action_id,
                node_id=node.id,
                status=ActionInstanceNodeStatusEnum.UNREADY,
                configs=(node.data.form_data or []) + default_configs,
                definition_id=node.data.definition_id
            )
            await action_instance_node.insert()
        
        start_nodes = find_start_nodes(blueprint)
        if not start_nodes:
            logger.warning(f"没有找到起始节点: {self.action_id}")
        
        for node in start_nodes:
            await self.set_node_status(node.id, ActionInstanceNodeStatusEnum.READY)
        
        self.is_initialized = True
        return True, f"行动实例初始化成功，ID: {self.action_id}"

    async def start(self):
        """
        开始某个行动
        """
        if not self.is_initialized:
            logger.error(f"行动实例未初始化，ID: {self.action_id}")
            return False
        
        action = await ActionInstanceModel.find_one({"_id": self.action_id})
        if not action:
            logger.error(f"行动启动失败，ID不存在: {self.action_id}")
            return
        action.status = ActionFlowStatusEnum.RUNNING
        action.start_at = datetime.now()
        await action.save()

        ready_nodes = await ActionInstanceNodeModel.find({"action_id": action.id, "status": ActionInstanceNodeStatusEnum.READY}).to_list()
        for node in ready_nodes:
            await self.run_node(node.id)

    async def run_node(self, node_instance_id):
        """
        运行指定行动的指定节点
        
        TODO: 检查前置节点是否运行完成，如果未完成则设置状态为unready
        """
        logger.info(f"运行节点: {node_instance_id}")
        node_instance = await ActionInstanceNodeModel.find_one({"_id": node_instance_id})
        if not node_instance:
            logger.error(f"未找到节点，Action ID: {self.action_id}，Node Instance ID: {node_instance_id}")
            return False
        
        node_instance.status = ActionInstanceNodeStatusEnum.RUNNING
        node_instance.start_at = datetime.now()
        await node_instance.save()
        
        node_definition = await ActionNodeModel.find_one({"_id": node_instance.definition_id})
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

    async def finish_node(self, node_instance_id, outputs: dict[str, Any]):
        """
        TODO: 完成指定行动的指定节点，并检查和准备运行下一个节点
        """

    async def set_node_status(self, node_id, status: ActionInstanceNodeStatusEnum):
        node_instance = await ActionInstanceNodeModel.find_one({"node_id": node_id, "action_id": self.action_id})
        if not node_instance:
            logger.error(f"未找到节点，Action ID: {self.action_id}，Node ID: {node_id}")
            return False
        
        node_instance.status = status
        await node_instance.save()
        return True
