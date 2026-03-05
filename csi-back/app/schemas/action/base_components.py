from datetime import datetime
from typing import Any
from pydantic import BaseModel, Field

from app.schemas.action.action import ActionConfigIO, ActionConfigMeta


class BaseComponentsConfigSchema(BaseModel):
    meta: ActionConfigMeta = Field(description="基础组件配置元数据")
    config: dict[str, Any] = Field(description="基础组件配置")
    inputs: dict[str, ActionConfigIO] = Field(default={}, description="节点输入配置")
    outputs: dict[str, ActionConfigIO] = Field(default={}, description="节点输出配置")


class BaseComponentsTaskConfigCreateRequest(BaseModel):
    name: str = Field(description="基础组件配置名称")
    description: str = Field(description="基础组件配置描述")
    type: str = Field(description="基础组件配置类型")
    version: str = Field(default="1.0.0", description="基础组件配置版本")
    config_data: BaseComponentsConfigSchema = Field(description="基础组件配置")


class BaseComponentsTaskConfigUpdateRequest(BaseModel):
    name: str | None = Field(default=None, description="基础组件配置名称")
    description: str | None = Field(default=None, description="基础组件配置描述")
    type: str | None = Field(default=None, description="基础组件配置类型")
    version: str | None = Field(default=None, description="基础组件配置版本")
    config_data: BaseComponentsConfigSchema | None = Field(default=None, description="基础组件配置")


class BaseComponentsTaskConfigResponse(BaseModel):
    id: str = Field(description="配置ID")
    node_instance_id: str = Field(description="节点实例ID")
    name: str = Field(description="基础组件配置名称")
    description: str = Field(description="基础组件配置描述")
    type: str = Field(description="基础组件配置类型")
    version: str = Field(description="基础组件配置版本")
    config_data: BaseComponentsConfigSchema = Field(description="基础组件配置")
    created_at: datetime = Field(description="创建时间")
    updated_at: datetime = Field(description="更新时间")
