from datetime import datetime
from typing import Any, Literal

from beanie import Document
from pydantic import BaseModel, Field, model_validator

from app.schemas.action.execution import (
    NativeNodeExtensionSpec,
    NodeDefinitionContract,
    NodeExecutionSpec,
    validate_component_command,
)
from app.schemas.constants import (
    DEFAULT_COMPONENT_COMMAND,
    DEFAULT_COMPONENT_COMMAND_ARGS,
    ActionNodeDefinitionOriginEnum,
    ActionNodeKindEnum,
)
from app.schemas.general import DictModelSchema


class ActionNodeHandleModel(BaseModel):
    """行动节点连接点模型。"""

    id: str = Field(description="连接点ID")
    port_id: str | None = Field(default=None, description="节点定义内的稳定端口ID")
    handle_config_id: str | None = Field(
        default=None,
        description="可复用Handle展示配置ID",
    )
    interface_type_id: str | None = Field(default=None, description="端口接口类型ID")
    compatible_interface_type_ids: list[str] = Field(
        default_factory=list,
        description="该端口允许连接的其他接口类型ID",
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
    custom_style: list[DictModelSchema] | None = Field(
        default_factory=list,
        description="自定义样式",
    )


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
    options: list[dict[str, str]] | None = Field(
        default_factory=list,
        description="选项列表，仅select类型有效",
    )
    custom_style: list[DictModelSchema] | None = Field(
        default_factory=list,
        description="自定义样式",
    )
    custom_props: list[DictModelSchema] | None = Field(
        default_factory=list,
        description="自定义属性",
    )


class ActionNodeModel(Document):
    """
    行动节点模型
    """
    id: str = Field(alias="_id")
    name: str = Field(description="节点名称")
    description: str = Field(description="节点描述")
    type: str = Field(description="节点类型")
    node_kind: ActionNodeKindEnum = Field(
        default=ActionNodeKindEnum.ORDINARY,
        description="节点一级类型",
    )
    category: str | None = Field(default=None, description="节点展示分类")
    execution: NodeExecutionSpec = Field(description="节点执行配置")
    extension: NativeNodeExtensionSpec | None = Field(default=None, description="原生扩展契约")
    definition_origin: ActionNodeDefinitionOriginEnum = Field(
        default=ActionNodeDefinitionOriginEnum.USER,
        description="节点定义来源",
    )
    builtin_key: str | None = Field(default=None, description="内置节点稳定键")
    node_family_id: str | None = Field(default=None, description="封装节点资源族ID")
    definition_version: int = Field(default=1, ge=1, description="节点定义版本")
    enabled: bool = Field(default=True, description="资源是否启用")
    disabled_at: datetime | None = Field(default=None, description="禁用时间")
    disabled_by: str | None = Field(default=None, description="禁用操作者")
    is_latest: bool = Field(default=True, description="是否为节点资源最新版本")
    source_blueprint_id: str | None = Field(default=None, description="源蓝图ID")
    source_revision_id: str | None = Field(default=None, description="源蓝图Revision ID")
    version: str = Field(description="节点版本")
    handles: list[ActionNodeHandleModel] = Field(description="节点连接点")
    inputs: list[ActionNodeInputModel] = Field(description="节点输入项")
    default_configs: list[DictModelSchema] | None = Field(default=None, description="默认配置")
    related_components: list[str] = Field(description="关联组件")
    component_timeouts: dict[str, int] = Field(
        default_factory=dict,
        description="关联组件超时配置，key为组件ID，value为秒，0表示不限制",
    )
    command: str = Field(default=DEFAULT_COMPONENT_COMMAND, description="执行命令")
    command_args: list[str] = Field(
        default_factory=lambda: list(DEFAULT_COMPONENT_COMMAND_ARGS),
        description="执行命令参数",
    )
    is_deleted: bool = Field(default=False, description="是否已删除")
    
    created_at: datetime = Field(default_factory=lambda: datetime.now())
    updated_at: datetime = Field(default_factory=lambda: datetime.now())

    @model_validator(mode="after")
    def apply_contract_defaults(self):
        """应用普通节点默认契约并校验一级类型与驱动映射。"""
        self.command, self.command_args = validate_component_command(
            self.command,
            self.command_args,
        )
        if self.category is None:
            self.category = self.type
        NodeDefinitionContract(
            node_kind=self.node_kind,
            execution=self.execution,
            extension=self.extension,
        )
        return self
    
    class Settings:
        name = "action_nodes"
        indexes = [
            "id",
            "name",
            "type",
            "node_kind",
            "definition_origin",
            "builtin_key",
            "node_family_id",
            "version",
        ]

