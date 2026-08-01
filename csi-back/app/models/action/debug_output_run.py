"""调试输出节点的持久化 Run 模型。"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Literal

from beanie import Document
from pydantic import BaseModel, Field, model_validator
from pymongo import ASCENDING, IndexModel

from app.schemas.action.reference import ReferenceStreamDescriptor


class DebugOutputRunStatusEnum(str, Enum):
    """调试输出 Run 的生命周期状态。"""

    PENDING = "pending"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class DebugOutputDesiredStateEnum(str, Enum):
    """调试输出 Run 的期望状态。"""

    RUNNING = "running"
    PAUSED = "paused"
    CANCELLED = "cancelled"


class DebugOutputInputEdgeModel(BaseModel):
    """冻结调试输入边及其数据传输契约。"""

    edge_id: str = Field(min_length=1)
    data_type: Literal["value", "reference"]
    source_node_id: str = Field(min_length=1)
    source_port_id: str = Field(min_length=1)
    target_port_id: str = Field(min_length=1)
    value_slot: str | None = None
    reference_stream: ReferenceStreamDescriptor | None = None

    @model_validator(mode="after")
    def validate_transport(self):
        """确保 Reference 边携带稳定的流描述符。"""
        if self.data_type == "reference" and self.reference_stream is None:
            raise ValueError("Reference 调试输入边必须提供 reference_stream")
        if self.data_type == "value" and self.reference_stream is not None:
            raise ValueError("Value 调试输入边不能提供 reference_stream")
        return self


class DebugOutputRunModel(Document):
    """保存可由任意 Worker 领取和恢复的调试输出任务。"""

    id: str = Field(alias="_id")
    action_id: str
    node_instance_id: str
    node_execution_id: str
    execution_key: str
    incoming_edges: list[DebugOutputInputEdgeModel] = Field(
        default_factory=list
    )

    status: DebugOutputRunStatusEnum = DebugOutputRunStatusEnum.PENDING
    desired_state: DebugOutputDesiredStateEnum = (
        DebugOutputDesiredStateEnum.RUNNING
    )
    requested_reason: str | None = None
    active: bool = True

    received_value_edge_ids: list[str] = Field(default_factory=list)
    aborted_input_edge_ids: list[str] = Field(default_factory=list)
    received_eos_keys: list[str] = Field(default_factory=list)
    received_abort_keys: list[str] = Field(default_factory=list)

    logged_count: int = Field(default=0, ge=0)
    logged_byte_count: int = Field(default=0, ge=0)
    truncated_count: int = Field(default=0, ge=0)
    warning_count: int = Field(default=0, ge=0)

    worker_id: str | None = None
    lease_token: str | None = None
    lease_expires_at: datetime | None = None
    last_heartbeat_at: datetime | None = None
    attempt: int = Field(default=0, ge=0)
    error_message: str | None = None

    queued_at: datetime = Field(default_factory=datetime.now)
    started_at: datetime | None = None
    finished_at: datetime | None = None
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)

    @model_validator(mode="after")
    def validate_edges(self):
        """拒绝同一 Run 内重复的执行边。"""
        edge_ids = [edge.edge_id for edge in self.incoming_edges]
        if len(set(edge_ids)) != len(edge_ids):
            raise ValueError("调试输出 Run 的输入边 ID 不能重复")
        return self

    class Settings:
        name = "debug_output_runs"
        indexes = [
            IndexModel(
                [
                    ("action_id", ASCENDING),
                    ("node_instance_id", ASCENDING),
                    ("execution_key", ASCENDING),
                ],
                unique=True,
            ),
            IndexModel(
                [
                    ("active", ASCENDING),
                    ("status", ASCENDING),
                    ("desired_state", ASCENDING),
                    ("lease_expires_at", ASCENDING),
                    ("queued_at", ASCENDING),
                ]
            ),
            "action_id",
            "node_instance_id",
            "node_execution_id",
            "incoming_edges.reference_stream.owner_action_id",
        ]


__all__ = [
    "DebugOutputDesiredStateEnum",
    "DebugOutputInputEdgeModel",
    "DebugOutputRunModel",
    "DebugOutputRunStatusEnum",
]
