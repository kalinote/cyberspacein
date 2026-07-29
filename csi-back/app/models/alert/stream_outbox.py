from datetime import datetime, timezone
from typing import Any

from beanie import Document
from pydantic import Field
from pymongo import ASCENDING, IndexModel

from app.schemas.alert.constants import AlertOutboxStatusEnum


def utc_now() -> datetime:
    """返回带 UTC 时区的当前时间。"""
    return datetime.now(timezone.utc)


class AlertStreamOutboxModel(Document):
    """可靠发布告警领域 SSE 的通用 Outbox。"""

    id: str = Field(alias="_id")
    event_type: str
    aggregate_type: str
    aggregate_id: str | None = None
    aggregate_version: int | None = None
    payload: dict[str, Any] = Field(default_factory=dict)
    status: AlertOutboxStatusEnum = AlertOutboxStatusEnum.PENDING
    claimed_by: str | None = None
    lease_until: datetime | None = None
    attempts: int = 0
    next_retry_at: datetime | None = None
    last_error: str | None = None
    created_at: datetime = Field(default_factory=utc_now)
    published_at: datetime | None = None
    expire_at: datetime | None = None

    class Settings:
        name = "alert_stream_outbox"
        indexes = [
            IndexModel(
                [
                    ("status", ASCENDING),
                    ("next_retry_at", ASCENDING),
                    ("created_at", ASCENDING),
                ]
            ),
            IndexModel(
                [
                    ("aggregate_type", ASCENDING),
                    ("aggregate_id", ASCENDING),
                    ("created_at", ASCENDING),
                ]
            ),
            IndexModel([("lease_until", ASCENDING)]),
            IndexModel([("expire_at", ASCENDING)], expireAfterSeconds=0),
        ]
