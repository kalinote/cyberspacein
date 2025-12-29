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
    name: str = Field(description="节点名称")
    description: str = Field(description="节点描述")
    type: str = Field(description="节点类型")
    version: str = Field(description="节点版本")
    handles: list[ActionNodeHandleModel] = Field(description="节点连接点")
    inputs: list[ActionNodeInputModel] = Field(description="节点输入项")
    default_configs: list[DictModel] | None = Field(default=None, description="默认配置")
    related_components: list[str] = Field(description="关联组件")
    command: str = Field(description="执行命令")
    command_args: list[str] = Field(description="执行命令参数")
    is_deleted: bool = Field(default=False, description="是否已删除")
    
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

