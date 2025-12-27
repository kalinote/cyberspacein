
from datetime import datetime
import random
from app.models.action.action import ActionInstanceModel, ActionInstanceNodeModel
import logging
from app.schemas.enum import ActionFlowStatusEnum, ActionInstanceNodeStatusEnum
from app.utils.dict_helper import pack_dict, unpack_dict
from app.utils.id_lib import generate_id
from app.utils.workflow import find_start_nodes
from app.models.action.blueprint import ActionBlueprintModel

logger = logging.getLogger(__name__)

class ActionInstanceManager:
    def __init__(self):
        self.action_instances: dict[str, ActionInstance] = {}
        
    def new(self, blueprint_id: str):
        """
        创建新的行动实例
        """
        self.action_instances[blueprint_id] = ActionInstance(blueprint_id)
        return self.action_instances[blueprint_id]

class ActionInstance:
    def __init__(self, blueprint_id: str):
        self.blueprint_id = blueprint_id
        self.action_id = generate_id(self.blueprint_id + datetime.now().strftime("%Y%m%d%H%M%S") + str(random.randint(1000, 9999)))
        self.is_init = False

    async def init(self):
        """
        初始化行动实例
        """
        if self.is_init:
            return True, f"行动实例已初始化，ID: {self.action_id}"
        blueprint = await ActionBlueprintModel.find_one({"_id": self.blueprint_id})
        if not blueprint:
            logger.error(f"行动实例初始化失败，蓝图不存在: {self.blueprint_id}")
            return False, f"行动实例初始化失败，蓝图不存在: {self.blueprint_id}"
        action_instance = ActionInstanceModel(
            id=self.action_id,
            blueprint_id=self.blueprint_id,
            status=ActionFlowStatusEnum.READY
        )
        await action_instance.insert()
        for node in blueprint.graph.nodes:
            action_instance_node = ActionInstanceNodeModel(
                id=generate_id(self.action_id + node.id),
                action_id=self.action_id,
                node_id=node.id,
                status=ActionInstanceNodeStatusEnum.UNREADY
            )
            await action_instance_node.insert()
        
        self.is_init = True
        return True, f"行动实例初始化成功，ID: {self.action_id}"

    async def start(self):
        """
        开始某个行动
        """
        if not self.is_init:
            logger.error(f"行动实例未初始化，ID: {self.action_id}")
            return False
        
        action = await ActionInstanceModel.find_one({"_id": self.action_id})
        if not action:
            logger.error(f"行动启动失败，ID不存在: {self.action_id}")
            return
        
        blueprint = await ActionBlueprintModel.find_one({"_id": action.blueprint_id})
        start_nodes = find_start_nodes(blueprint)
        if not start_nodes:
            logger.error(f"行动启动失败，没有找到起始节点: {self.action_id}")
            return
        
        for node in start_nodes:
            await self.set_node_status(node.id, ActionInstanceNodeStatusEnum.READY)

    async def run_node(self, node_id):
        """
        运行指定行动的指定节点
        """

    async def set_node_status(self, node_id, status: ActionInstanceNodeStatusEnum):
        node_instance = await ActionInstanceNodeModel.find_one({"node_id": node_id, "action_id": self.action_id})
        if not node_instance:
            logger.error(f"未找到节点，Action ID: {self.action_id}，Node ID: {node_id}")
            return False
        
        node_instance.status = status
        await node_instance.save()
        return True

action_instance_manager = ActionInstanceManager()
