from datetime import datetime
from typing import Any, Literal
from beanie import Document
from pydantic import BaseModel, Field
from pymongo import ASCENDING, IndexModel

from app.schemas.constants import (
    ActionConfigIOTypeEnum,
    ActionFlowStatusEnum,
    ActionInstanceNodeStatusEnum,
    ActionInvocationModeEnum,
    ActionTriggerTypeEnum,
    ActionVisibilityEnum,
)
from app.schemas.action.execution import (
    BlueprintExecutionPlan,
    NativeNodeExtensionSpec,
    NodeExecutionSpec,
)
from app.schemas.action.reference import (
    ReferenceQueueBinding,
    ReferenceStreamDescriptor,
)
from app.schemas.general import DictModelSchema
from app.models.action.blueprint import ActionBlueprintSnapshotModel

class ActionInstanceModel(Document):
    """
    行动实例化流程模型
    """
    id: str = Field(alias="_id")
    blueprint_id: str = Field(description="蓝图ID")
    blueprint_snapshot: ActionBlueprintSnapshotModel = Field(
        description="行动创建时使用的完整蓝图快照"
    )
    blueprint_revision_id: str | None = Field(default=None, description="不可变蓝图Revision ID")
    execution_plan_snapshot: BlueprintExecutionPlan = Field(
        description="行动启动时使用的不可变执行计划"
    )
    invocation_mode: ActionInvocationModeEnum = Field(
        default=ActionInvocationModeEnum.STANDALONE,
        description="蓝图调用模式",
    )
    debug: bool = Field(default=False, description="是否以调试模式运行")
    visibility: ActionVisibilityEnum = Field(
        default=ActionVisibilityEnum.NORMAL,
        description="行动历史可见性",
    )
    root_action_id: str | None = Field(default=None, description="根行动ID")
    parent_action_id: str | None = Field(default=None, description="父行动ID")
    parent_node_instance_id: str | None = Field(default=None, description="父节点实例ID")
    parent_node_execution_id: str | None = Field(default=None, description="父节点执行ID")
    nesting_depth: int = Field(default=0, ge=0, description="嵌套深度")
    invocation_inputs: dict[str, Any] = Field(default_factory=dict, description="子行动调用输入")
    invocation_outputs: dict[str, Any] = Field(default_factory=dict, description="子行动调用输出")
    invocation_reference_inputs: dict[str, list[ReferenceStreamDescriptor]] = Field(
        default_factory=dict,
        description="按公开端口冻结的子行动 Reference 输入流",
    )
    invocation_reference_outputs: dict[str, list[ReferenceStreamDescriptor]] = Field(
        default_factory=dict,
        description="按公开端口冻结的子行动 Reference 输出流",
    )
    reference_finalization_state: Literal[
        "none",
        "bridging",
        "completed",
        "failed",
        "cancelled",
    ] = Field(default="none", description="Reference 跨运行时交接状态")
    reference_queue_lifecycle: Literal[
        "provisioning",
        "active",
        "closing",
        "cleanup_failed",
        "cleaned",
    ] = Field(default="provisioning", description="Reference 队列生命周期状态")
    queue_cleanup_state: Literal[
        "pending",
        "completed",
        "failed",
    ] = Field(default="pending", description="行动自有队列清理状态")
    initiator_user_id: str | None = Field(default=None, description="行动发起用户ID")
    is_deleted: bool = Field(default=False, description="是否已删除")

    start_at: datetime | None = Field(default=None, description="行动实例化流程开始时间")
    deadline_at: datetime | None = Field(default=None, description="行动执行截止时间")
    paused_at: datetime | None = Field(default=None, description="行动最近一次暂停时间")
    paused_duration: float = Field(default=0, description="行动累计暂停时长(秒)")
    finished_at: datetime | None = Field(default=None, description="行动实例化流程结束时间")
    status: ActionFlowStatusEnum = Field(default=ActionFlowStatusEnum.READY, description="行动实例化流程状态")
    implementation_period: int = Field(default=0, description="行动执行期限(秒)，0表示不限制")

    nodes_id: list[str] = Field(default_factory=list, description="节点ID列表，这是节点id")
    finished_nodes_instance: list[str] = Field(default_factory=list, description="已完成的节点ID列表，这是节点实例id")
    duration: float = Field(default=0, description="行动执行时长(秒)")
    created_at: datetime = Field(default_factory=lambda: datetime.now())
    updated_at: datetime = Field(default_factory=lambda: datetime.now())
    
    progress: float = Field(default=0, description="行动实例化流程进度(%)")
    trigger_type: ActionTriggerTypeEnum = Field(default=ActionTriggerTypeEnum.MANUAL)
    trigger_key: str | None = None
    scheduled_for: datetime | None = None
    schedule_id: str | None = None
    schedule_name: str | None = None
    schedule_priority: int = 5

    class Settings:
        name = "action_instances"
        indexes = [
            "id",
            "blueprint_id",
            "status",
            "visibility",
            "root_action_id",
            "parent_action_id",
            "blueprint_revision_id",
            IndexModel(
                [("trigger_key", ASCENDING)],
                unique=True,
                partialFilterExpression={"trigger_key": {"$type": "string"}},
            ),
            IndexModel([("schedule_id", ASCENDING), ("created_at", ASCENDING)]),
        ]

