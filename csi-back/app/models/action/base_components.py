from datetime import datetime
from typing import Any
from beanie import Document
from pydantic import BaseModel, Field

from app.schemas.action.action import ActionConfigIO, ActionConfigMeta

class BaseComponentsConfigModel(BaseModel):
    meta: ActionConfigMeta = Field(description="基础组件配置元数据")
    config: dict[str, Any] = Field(description="基础组件配置")
    inputs: dict[str, ActionConfigIO] = Field(default={}, description="节点输入配置")
    outputs: dict[str, ActionConfigIO] = Field(default={}, description="节点输出配置")

class BaseComponentsTaskConfigModel(Document):
    id: str = Field(alias="_id")
    node_instance_id: str = Field(description="节点实例ID，用于检索基础组件任务配置")
    name: str = Field(description="基础组件配置名称")
    description: str = Field(description="基础组件配置描述")
    type: str = Field(description="【预留字段】基础组件配置类型")
    version: str = Field(default="1.0.0", description="基础组件配置版本")
    is_deleted: bool = Field(default=False, description="是否已删除")
    created_at: datetime = Field(default_factory=lambda: datetime.now())
    updated_at: datetime = Field(default_factory=lambda: datetime.now())
    config_data: BaseComponentsConfigModel = Field(description="基础组件配置")

    class Settings:
        name = "base_components_task_configs"
        indexes = [
            "id",
            "node_instance_id",
            "name",
        ]