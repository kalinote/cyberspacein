from datetime import datetime, timezone

from beanie import Document
from pydantic import Field
from pymongo import ASCENDING, IndexModel

from app.schemas.alert.constants import AlertInboxStatusEnum
from app.schemas.alert.observation import AlertObservation


def utc_now() -> datetime:
    """返回带 UTC 时区的当前时间。"""
    return datetime.now(timezone.utc)


class AlertObservationInboxModel(Document):
    """持久化接收业务模块发布的实时观测。"""

    id: str = Field(alias="_id")
    observation: AlertObservation
    status: AlertInboxStatusEnum = AlertInboxStatusEnum.PENDING
    claimed_by: str | None = None
    lease_until: datetime | None = None
    attempts: int = 0
    next_retry_at: datetime | None = None
    last_error: str | None = None
    created_at: datetime = Field(default_factory=utc_now)
    processed_at: datetime | None = None
    expire_at: datetime | None = None

    class Settings:
        name = "alert_observation_inbox"
        indexes = [
            IndexModel(
                [
                    ("status", ASCENDING),
                    ("next_retry_at", ASCENDING),
                    ("created_at", ASCENDING),
                ]
            ),
            IndexModel([("lease_until", ASCENDING)]),
            IndexModel([("expire_at", ASCENDING)], expireAfterSeconds=0),
        ]
