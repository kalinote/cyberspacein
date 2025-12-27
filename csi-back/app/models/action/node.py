from typing import Any
from datetime import datetime
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
    allowed_socket_types: list[str] | None = None
    label: str
    custom_style: list[DictModel] | None = None


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
    options: list[dict[str, str]] | None = None
    custom_style: list[DictModel] | None = None
    custom_props: list[DictModel] | None = None


class ActionNodeModel(Document):
    """
    行动节点模型
    """
    id: str = Field(alias="_id")
    name: str
    description: str
    type: str
    version: str
    handles: list[ActionNodeHandleModel]
    inputs: list[ActionNodeInputModel]
    default_configs: list[DictModel] | None = None
    related_components: list[str]
    command: str
    command_args: list[str]
    
    created_at: datetime = Field(default_factory=lambda: datetime.now())
    updated_at: datetime = Field(default_factory=lambda: datetime.now())
    
    class Settings:
        name = "action_nodes"
        indexes = [
            "id"
            "name",
            "type",
            "version",
        ]

