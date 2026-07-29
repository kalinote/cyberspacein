from datetime import datetime, timezone
from typing import Any

from beanie import Document
from pydantic import Field
from pymongo import ASCENDING, IndexModel

from app.schemas.alert.constants import (
    AlertEventTypeEnum,
    AlertSeverityEnum,
    AlertStatusEnum,
    AlertValueTypeEnum,
)


def utc_now() -> datetime:
    """返回带 UTC 时区的当前时间。"""
    return datetime.now(timezone.utc)


class AlertEventModel(Document):
    """永久保存告警生命周期与等级变化。"""

    id: str = Field(alias="_id")
    alert_id: str
    incident_key: str
    event_type: AlertEventTypeEnum
    from_status: AlertStatusEnum | None = None
    to_status: AlertStatusEnum | None = None
    from_severity: AlertSeverityEnum | None = None
    to_severity: AlertSeverityEnum | None = None
    rule_id: str | None = None
    rule_version: int | None = None
    observation_id: str | None = None
    value: Any = None
    value_type: AlertValueTypeEnum | None = None
    note: str | None = None
    alert_version: int
    created_at: datetime = Field(default_factory=utc_now)

    class Settings:
        name = "alert_events"
        indexes = [
            IndexModel([("alert_id", ASCENDING), ("created_at", ASCENDING)]),
            IndexModel([("incident_key", ASCENDING), ("created_at", ASCENDING)]),
            "created_at",
        ]
