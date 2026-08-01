"""实体单例综合内容分析节点的持久化 Run 模型。"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any

from beanie import Document
from pydantic import Field, field_validator, model_validator
from pymongo import ASCENDING, IndexModel

from app.schemas.action.reference import ReferenceStreamDescriptor


class EntityContentAnalysisRunModeEnum(str, Enum):
    """实体内容分析 Run 的输入输出模式。"""

    SINGLE = "single"
    REFERENCE = "reference"


class EntityContentAnalysisRunStatusEnum(str, Enum):
    """实体内容分析 Run 的生命周期状态。"""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class EntityContentAnalysisDesiredStateEnum(str, Enum):
    """实体内容分析 Run 的期望状态。"""

    RUNNING = "running"
    CANCELLED = "cancelled"


class EntityContentAnalysisRunModel(Document):
    """保存可由任意 Worker 领取和恢复的实体内容分析任务。"""

    id: str = Field(alias="_id")
    action_id: str
    node_instance_id: str
    execution_key: str
    model_config_id: str
    llm_provider: str
    analysis_field: str = "clean_content"
    min_analysis_length: int = Field(default=50, ge=0)
    chunk_size: int = Field(default=8000, ge=1)
    user_prompt_override: str | None = None
    mode: EntityContentAnalysisRunModeEnum

    single_input: dict[str, Any] | None = None
    single_output: dict[str, Any] | None = None
    source_streams: list[ReferenceStreamDescriptor] = Field(default_factory=list)
    destination_streams: list[ReferenceStreamDescriptor] = Field(
        default_factory=list
    )

    status: EntityContentAnalysisRunStatusEnum = (
        EntityContentAnalysisRunStatusEnum.PENDING
    )
    desired_state: EntityContentAnalysisDesiredStateEnum = (
        EntityContentAnalysisDesiredStateEnum.RUNNING
    )
    requested_reason: str | None = None
    active: bool = True

    received_eos_keys: list[str] = Field(default_factory=list)
    received_abort_keys: list[str] = Field(default_factory=list)
    processed_count: int = Field(default=0, ge=0)
    skipped_count: int = Field(default=0, ge=0)
    processed_byte_count: int = Field(default=0, ge=0)

    worker_id: str | None = None
    lease_token: str | None = None
    lease_expires_at: datetime | None = None
    last_heartbeat_at: datetime | None = None
    attempt: int = Field(default=0, ge=0)
    max_attempts: int = Field(default=3, ge=1)
    error_message: str | None = None

    queued_at: datetime = Field(default_factory=datetime.now)
    started_at: datetime | None = None
    finished_at: datetime | None = None
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)

    @field_validator("analysis_field")
    @classmethod
    def validate_analysis_field(cls, value: str) -> str:
        """拒绝空白的分析字段名。"""
        normalized = value.strip()
        if not normalized:
            raise ValueError("analysis_field 不能为空")
        return normalized

    @model_validator(mode="after")
    def validate_io_mode(self):
        """保证单条模式与 Reference 模式的载荷严格互斥。"""
        if self.mode == EntityContentAnalysisRunModeEnum.SINGLE:
            if self.single_input is None:
                raise ValueError("单条模式必须提供 single_input")
            if self.source_streams or self.destination_streams:
                raise ValueError("单条模式不能配置 Reference 流")
        else:
            if self.single_input is not None or self.single_output is not None:
                raise ValueError("Reference 模式不能保存单条输入输出")
            if not self.source_streams:
                raise ValueError("Reference 模式至少需要一个源流")
            if not self.destination_streams:
                raise ValueError("Reference 模式至少需要一个目标流")
            if len({item.stream_id for item in self.source_streams}) != len(
                self.source_streams
            ):
                raise ValueError("Reference 源流 ID 不能重复")
            if len(
                {item.queue_name for item in self.destination_streams}
            ) != len(self.destination_streams):
                raise ValueError("Reference 目标队列不能重复")
        return self

    class Settings:
        name = "entity_content_analysis_runs"
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
                    ("lease_expires_at", ASCENDING),
                    ("queued_at", ASCENDING),
                ]
            ),
            "action_id",
            "node_instance_id",
            "source_streams.owner_action_id",
            "destination_streams.owner_action_id",
        ]


__all__ = [
    "EntityContentAnalysisDesiredStateEnum",
    "EntityContentAnalysisRunModeEnum",
    "EntityContentAnalysisRunModel",
    "EntityContentAnalysisRunStatusEnum",
]
