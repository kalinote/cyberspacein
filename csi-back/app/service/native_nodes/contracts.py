from __future__ import annotations

from typing import Any, Literal, Protocol

from pydantic import BaseModel, Field

from app.schemas.action.execution import (
    NativeNodeExtensionSpec,
    NodeExecutionContext,
    NodeExecutionOutcome,
    NodeExecutionSpec,
    NodeStartResult,
)


class NativeHandleDefinition(BaseModel):
    """后端内置节点端口定义。"""

    port_id: str
    interface_type_id: str
    handle_name: str
    direction: Literal["source", "target"]
    position: Literal["left", "right", "top", "bottom"]
    data_type: Literal["value", "reference"] = "value"
    label: str
    color: str = "#6366f1"
    other_compatible_interfaces: list[str] = Field(
        default_factory=list,
        description="兼容接口类型；* 表示允许任意接口类型",
    )


class NativeInputDefinition(BaseModel):
    """后端内置节点实例表单字段。"""

    id: str
    name: str
    type: str
    position: str = "center"
    label: str
    description: str = ""
    required: bool = False
    default: Any = None
    options: list[dict[str, str]] = Field(default_factory=list)
    custom_style: dict[str, Any] = Field(default_factory=dict)
    custom_props: dict[str, Any] = Field(default_factory=dict)


class BackendNativeNodeDefinition(BaseModel):
    """后端原生节点权威定义。"""

    builtin_key: str
    definition_version: int = Field(ge=1)
    name: str
    description: str
    handler: str
    handler_schema_version: int = Field(default=1, ge=1)
    category: str
    icon: str | None = None
    instance_input_schema: list[NativeInputDefinition] = Field(default_factory=list)
    handles: list[NativeHandleDefinition] = Field(default_factory=list)
    extension: NativeNodeExtensionSpec


class NativeNodeHandler(Protocol):
    """后端原生节点运行协议。"""

    async def start(
        self,
        context: NodeExecutionContext,
        spec: NodeExecutionSpec,
    ) -> NodeStartResult:
        ...

    async def reconcile(
        self,
        provider_run_id: str,
        extension_state: dict[str, Any],
    ) -> NodeExecutionOutcome | None:
        ...

    async def cancel(
        self,
        provider_run_id: str,
        reason: str,
        extension_state: dict[str, Any],
    ) -> bool:
        ...
