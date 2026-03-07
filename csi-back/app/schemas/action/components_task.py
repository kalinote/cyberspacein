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

class BaseComponentsTaskResponse(BaseModel):
    id: str = Field(description="任务ID")
    base_components_id: str = Field(description="基础组件ID")
    status: str = Field(description="任务状态")
    created_at: datetime | None = Field(default=None, description="创建时间")
    start_at: datetime | None = Field(default=None, description="开始时间")
    end_at: datetime | None = Field(default=None, description="结束时间")
    config_id: str = Field(description="配置ID")
    error_message: str | None = Field(default=None, description="错误信息")
    schedule_id: str | None = Field(default=None, description="调度计划ID")
    priority: int | None = Field(default=None, description="优先级")
    total_duration: int | None = Field(default=0, description="总运行时长(毫秒)")
    