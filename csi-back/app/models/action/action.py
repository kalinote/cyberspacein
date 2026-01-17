from datetime import datetime
from typing import Any
from beanie import Document
from pydantic import BaseModel, Field

from app.schemas.enum import ActionConfigIOTypeEnum, ActionFlowStatusEnum, ActionInstanceNodeStatusEnum
from app.schemas.general import DictModelSchema

class ActionInstanceModel(Document):
    """
    行动实例化流程模型
    """
    id: str = Field(alias="_id")
    blueprint_id: str = Field(description="蓝图ID")
    is_deleted: bool = Field(default=False, description="是否已删除")

    start_at: datetime | None = Field(default=None, description="行动实例化流程开始时间")
    finished_at: datetime | None = Field(default=None, description="行动实例化流程结束时间")
    status: ActionFlowStatusEnum = Field(default=ActionFlowStatusEnum.READY, description="行动实例化流程状态")

    nodes_id: list[str] = Field(default_factory=list, description="节点ID列表，这是节点id")
    finished_nodes_instance: list[str] = Field(default_factory=list, description="已完成的节点ID列表，这是节点实例id")
    duration: float = Field(default=0, description="行动执行时长(秒)")
    
    progress: float = Field(default=0, description="行动实例化流程进度(%)")

    class Settings:
        name = "action_instances"
        indexes = [
            "id"
            "blueprint_id",
            "status",
        ]

class ActionConfigIOModel(BaseModel):
    type: ActionConfigIOTypeEnum = Field(description="数据类型")
    key: str = Field(description="接口名")
    value: Any = Field(description="数据值")
        
class ActionInstanceNodeModel(Document):
    """
    行动实例节点信息模型
    
    TODO: 尚不完善
    """
    id: str = Field(alias="_id")
    action_id: str = Field(description="行动ID")
    node_id: str = Field(description="节点ID")
    definition_id: str = Field(description="行动节点定义ID")
    status: ActionInstanceNodeStatusEnum = Field(default=ActionInstanceNodeStatusEnum.UNKNOWN, description="节点状态")
    error_message: str | None = Field(default=None, description="节点执行错误信息")
    
    start_at: datetime | None = Field(default=None, description="节点执行开始时间")
    finished_at: datetime | None = Field(default=None, description="节点执行结束时间")
    duration: float = Field(default=0, description="节点执行时长(秒)")
    
    progress: float = Field(default=0, description="节点执行进度(%)")
    configs: list[DictModelSchema] = Field(default_factory=list, description="节点配置")
    inputs: dict[str, ActionConfigIOModel] = Field(default_factory=dict, description="节点输入配置，key是handle_id，value是数据")
    outputs: dict[str, ActionConfigIOModel] = Field(default_factory=dict, description="节点输出配置，key是handle_id，value是数据")
    reference_queues: dict[str, str] = Field(default_factory=dict, description="REFERENCE类型的边到队列的映射，key是target_node_id，value是队列名")
    
    class Settings:
        name = "action_instance_nodes"
        indexes = [
            "id"
            "action_id",
        ]
        