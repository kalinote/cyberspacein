from typing import List, Optional, Any, Dict
from datetime import datetime, timezone
from beanie import Document
from pydantic import BaseModel, Field
from app.schemas.general import DictModel


class ActionNodeHandleModel(BaseModel):
    """
    行动节点连接点模型
    """
    id: str
    name: str
    type: str
    position: str
    socket_type: str
    allowed_socket_types: Optional[List[str]] = None
    label: str
    custom_style: Optional[List[DictModel]] = None


class ActionNodeInputModel(BaseModel):
    """
    行动节点输入项模型
    """
    id: str
    name: str
    type: str
    position: str
    label: str
    description: str
    required: bool
    default: Any
    options: Optional[List[Dict[str, str]]] = None
    custom_style: Optional[List[DictModel]] = None
    custom_props: Optional[List[DictModel]] = None


class ActionNodeModel(Document):
    """
    行动节点模型
    """
    id: str = Field(alias="_id")
    name: str
    description: str
    type: str
    version: str
    handles: List[ActionNodeHandleModel]
    inputs: List[ActionNodeInputModel]
    default_configs: Optional[List[DictModel]] = None
    related_components: List[str]
    
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    
    class Settings:
        name = "action_nodes"
        indexes = [
            "id"
            "name",
            "type",
            "version",
        ]

