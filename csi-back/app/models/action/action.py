from datetime import datetime
from beanie import Document
from pydantic import BaseModel, Field

from app.schemas.enum import ActionFlowStatusEnum, ActionInstanceNodeStatusEnum
from app.schemas.general import DictModel

class ActionInstanceModel(Document):
    """
    行动实例化流程模型
    """
    id: str = Field(alias="_id")
    blueprint_id: str = Field(description="蓝图ID")

    start_at: datetime | None = Field(default=None, description="行动实例化流程开始时间")
    finished_at: datetime | None = Field(default=None, description="行动实例化流程结束时间")
    status: ActionFlowStatusEnum = Field(default=ActionFlowStatusEnum.READY, description="行动实例化流程状态")

    nodes_id: list[str] = Field(default_factory=list, description="节点ID列表")
    finished_nodes_id: list[str] = Field(default_factory=list, description="已完成的节点ID列表")
    duration: int = Field(default=0, description="行动执行时长(秒)")
    
    progress: int = Field(default=0, description="行动实例化流程进度(%)")

    class Settings:
        name = "action_instances"
        indexes = [
            "id"
            "blueprint_id",
            "status",
        ]
        
class ActionInstanceNodeModel(Document):
    """
    行动实例节点信息模型
    
    TODO: 尚不完善
    """
    id: str = Field(alias="_id")
    action_id: str
    node_id: str
    status: ActionInstanceNodeStatusEnum
    
    start_at: datetime | None = Field(default=None, description="节点执行开始时间")
    finished_at: datetime | None = Field(default=None, description="节点执行结束时间")
    duration: int = Field(default=0, description="节点执行时长(秒)")
    
    progress: int = Field(default=0, description="节点执行进度(%)")
    
    class Settings:
        name = "action_instance_nodes"
        indexes = [
            "id"
            "action_id",
        ]
