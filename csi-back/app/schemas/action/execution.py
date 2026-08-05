from __future__ import annotations

import json
import re
from typing import Any, Literal

from pydantic import BaseModel, Field, model_validator

from app.schemas.constants import (
    ActionExecutionDriverEnum,
    ActionInvocationModeEnum,
    ActionNodeKindEnum,
    ActionSchedulingModeEnum,
    DEFAULT_COMPONENT_COMMAND,
    DEFAULT_COMPONENT_COMMAND_ARGS,
)
from app.schemas.action.reference import ReferenceStreamDescriptor


_DRIVER_BY_NODE_KIND = {
    ActionNodeKindEnum.ORDINARY: ActionExecutionDriverEnum.COMPONENT,
    ActionNodeKindEnum.BACKEND_NATIVE: ActionExecutionDriverEnum.BACKEND_NATIVE,
    ActionNodeKindEnum.ENCAPSULATED: ActionExecutionDriverEnum.SUBFLOW,
}
_COMPONENT_COMMAND_PATTERN = re.compile(r"^[A-Za-z0-9_./:\\-]+$")
_UNSAFE_COMPONENT_ARGUMENT = re.compile(r"[\x00-\x1f\x7f;&|<>`]")
_RESERVED_COMPONENT_ARGUMENTS = {
    "--api-base-url",
    "--component-run-id",
    "--component-bootstrap",
}
MAX_EXTENSION_PAYLOAD_BYTES = 262_144


def validate_component_command(
    command: str,
    command_args: list[str],
) -> tuple[str, list[str]]:
    """规范化组件命令并拒绝注入字符、超长值和运行时保留参数。"""
    normalized_command = command.strip()
    if not normalized_command:
        return DEFAULT_COMPONENT_COMMAND, list(DEFAULT_COMPONENT_COMMAND_ARGS)
    if len(normalized_command) > 256 or not _COMPONENT_COMMAND_PATTERN.fullmatch(
        normalized_command
    ):
        raise ValueError("组件命令只能包含可执行名称或路径，且长度不能超过256字符")
    if len(command_args) > 64:
        raise ValueError("组件命令参数不能超过64项")
    normalized_args = []
    for argument in command_args:
        if len(argument) > 1024:
            raise ValueError("单个组件命令参数长度不能超过1024字符")
        if (
            _UNSAFE_COMPONENT_ARGUMENT.search(argument)
            or "$(" in argument
            or "${" in argument
        ):
            raise ValueError("组件命令参数包含不安全字符")
        argument_name = argument.split("=", 1)[0]
        if argument_name in _RESERVED_COMPONENT_ARGUMENTS:
            raise ValueError(f"组件命令参数 {argument_name} 由运行时保留")
        normalized_args.append(argument)
    return normalized_command, normalized_args


def validate_extension_payload(
    extension_state: dict[str, Any],
    extension_result: dict[str, Any],
) -> None:
    """限制原生扩展状态与结果的合计持久化大小。"""
    payload_size = len(
        json.dumps(
            {
                "extension_state": extension_state,
                "extension_result": extension_result,
            },
            ensure_ascii=False,
            default=str,
        ).encode("utf-8")
    )
    if payload_size > MAX_EXTENSION_PAYLOAD_BYTES:
        raise ValueError(
            f"节点扩展载荷超过{MAX_EXTENSION_PAYLOAD_BYTES}字节限制"
        )


class NodeExecutionSpec(BaseModel):
    """保存节点执行驱动和版本化业务配置。"""

    driver: ActionExecutionDriverEnum
    handler: str
    schema_version: int = Field(default=1, ge=1)
    config: dict[str, Any] = Field(default_factory=dict)


class NativeNodeExtensionSpec(BaseModel):
    """保存后端原生节点的通用扩展装配。"""

    contract_version: int = Field(default=1, ge=1)
    compiler_adapter: str = "default"
    execution_policy: str = "default"
    renderer_key: str = "schema"
    config: dict[str, dict[str, Any]] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_namespaces(self):
        allowed = {"compiler", "execution_policy", "renderer"}
        unknown = set(self.config) - allowed
        if unknown:
            raise ValueError(f"原生节点扩展配置包含未知命名空间: {', '.join(sorted(unknown))}")
        return self


class NodeDefinitionContract(BaseModel):
    """校验节点一级类型与执行驱动的固定映射。"""

    node_kind: ActionNodeKindEnum
    execution: NodeExecutionSpec
    extension: NativeNodeExtensionSpec | None = None

    @model_validator(mode="after")
    def validate_contract(self):
        expected = _DRIVER_BY_NODE_KIND[self.node_kind]
        if self.execution.driver != expected:
            raise ValueError(
                f"节点类型 {self.node_kind.value} 只能使用 {expected.value} 执行驱动"
            )
        if self.node_kind == ActionNodeKindEnum.BACKEND_NATIVE and self.extension is None:
            raise ValueError("后端原生节点必须提供扩展契约")
        if self.node_kind != ActionNodeKindEnum.BACKEND_NATIVE and self.extension is not None:
            raise ValueError("普通节点和封装节点不能提供原生扩展契约")
        return self


