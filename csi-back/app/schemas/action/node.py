from typing import Any, Literal
from datetime import datetime
from pydantic import BaseModel, Field

from app.schemas.constants import ActionNodeInputTypeEnum, ActionNodeTypeEnum


class ActionNodeOption(BaseModel):
    label: str = Field(description="选项显示文本")
    value: str = Field(description="选项值")


class ActionNodeHandle(BaseModel):
    id: str = Field(description="连接点ID")
    relabel: str | None = Field(default=None, description="连接点重命名标签")
    type: Literal["source", "target"] = Field(description="连接点类型")
    position: Literal["left", "right", "top", "bottom"] = Field(description="连接点位置")
    custom_style: dict[str, Any] | None = Field(default={}, description="自定义样式")

class ActionNodeHandleResponse(ActionNodeHandle):
    handle_name: str = Field(description="连接点名称")
    data_type: Literal["value", "reference"] = Field(description="接口类型")
    label: str = Field(description="默认连接点标签")
    color: str = Field(description="连接点颜色")
    other_compatible_interfaces: list[str] = Field(default=[], description="其他兼容接口id列表")

class ActionNodeInput(BaseModel):
    name: str = Field(description="输入项名称")
    type: ActionNodeInputTypeEnum = Field(description="输入项类型")
    position: Literal["left", "right", "top", "bottom", "center"] = Field(description="输入项位置")
    label: str = Field(description="输入项标签")
    description: str = Field(description="输入项描述")
    required: bool = Field(description="是否必填")
    default: Any = Field(description="默认值")
    options: list[ActionNodeOption] | None = Field(default=None, description="选项列表，仅select类型有效")
    custom_style: dict[str, Any] | None = Field(default=None, description="自定义样式")
    custom_props: dict[str, Any] | None = Field(default=None, description="自定义属性")

class ActionNodeInputResponse(ActionNodeInput):
    id: str = Field(description="输入项ID")

class ActionNode(BaseModel):
    name: str = Field(description="节点类型名称")
    description: str = Field(description="节点类型描述")
    type: ActionNodeTypeEnum = Field(description="节点类别")
    version: str = Field(description="节点版本")
    handles: list[ActionNodeHandle] = Field(description="连接点列表")
    inputs: list[ActionNodeInput] = Field(description="输入配置列表")
    default_configs: dict[str, Any] = Field(default={}, description="默认配置")
    related_components: list[str] = Field(description="相关组件列表")
    command: str = Field(description="执行命令")
    command_args: list[str] = Field(default=[], description="自定义执行命令参数")

class ActionNodeResponse(ActionNode):
    id: str = Field(description="节点类型ID")
    handles: list[ActionNodeHandleResponse] = Field(description="连接点列表")
    inputs: list[ActionNodeInputResponse] = Field(description="输入配置列表")

class BaseComponent(BaseModel):
    id: str = Field(description="基础组件ID")
    name: str = Field(description="基础组件名称")
    description: str = Field(description="基础组件描述")
    status: str = Field(description="基础组件最后一次运行状态")
    last_run_at: datetime | None = Field(default=None, description="基础组件最后一次运行时间")
    total_runs: int = Field(default=0, description="基础组件总运行次数")
    average_runtime: float = Field(default=0.0, description="基础组件平均运行时间(秒)")
