from typing import Any, Dict, List, Optional, Literal
from datetime import datetime
from pydantic import BaseModel, Field

from app.schemas.enum import ActionNodeTypeEnum


class ActionNodeOption(BaseModel):
    label: str = Field(description="选项显示文本")
    value: str = Field(description="选项值")


class ActionNodeHandle(BaseModel):
    # TODO: 改成id和relabel
    id: str = Field(description="连接点ID")
    name: str = Field(description="连接点名称")
    type: Literal["source", "target"] = Field(description="连接点类型")
    position: Literal["left", "right", "top", "bottom"] = Field(description="连接点位置")
    socket_type: str = Field(description="接口类型")
    allowed_socket_types: Optional[List[str]] = Field(default=None, description="允许的接口类型列表，仅target类型有效")
    label: str = Field(description="连接点标签")
    custom_style: Optional[Dict[str, Any]] = Field(default=None, description="自定义样式")

class ActionNodeHandleResponse(ActionNodeHandle):
    id: str = Field(description="连接点ID")

class ActionNodeInput(BaseModel):
    name: str = Field(description="输入项名称")
    type: Literal['int', 'string', 'textarea', 'select', 'checkbox', 'checkbox-group', 'radio-group', 'boolean', 'datetime', 'tags', 'conditions'] = Field(description="输入项类型")
    position: Literal["left", "right", "top", "bottom", "center"] = Field(description="输入项位置")
    label: str = Field(description="输入项标签")
    description: str = Field(description="输入项描述")
    required: bool = Field(description="是否必填")
    default: Any = Field(description="默认值")
    options: Optional[List[ActionNodeOption]] = Field(default=None, description="选项列表，仅select类型有效")
    custom_style: Optional[Dict[str, Any]] = Field(default=None, description="自定义样式")
    custom_props: Optional[Dict[str, Any]] = Field(default=None, description="自定义属性")

class ActionNodeInputResponse(ActionNodeInput):
    id: str = Field(description="输入项ID")

class ActionNode(BaseModel):
    name: str = Field(description="节点类型名称")
    description: str = Field(description="节点类型描述")
    type: ActionNodeTypeEnum = Field(description="节点类别")
    version: str = Field(description="节点版本")
    handles: List[ActionNodeHandle] = Field(description="连接点列表")
    inputs: List[ActionNodeInput] = Field(description="输入配置列表")
    default_configs: Dict[str, Any] = Field(default={}, description="默认配置")
    related_components: List[str] = Field(description="相关组件列表")
    command: str = Field(description="执行命令")
    command_args: List[str] = Field(default=[], description="自定义执行命令参数")

class ActionNodeResponse(ActionNode):
    id: str = Field(description="节点类型ID")
    handles: List[ActionNodeHandleResponse] = Field(description="连接点列表")
    inputs: List[ActionNodeInputResponse] = Field(description="输入配置列表")

class BaseComponent(BaseModel):
    id: str = Field(description="基础组件ID")
    name: str = Field(description="基础组件名称")
    description: str = Field(description="基础组件描述")
    status: str = Field(description="基础组件最后一次运行状态")
    last_run_at: Optional[datetime] = Field(default=None, description="基础组件最后一次运行时间")
    total_runs: int = Field(default=0, description="基础组件总运行次数")
    average_runtime: float = Field(default=0.0, description="基础组件平均运行时间(秒)")