class NodeIncomingEdge(BaseModel):
    """描述节点的一条结构化输入边。"""

    edge_id: str
    source_node_id: str
    source_port_id: str
    target_port_id: str
    data_type: Literal["value", "reference"]
    value_slot: str | None = None
    value_available: bool = False
    aborted: bool = False
    value: Any = None
    reference_stream: ReferenceStreamDescriptor | None = None


class NodeExecutionContext(BaseModel):
    """节点执行器接收的稳定上下文。"""

    action_id: str
    node_instance_id: str
    node_id: str
    execution_id: str | None = None
    execution_key: str = "default"
    invocation_mode: ActionInvocationModeEnum = ActionInvocationModeEnum.STANDALONE
    debug: bool = False
    inputs: dict[str, Any] = Field(default_factory=dict)
    input_groups: dict[str, list[Any]] = Field(default_factory=dict)
    reference_inputs: dict[str, list[ReferenceStreamDescriptor]] = Field(
        default_factory=dict,
    )
    reference_outputs: dict[str, list[ReferenceStreamDescriptor]] = Field(
        default_factory=dict,
    )
    incoming_edges: list[NodeIncomingEdge] = Field(default_factory=list)
    invocation_inputs: dict[str, Any] = Field(default_factory=dict)
    instance_config: dict[str, Any] = Field(default_factory=dict)
    initiator_user_id: str | None = None


class NodeStartResult(BaseModel):
    """节点执行器启动结果。"""

    state: Literal["completed", "running"]
    provider_run_id: str | None = None
    outputs: dict[str, Any] = Field(default_factory=dict)
    progress: float = Field(default=0, ge=0, le=100)
    extension_state: dict[str, Any] = Field(default_factory=dict)
    extension_result: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_extension_size(self):
        """拒绝把无界扩展载荷写入行动文档。"""
        validate_extension_payload(
            self.extension_state,
            self.extension_result,
        )
        return self


class NodeExecutionOutcome(BaseModel):
    """异步节点对账结果。"""

    status: Literal[
        "queued",
        "running",
        "waiting",
        "awaiting_approval",
        "completed",
        "failed",
        "cancelled",
        "timeout",
        "paused",
    ]
    outputs: dict[str, Any] = Field(default_factory=dict)
    progress: float = Field(default=0, ge=0, le=100)
    extension_state: dict[str, Any] = Field(default_factory=dict)
    extension_result: dict[str, Any] = Field(default_factory=dict)
    error_message: str | None = None

    @model_validator(mode="after")
    def validate_extension_size(self):
        """拒绝把无界扩展载荷写入行动文档。"""
        validate_extension_payload(
            self.extension_state,
            self.extension_result,
        )
        return self


class ExecutionPlanEdge(BaseModel):
    """执行计划中的稳定边快照。"""

    id: str
    source: str
    source_port_id: str
    source_handle_config_id: str | None = None
    source_interface_type_id: str | None = None
    target: str
    target_port_id: str
    target_handle_config_id: str | None = None
    target_interface_type_id: str | None = None
    data_type: Literal["value", "reference"] = "value"
    reference_protocol: Literal["eos-v1"]
    extension_contract_version: int | None = None
    extension: dict[str, Any] = Field(default_factory=dict)


class ExecutionPlanNode(BaseModel):
    """执行计划中的节点快照。"""

    id: str
    definition_id: str
    definition_version: int = 1
    node_kind: ActionNodeKindEnum
    execution: NodeExecutionSpec
    extension_spec: NativeNodeExtensionSpec | None = None
    instance_config: dict[str, Any] = Field(default_factory=dict)
    effective_in_degree: int = 0
    effective_out_degree: int = 0
    extension_contract_version: int | None = None
    extension: dict[str, Any] = Field(default_factory=dict)


class SkippedNode(BaseModel):
    """编译阶段跳过的设计节点。"""

    node_id: str
    reason: str


class BlueprintExecutionPlan(BaseModel):
    """一次调用使用的不可变蓝图执行计划。"""

    plan_schema_version: Literal[2, 3]
    revision_id: str | None = None
    invocation_mode: ActionInvocationModeEnum
    scheduling_mode: ActionSchedulingModeEnum = ActionSchedulingModeEnum.BARRIER
    debug: bool = False
    nodes: list[ExecutionPlanNode]
    edges: list[ExecutionPlanEdge]
    skipped_nodes: list[SkippedNode] = Field(default_factory=list)
    public_interface_snapshot: dict[str, Any] = Field(default_factory=dict)
    extension: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def normalize_legacy_scheduling_mode(self):
        """旧版执行计划始终按同步屏障模式解释。"""
        if self.plan_schema_version == 2:
            self.scheduling_mode = ActionSchedulingModeEnum.BARRIER
        return self


def default_component_execution() -> NodeExecutionSpec:
    """生成普通节点的默认组件执行配置。"""
    return NodeExecutionSpec(
        driver=ActionExecutionDriverEnum.COMPONENT,
        handler="component.run",
    )
