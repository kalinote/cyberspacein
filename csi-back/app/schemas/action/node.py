from typing import Any, Literal
from datetime import datetime
from pydantic import BaseModel, Field, NonNegativeInt, model_validator

from app.schemas.action.execution import (
    NativeNodeExtensionSpec,
    NodeDefinitionContract,
    NodeExecutionSpec,
    default_component_execution,
    validate_component_command,
)
from app.schemas.constants import (
    DEFAULT_COMPONENT_COMMAND,
    DEFAULT_COMPONENT_COMMAND_ARGS,
    ActionNodeDefinitionOriginEnum,
    ActionNodeInputTypeEnum,
    ActionNodeKindEnum,
    ActionNodeTypeEnum,
)


class ActionNodeOption(BaseModel):
    label: str = Field(description="选项显示文本")
    value: str = Field(description="选项值")


class ActionNodeHandle(BaseModel):
    id: str = Field(description="连接点ID")
    port_id: str | None = Field(default=None, description="稳定端口ID")
    handle_config_id: str | None = Field(
        default=None,
        description="可复用Handle展示配置ID",
    )
    interface_type_id: str | None = Field(default=None, description="接口类型ID")
    compatible_interface_type_ids: list[str] = Field(
        default_factory=list,
        description="兼容的其他接口类型ID",
    )
    relabel: str | None = Field(default=None, description="连接点重命名标签")
    handle_name: str | None = Field(default=None, description="内联连接点名称")
    data_type: Literal["value", "reference"] | None = Field(
        default=None,
        description="内联数据传输类型",
    )
    accepted_data_types: list[Literal["value", "reference"]] = Field(
        default_factory=list,
        description="目标端口额外允许的数据传输类型",
    )
    label: str | None = Field(default=None, description="内联默认标签")
    color: str | None = Field(default=None, description="内联颜色")
    type: Literal["source", "target"] = Field(description="连接点类型")
    position: Literal["left", "right", "top", "bottom"] = Field(description="连接点位置")
    custom_style: dict[str, Any] | None = Field(
        default_factory=dict,
        description="自定义样式",
    )

class ActionNodeHandleResponse(ActionNodeHandle):
    handle_name: str = Field(description="连接点名称")
    data_type: Literal["value", "reference"] = Field(description="接口类型")
    label: str = Field(description="默认连接点标签")
    color: str = Field(description="连接点颜色")
    other_compatible_interfaces: list[str] = Field(
        default_factory=list,
        description="其他兼容接口id列表",
    )

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
    node_kind: ActionNodeKindEnum = Field(default=ActionNodeKindEnum.ORDINARY)
    category: str | None = None
    execution: NodeExecutionSpec = Field(default_factory=default_component_execution)
    extension: NativeNodeExtensionSpec | None = None
    definition_origin: ActionNodeDefinitionOriginEnum = (
        ActionNodeDefinitionOriginEnum.USER
    )
    builtin_key: str | None = None
    node_family_id: str | None = None
    definition_version: int = Field(default=1, ge=1)
    enabled: bool = True
    disabled_at: datetime | None = None
    disabled_by: str | None = None
    is_latest: bool = True
    source_blueprint_id: str | None = None
    source_revision_id: str | None = None
    version: str = Field(description="节点版本")
    handles: list[ActionNodeHandle] = Field(description="连接点列表")
    inputs: list[ActionNodeInput] = Field(description="输入配置列表")
    default_configs: dict[str, Any] = Field(
        default_factory=dict,
        description="默认配置",
    )
    related_components: list[str] = Field(description="相关组件列表")
    component_timeouts: dict[str, NonNegativeInt] = Field(
        default_factory=dict,
        description="组件超时秒数，key为组件ID，0表示不限制",
    )
    command: str = Field(default=DEFAULT_COMPONENT_COMMAND, description="执行命令")
    command_args: list[str] = Field(
        default_factory=lambda: list(DEFAULT_COMPONENT_COMMAND_ARGS),
        description="自定义执行命令参数",
    )

    @model_validator(mode="after")
    def apply_contract_defaults(self):
        """应用普通节点默认值并校验执行契约。"""
        self.command, self.command_args = validate_component_command(
            self.command,
            self.command_args,
        )
        if self.category is None:
            self.category = self.type.value
        NodeDefinitionContract(
            node_kind=self.node_kind,
            execution=self.execution,
            extension=self.extension,
        )
        return self


class ActionNodeResponse(ActionNode):
    id: str = Field(description="节点类型ID")
    handles: list[ActionNodeHandleResponse] = Field(description="连接点列表")
    inputs: list[ActionNodeInputResponse] = Field(description="输入配置列表")


class EncapsulatedNodeSourceBlueprintResponse(BaseModel):
    """封装节点源蓝图摘要。"""

    id: str
    name: str
    version: str
    is_deleted: bool = False


class EncapsulatedNodeReferenceResponse(BaseModel):
    """可编辑蓝图对封装节点版本的引用。"""

    blueprint_id: str
    blueprint_name: str
    blueprint_version: str
    instance_count: int = Field(ge=1)
    instance_ids: list[str] = Field(default_factory=list)


class EncapsulatedNodeVersionResponse(BaseModel):
    """封装节点版本列表项。"""

    id: str
    name: str
    description: str
    definition_version: int = Field(ge=1)
    source_revision_id: str
    is_latest: bool
    created_at: datetime
    draft_reference_count: int = Field(ge=0)


class EncapsulatedNodeFamilyResponse(BaseModel):
    """封装节点资源族及其有效版本。"""

    node_family_id: str
    name: str
    source_blueprint: EncapsulatedNodeSourceBlueprintResponse | None = None
    latest_node_id: str
    latest_definition_version: int = Field(ge=1)
    active_version_count: int = Field(ge=1)
    max_history_version: int = Field(ge=1)
    next_definition_version: int = Field(ge=2)
    latest_created_at: datetime
    versions: list[EncapsulatedNodeVersionResponse] = Field(default_factory=list)


class EncapsulatedNodeDetailResponse(BaseModel):
    """封装节点版本详情。"""

    node: ActionNodeResponse
    source_blueprint: EncapsulatedNodeSourceBlueprintResponse | None = None
    references: list[EncapsulatedNodeReferenceResponse] = Field(default_factory=list)


class EncapsulatedNodeDeleteResponse(BaseModel):
    """封装节点版本删除结果。"""

    deleted_node_id: str
    node_family_id: str
    promoted_latest_node_id: str | None = None
    promoted_latest_definition_version: int | None = None
    next_definition_version: int | None = Field(default=None, ge=2)
    family_deleted: bool = False


class EncapsulatedNodeDeleteConflictResponse(BaseModel):
    """封装节点删除引用冲突。"""

    references: list[EncapsulatedNodeReferenceResponse] = Field(default_factory=list)


class BaseComponent(BaseModel):
    id: str = Field(description="基础组件ID")
    name: str = Field(description="基础组件名称")
    description: str = Field(description="基础组件描述")
    status: str = Field(description="基础组件最后一次运行状态")
    last_run_at: datetime | None = Field(default=None, description="基础组件最后一次运行时间")
    total_runs: int = Field(default=0, description="基础组件总运行次数")
    average_runtime: float = Field(default=0.0, description="基础组件平均运行时间(秒)")