class ActionConfigIOModel(BaseModel):
    type: ActionConfigIOTypeEnum = Field(description="数据类型")
    key: str = Field(description="接口名")
    value: Any = Field(description="数据值")
        
class ActionInstanceNodeModel(Document):
    """
    行动实例节点信息模型
    
    TODO: 尚不完善
    """
    id: str = Field(alias="_id")
    action_id: str = Field(description="行动ID")
    node_id: str = Field(description="节点ID")
    definition_id: str = Field(description="行动节点定义ID")
    definition_snapshot: dict[str, Any] = Field(
        description="行动创建时冻结的完整节点定义"
    )
    status: ActionInstanceNodeStatusEnum = Field(default=ActionInstanceNodeStatusEnum.UNKNOWN, description="节点状态")
    error_message: str | None = Field(default=None, description="节点执行错误信息")
    
    start_at: datetime | None = Field(default=None, description="节点执行开始时间")
    finished_at: datetime | None = Field(default=None, description="节点执行结束时间")
    duration: float = Field(default=0, description="节点执行时长(秒)")
    
    progress: float = Field(default=0, description="节点执行进度(%)")
    configs: list[DictModelSchema] = Field(default_factory=list, description="节点配置")
    inputs: dict[str, ActionConfigIOModel] = Field(default_factory=dict, description="节点输入配置，key是handle_id，value是数据")
    outputs: dict[str, ActionConfigIOModel] = Field(default_factory=dict, description="节点输出配置，key是handle_id，value是数据")
    reference_queue_bindings: dict[str, ReferenceQueueBinding] = Field(
        default_factory=dict,
        description="REFERENCE 类型执行边到队列描述符的映射，key 为 edge_id",
    )
    finalization_claimed: bool = Field(default=False, description="是否已有组件声明节点终态处理")
    execution_spec_snapshot: NodeExecutionSpec = Field(
        description="节点执行配置快照"
    )
    extension_spec_snapshot: NativeNodeExtensionSpec | None = Field(
        default=None,
        description="节点扩展配置快照",
    )
    node_definition_version: int = Field(default=1, ge=1, description="节点定义版本")
    extension_contract_version: int | None = Field(default=None, description="扩展契约版本")
    current_execution_id: str | None = Field(default=None, description="当前执行记录ID")
    execution_ids: list[str] = Field(
        default_factory=list,
        description="该节点全部执行键对应的通用执行记录ID",
    )
    skip_reason: str | None = Field(default=None, description="编译跳过原因")
    effective_in_degree: int = Field(default=0, ge=0, description="执行图有效入度")
    effective_out_degree: int = Field(default=0, ge=0, description="执行图有效出度")
    instance_config: dict[str, Any] = Field(default_factory=dict, description="蓝图节点实例配置快照")
    delivered_dependencies: list[str] = Field(
        default_factory=list,
        description="已完成数据传递的直接前置设计节点ID",
    )
    activated_input_edge_ids: list[str] = Field(
        default_factory=list,
        description="Reference生产者已启动的输入边ID",
    )
    delivered_input_edge_ids: list[str] = Field(
        default_factory=list,
        description="已物化或完成传递的输入边ID",
    )
    aborted_input_edge_ids: list[str] = Field(
        default_factory=list,
        description="已确认无法产生数据的输入边ID",
    )
    
    class Settings:
        name = "action_instance_nodes"
        indexes = [
            "id",
            "action_id",
            "current_execution_id",
        ]
