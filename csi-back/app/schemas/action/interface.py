from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


class BoundaryPortMapping(BaseModel):
    """记录公开端口与绑定目标端口的映射。"""

    interface_port_id: str
    target_port_id: str


class BoundaryBinding(BaseModel):
    """记录边界节点替换的目标节点和端口。"""

    bound_node_id: str
    port_mappings: list[BoundaryPortMapping] = Field(default_factory=list)


class BlueprintInterfacePort(BaseModel):
    """蓝图发布后冻结的公开接口端口。"""

    id: str
    name: str
    label: str | None = None
    direction: Literal["input", "output"]
    handle_config_id: str | None = None
    interface_type_id: str
    data_type: Literal["value", "reference"] = "value"
    color: str | None = None
    compatible_interface_type_ids: list[str] = Field(default_factory=list)
    required: bool = False
    description: str | None = None
    schema_version: int = 1


class BlueprintInterfaceSpec(BaseModel):
    """蓝图公开流程接口。"""

    inputs: list[BlueprintInterfacePort] = Field(default_factory=list)
    outputs: list[BlueprintInterfacePort] = Field(default_factory=list)


class BlueprintValidationIssue(BaseModel):
    """蓝图编译或发布校验问题。"""

    code: str
    message: str
    node_id: str | None = None
    edge_id: str | None = None
    details: dict[str, Any] = Field(default_factory=dict)
