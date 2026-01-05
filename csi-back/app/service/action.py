
from datetime import datetime
import random
from typing import Any
from app.core.config import settings
from app.models.action.action import ActionConfigIOModel, ActionInstanceModel, ActionInstanceNodeModel
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
from app.db.rabbitmq import delete_queue

logger = logging.getLogger(__name__)

class ActionInstanceService:
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
        
        # 检查前置节点是否全部完成
        all_previous_nodes = await ActionInstanceService.find_all_previous_nodes(action_id, node_instance.node_id)
        previous_node_instances = await ActionInstanceNodeModel.find(In(ActionInstanceNodeModel.node_id, all_previous_nodes)).to_list()
        for prev_node in previous_node_instances:
            if prev_node.status != ActionInstanceNodeStatusEnum.COMPLETED:
                logger.info(f"前置节点未完成({prev_node.node_id})，等待中，当前节点: {node_instance.id}，前置节点: {prev_node.id}")
                node_instance.status = ActionInstanceNodeStatusEnum.UNREADY
                await node_instance.save()
                return False
        
        # 所有前置节点检查通过，设置为运行状态
        node_instance.status = ActionInstanceNodeStatusEnum.RUNNING
        node_instance.start_at = datetime.now()
        await node_instance.save()
            
        action = await ActionInstanceModel.find_one({"_id": action_id})
        if not action:
            logger.error(f"未找到行动，Action ID: {action_id}")
            return False
        blueprint = await ActionInstanceService.get_blueprint(action.blueprint_id)
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
                    # 生成队列名
                    queue_name = generate_id(action_id + edge.target + datetime.now().strftime("%Y%m%d%H%M%S") + str(random.randint(1000, 9999)))
                    node_instance.outputs[edge.sourceHandle] = ActionConfigIOModel(
                        key=handle_definition.handle_name, 
                        value=queue_name,
                        type=handle_definition.type
                    )
                    await node_instance.save()
        
        # 这里是开始运行，在此之前应该做好全部准备工作
        command = node_definition.command
        command_args = ["--api-base-url", settings.api_base_url, "--action-node-id", node_instance.id] + node_definition.command_args
        related_components = node_definition.related_components
        
        for component in related_components:
            result = await run_component(component, command, command_args)
            if not result:
                logger.error(f"运行组件失败，调度平台无结果返回，Component ID: {component}")
                node_instance.status = ActionInstanceNodeStatusEnum.FAILED
                node_instance.error_message = f"运行组件失败，调度平台无结果返回"
                node_instance.finished_at = datetime.now()
                node_instance.duration = (datetime.now() - node_instance.start_at).total_seconds()
                await node_instance.save()
                return False

        return True

    @staticmethod
    async def finish_node(node_instance_id: str, result: SDKResultRequest):
        node_instance = await ActionInstanceNodeModel.find_one({"_id": node_instance_id})
        if not node_instance:
            logger.error(f"上报节点实例不存在，ID: {node_instance_id}")
            return False
        
        if result.status == "success":
            node_instance.status = ActionInstanceNodeStatusEnum.COMPLETED
            node_instance.progress = 100
            node_instance.finished_at = datetime.now()
            node_instance.duration = (datetime.now() - node_instance.start_at).total_seconds()
            for handle_name, value in result.outputs.items():
                handle_definition = await ActionInstanceService.get_handle_definition_by_name(handle_name)
                if not handle_definition:
                    # logger.error(f"未找到连接点定义，Handle Name: {handle_name}")
                    continue
                node_instance.outputs[handle_definition.id] = ActionConfigIOModel(
                    key=handle_name, 
                    value=value,
                    type=handle_definition.type
                )
                
            await node_instance.save()
            
            for input_handle_id, input_data in node_instance.inputs.items():
                if input_data.type == ActionConfigIOTypeEnum.REFERENCE:
                    try:
                        await delete_queue(input_data.value)
                    except Exception as e:
                        logger.error(f"清理inputs队列失败，节点实例ID: {node_instance_id}, 队列名: {input_data.value}, 错误: {str(e)}")
            
            action = await ActionInstanceModel.find_one({"_id": node_instance.action_id})
            action.finished_nodes_instance.append(node_instance.id)
            action.progress = int(len(action.finished_nodes_instance) / len(action.nodes_id)) * 100
            await action.save()
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
            
        node_definition = await ActionInstanceService.get_node_definition(node_instance.definition_id)
        if not node_definition:
            logger.error(f"未找到节点定义，Node Instance ID: {node_instance.id}")
            return False
        
        next_nodes = await ActionInstanceService.find_next_node(action.id, node_instance.node_id)
        if not next_nodes:
            # TODO: 蓝图错误或行动完成，后续添加检查是否所有节点已完成
            if await ActionInstanceService.check_action_finished(action.id):
                await ActionInstanceService.finish_action(action.id)
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
                if source_handle_id not in node_instance.outputs:
                    logger.error(f"未找到源连接点的输出数据，Source Handle ID: {source_handle_id}")
                    continue
                
                source_output = node_instance.outputs[source_handle_id]
                
                target_handle_definition = await ActionInstanceService.get_handle_definition(target_handle_id)
                if not target_handle_definition:
                    logger.error(f"未找到目标连接点定义，Target Handle ID: {target_handle_id}")
                    continue
                
                next_node_instance.inputs[target_handle_id] = ActionConfigIOModel(
                    key=target_handle_definition.handle_name,
                    value=source_output.value,
                    type=source_output.type
                )

            await next_node_instance.save()
            
            # 运行下一个节点
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
        
        blueprint = await ActionInstanceService.get_blueprint(action.blueprint_id)
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
        
        blueprint = await ActionInstanceService.get_blueprint(action.blueprint_id)
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
    async def finish_action(action_id: str):
        """
        完成行动
        """
        action = await ActionInstanceModel.find_one({"_id": action_id})
        if not action:
            logger.error(f"未找到行动，Action ID: {action_id}")
            return False
        action.status = ActionFlowStatusEnum.COMPLETED
        action.finished_at = datetime.now()
        action.duration = (datetime.now() - action.start_at).total_seconds()
        await action.save()
        return True
    
    @staticmethod
    async def fail_action(action_id: str, error_message: str):
        """
        失败行动
        """
        action = await ActionInstanceModel.find_one({"_id": action_id})
        if not action:
            logger.error(f"未找到行动，Action ID: {action_id}")
            return False
        action.status = ActionFlowStatusEnum.FAILED
        action.error_message = error_message
        action.finished_at = datetime.now()
        action.duration = (datetime.now() - action.start_at).total_seconds()
        await action.save()
        return True

    @staticmethod
    async def check_action_finished(action_id: str):
        """
        判断行动是否所有节点全部完成
        
        TODO: 暂时直接判断节点列表和已完成节点列表是否数量一致，后续考虑引入封装、分支和循环时的判断方法
        """
        
        action = await ActionInstanceModel.find_one({"_id": action_id})
        if not action:
            logger.error(f"未找到行动，Action ID: {action_id}")
            return False
        
        blueprint = await ActionInstanceService.get_blueprint(action.blueprint_id)
        if not blueprint:
            logger.error(f"未找到蓝图，Blueprint ID: {action.blueprint_id}")
            return False
        
        return len(action.finished_nodes_instance) == len(blueprint.graph.nodes)
    
    @staticmethod
    async def update_progress(node_instance_id: str, progress: float):
        """
        更新节点运行进度
        """
        if progress > 100:
            progress = 100
        if progress < 0:
            progress = 0
        
        node_instance = await ActionInstanceNodeModel.find_one({"_id": node_instance_id})
        if not node_instance:
            logger.error(f"未找到节点实例，Node Instance ID: {node_instance_id}")
            return False
        
        node_instance.progress = progress
        await node_instance.save()
        return True
    