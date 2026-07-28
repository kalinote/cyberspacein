"""父子 Action 之间 Reference 流桥接的持久化模型。"""

from __future__ import annotations

from datetime import datetime
from enum import Enum

from beanie import Document
from pydantic import Field
from pymongo import ASCENDING, IndexModel

from app.schemas.action.reference import ReferenceStreamDescriptor


class ReferenceBridgeDirectionEnum(str, Enum):
    """Reference 桥接方向。"""

    INGRESS = "ingress"
    EGRESS = "egress"


class ReferenceBridgeStatusEnum(str, Enum):
    """Reference 桥接生命周期状态。"""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class ReferenceBridgeModel(Document):
    """保存可由任意 Worker 继续执行的父子 Reference 桥接。"""

    id: str = Field(alias="_id")
    parent_action_id: str
    child_action_id: str
    parent_node_instance_id: str
    public_port_id: str
    direction: ReferenceBridgeDirectionEnum
    sources: list[ReferenceStreamDescriptor]
    destinations: list[ReferenceStreamDescriptor]
    status: ReferenceBridgeStatusEnum = ReferenceBridgeStatusEnum.PENDING
    received_eos_keys: list[str] = Field(default_factory=list)
    received_abort_keys: list[str] = Field(default_factory=list)
    copied_message_count: int = Field(default=0, ge=0)
    copied_byte_count: int = Field(default=0, ge=0)
    worker_id: str | None = None
    lease_token: str | None = None
    lease_expires_at: datetime | None = None
    last_heartbeat_at: datetime | None = None
    attempt: int = Field(default=0, ge=0)
    last_error: str | None = None
    completed_at: datetime | None = None
    cancelled_at: datetime | None = None
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)

    class Settings:
        name = "reference_bridges"
        indexes = [
            IndexModel(
                [
                    ("status", ASCENDING),
                    ("lease_expires_at", ASCENDING),
                    ("created_at", ASCENDING),
                ]
            ),
            IndexModel(
                [
                    ("parent_action_id", ASCENDING),
                    ("parent_node_instance_id", ASCENDING),
                ]
            ),
            "child_action_id",
            "sources.owner_action_id",
            "destinations.owner_action_id",
        ]
