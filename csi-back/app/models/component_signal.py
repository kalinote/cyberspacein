from datetime import datetime, timezone
from typing import Any

from beanie import Document
from pydantic import Field, field_validator
from pymongo import ASCENDING, IndexModel

from app.schemas.alert.constants import AlertValueTypeEnum


def utc_now() -> datetime:
    """返回带 UTC 时区的当前时间。"""
    return datetime.now(timezone.utc)


class ComponentSignalSnapshotModel(Document):
    """保存组件信号中每个业务资源的最新有效状态。"""

    id: str = Field(alias="_id")
    definition_key: str
    definition_version: int
    source_schema_version: int
    source_key: str
    resource_type: str
    resource_id: str
    resource_name: str
    resource_url: str | None = None
    field_key: str
    signal_key: str
    value_type: AlertValueTypeEnum
    current_value: Any
    last_report_id: str
    last_observation_id: str
    last_source_event_id: str | None = None
    last_component_id: str
    last_component_run_id: str
    last_action_id: str
    last_node_instance_id: str
    observed_at: datetime
    metadata: dict[str, Any] = Field(default_factory=dict)
    version: int = Field(default=1, ge=1)
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)

    @field_validator("observed_at", "created_at", "updated_at")
    @classmethod
    def normalize_datetime(cls, value: datetime) -> datetime:
        """将数据库时间统一解释为 UTC。"""
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)

    class Settings:
        name = "component_signal_snapshots"
        indexes = [
            IndexModel(
                [("definition_key", ASCENDING), ("observed_at", ASCENDING)]
            ),
            IndexModel(
                [
                    ("source_key", ASCENDING),
                    ("field_key", ASCENDING),
                    ("observed_at", ASCENDING),
                ]
            ),
            IndexModel(
                [("resource_type", ASCENDING), ("resource_id", ASCENDING)]
            ),
            "last_component_run_id",
            "updated_at",
        ]
