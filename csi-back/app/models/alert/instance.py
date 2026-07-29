from datetime import datetime, timezone
from typing import Any

from beanie import Document
from pydantic import Field
from pymongo import ASCENDING, DESCENDING, IndexModel

from app.schemas.alert.constants import (
    AlertResolutionTypeEnum,
    AlertSeverityEnum,
    AlertStatusEnum,
    AlertValueTypeEnum,
)


def utc_now() -> datetime:
    """返回带 UTC 时区的当前时间。"""
    return datetime.now(timezone.utc)


class AlertInstanceModel(Document):
    """一次完整异常周期对应的告警实例。"""

    id: str = Field(alias="_id")
    open_key: str | None
    incident_key: str
    anomaly_sequence: int
    source_key: str
    resource_type: str
    resource_id: str
    resource_name: str
    resource_url: str | None = None
    field_key: str
    signal_key: str
    title: str
    detail: str
    status: AlertStatusEnum = AlertStatusEnum.FIRING
    initial_severity: AlertSeverityEnum
    current_severity: AlertSeverityEnum
    active_rule_ids: list[str] = Field(default_factory=list)
    trigger_value: Any
    trigger_value_type: AlertValueTypeEnum
    latest_value: Any
    latest_observed_at: datetime
    acknowledged_at: datetime | None = None
    resolved_at: datetime | None = None
    resolution_type: AlertResolutionTypeEnum | None = None
    resolution_note: str | None = None
    pending_event: dict[str, Any] | None = None
    version: int = 1
    triggered_at: datetime
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)

    class Settings:
        name = "alert_instances"
        indexes = [
            IndexModel(
                [("open_key", ASCENDING)],
                unique=True,
                partialFilterExpression={"open_key": {"$type": "string"}},
            ),
            IndexModel(
                [
                    ("status", ASCENDING),
                    ("current_severity", ASCENDING),
                    ("triggered_at", DESCENDING),
                ]
            ),
            IndexModel(
                [
                    ("source_key", ASCENDING),
                    ("status", ASCENDING),
                    ("triggered_at", DESCENDING),
                ]
            ),
            IndexModel(
                [
                    ("resource_type", ASCENDING),
                    ("resource_id", ASCENDING),
                    ("triggered_at", DESCENDING),
                ]
            ),
            IndexModel([("resolved_at", DESCENDING)]),
        ]
