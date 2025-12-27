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
    blueprint_id: str

    start_at: datetime | None = None
    finished_at: datetime | None = None
    status: ActionFlowStatusEnum = Field(default=ActionFlowStatusEnum.READY)

    finished_nodes_id: list[str] = Field(default_factory=list)

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
    
    class Settings:
        name = "action_instance_nodes"
        indexes = [
            "id"
            "action_id",
        ]
