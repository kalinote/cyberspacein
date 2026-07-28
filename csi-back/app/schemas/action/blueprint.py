from typing import Any
from datetime import datetime
from pydantic import BaseModel, Field, model_validator

from app.schemas.action.interface import (
    BlueprintInterfaceSpec,
    BoundaryBinding,
)
from app.schemas.constants import ActionNodeTypeEnum


class PositionSchema(BaseModel):
    """位置坐标"""
    x: float = Field(description="X坐标")
    y: float = Field(description="Y坐标")


class NodeDataSchema(BaseModel):
    """节点数据"""
    definition_id: str = Field(description="定义ID")
    version: str = Field(description="版本")
    form_data: dict[str, Any] = Field(description="表单数据，字典格式")
    node_definition_version: int = Field(default=1, ge=1)
    instance_config: dict[str, Any] = Field(default_factory=dict)
    interface_port_id: str | None = None
    boundary_binding: BoundaryBinding | None = None


class GraphNodeSchema(BaseModel):
    """图节点"""
    id: str = Field(description="节点ID")
    type: str = Field(description="节点类型")
    position: PositionSchema = Field(description="节点位置")
    data: NodeDataSchema = Field(description="节点数据")


class GraphEdgeSchema(BaseModel):
    """图边"""
    id: str = Field(description="边ID")
    source: str = Field(description="源节点ID")
    sourceHandle: str | None = Field(default=None, description="旧源节点连接点")
    target: str = Field(description="目标节点ID")
    targetHandle: str | None = Field(default=None, description="旧目标节点连接点")
    source_port_id: str | None = Field(default=None, description="稳定源端口ID")
    target_port_id: str | None = Field(default=None, description="稳定目标端口ID")

    @model_validator(mode="after")
    def normalize_port_ids(self):
        """双读双写新旧端口字段。"""
        self.source_port_id = self.source_port_id or self.sourceHandle
        self.target_port_id = self.target_port_id or self.targetHandle
        self.sourceHandle = self.sourceHandle or self.source_port_id
        self.targetHandle = self.targetHandle or self.target_port_id
        if not self.source_port_id or not self.target_port_id:
            raise ValueError("蓝图边必须提供源端口和目标端口")
        return self


class ViewportSchema(BaseModel):
    """视口"""
    x: float = Field(description="视口X坐标")
    y: float = Field(description="视口Y坐标")
    zoom: float = Field(description="缩放比例")


class GraphSchema(BaseModel):
    """图结构"""
    nodes: list[GraphNodeSchema] = Field(description="节点列表")
    edges: list[GraphEdgeSchema] = Field(description="边列表")
    viewport: ViewportSchema = Field(description="视口信息")

class TemplateParamSchema(BaseModel):
    """模板参数"""

    id: str | None = Field(default=None, description="稳定参数ID")
    name: str = Field(description="参数名称（唯一标识）")
    type: str = Field(description="参数类型（对应INPUT_TYPES）")
    label: str = Field(description="参数显示名称")
    required: bool = Field(default=False, description="是否必填")
    description: str | None = Field(default=None, description="参数描述")
    default: Any = Field(default=None, description="默认值")
    options: list[dict[str, Any]] = Field(default_factory=list, description="可选值")
    validation: dict[str, Any] = Field(default_factory=dict, description="校验规则")

class TemplateSpecSchema(BaseModel):
    """模板规格"""
    params: list[TemplateParamSchema] = Field(description="参数列表")
    bindings: dict[str, dict[str, str]] = Field(
        description="绑定关系 {节点ID: {字段名: 参数名}}"
    )

class ActionBlueprintSchema(BaseModel):
    """行动蓝图"""
    name: str = Field(description="蓝图名称")
    description: str = Field(description="蓝图描述")
    version: str = Field(description="蓝图版本")
    target: str = Field(description="行动目标")
    implementation_period: int = Field(default=0, ge=0, description="执行期限(秒)，0表示不限制")
    resource: dict[str, Any] | None = Field(default=None, description="资源信息")
    graph: GraphSchema = Field(description="图结构")
    is_template: bool = Field(default=False, description="是否为模板")
    template: TemplateSpecSchema | None = Field(default=None, description="模板规格")
    interface: BlueprintInterfaceSpec = Field(
        default_factory=BlueprintInterfaceSpec,
        description="由边界节点生成的公开接口，只读回显",
    )

class ActionBlueprintDetailResponseSchema(ActionBlueprintSchema):
    """行动蓝图响应"""
    id: str = Field(description="蓝图ID")
    created_at: datetime = Field(description="创建时间")
    updated_at: datetime = Field(description="更新时间")


class BlueprintScheduleImpactSchema(BaseModel):
    """蓝图更新导致停用的调度计划。"""
    id: str = Field(description="调度计划ID")
    name: str = Field(description="调度计划名称")
    reason: str = Field(description="停用原因")


class ActionBlueprintUpdateResponseSchema(BaseModel):
    """行动蓝图更新响应。"""
    blueprint: ActionBlueprintDetailResponseSchema
    disabled_schedules: list[BlueprintScheduleImpactSchema] = Field(default_factory=list)


class ActionBlueprintBaseInfoResponse(BaseModel):
    """行动蓝图基础信息响应"""
    id: str = Field(description="蓝图ID")
    name: str = Field(description="蓝图名称")
    version: str = Field(description="蓝图版本")
    description: str = Field(description="蓝图描述")
    target: str = Field(description="行动目标")
    type: str = Field(default="尚未实现", description="蓝图分类标签")
    type_tag_color: str = Field(default="#dbeafe", description="蓝图分类tag颜色") # TODO: 后续改为可配置
    type_text_color: str = Field(default="#1e40af", description="蓝图分类tag文字颜色") # TODO: 后续改为可配置
    implementation_period: int = Field(default=0, ge=0, description="执行期限(秒)，0表示不限制")
    created_at: datetime = Field(description="创建时间")
    updated_at: datetime = Field(description="更新时间")
    steps: int = Field(description="总步骤数量")
    branches: int = Field(description="总分支数量")
    is_template: bool = Field(default=False, description="是否为模板")
    latest_revision_number: int | None = None
    encapsulated_node_count: int = 0


class BlueprintValidateRequest(BaseModel):
    """校验蓝图草稿或指定调用模式。"""

    invocation_mode: str = "standalone"


class BlueprintValidateResponse(BaseModel):
    """蓝图校验与接口预览结果。"""

    valid: bool
    errors: list[dict[str, Any]] = Field(default_factory=list)
    warnings: list[dict[str, Any]] = Field(default_factory=list)
    interface: BlueprintInterfaceSpec = Field(default_factory=BlueprintInterfaceSpec)


class BlueprintRevisionResponse(BaseModel):
    """不可变蓝图Revision响应。"""

    id: str
    blueprint_id: str
    version: str
    revision_number: int
    content_hash: str
    interface_snapshot: BlueprintInterfaceSpec
    published_at: datetime
    published_by: str | None = None


class BlueprintPublishResponse(BaseModel):
    """发布蓝图响应。"""

    revision: BlueprintRevisionResponse
    validation_warnings: list[dict[str, Any]] = Field(default_factory=list)


class BlueprintEncapsulateRequest(BaseModel):
    """封装蓝图为节点。"""

    node_name: str = Field(min_length=1)
    description: str = ""
    category: ActionNodeTypeEnum = ActionNodeTypeEnum.SUBFLOW
    icon: str | None = None
    mode: str = Field(default="create", pattern="^(create|add_version)$")
    target_encapsulated_node_id: str | None = None


class BlueprintEncapsulateResponse(BaseModel):
    """封装操作响应。"""

    revision: BlueprintRevisionResponse
    encapsulated_node: dict[str, Any]
    generated_handles: list[dict[str, Any]] = Field(default_factory=list)
    generated_inputs: list[dict[str, Any]] = Field(default_factory=list)
    validation_warnings: list[dict[str, Any]] = Field(default_factory=list)
