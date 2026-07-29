from __future__ import annotations

from datetime import datetime, timedelta, timezone

from pymongo import ReturnDocument
from pymongo.errors import DuplicateKeyError

from app.core.config import settings
from app.models.alert.observation import AlertObservationInboxModel
from app.schemas.alert.constants import AlertInboxStatusEnum
from app.schemas.alert.observation import AlertObservation


def utc_now() -> datetime:
    """返回带 UTC 时区的当前时间。"""
    return datetime.now(timezone.utc)


class AlertObservationInboxService:
    """可靠接收、声明并确认业务模块的实时观测。"""

    @staticmethod
    async def publish(observation: AlertObservation) -> bool:
        """幂等写入实时观测，返回是否首次创建。"""
        inbox = AlertObservationInboxModel(
            id=observation.observation_id,
            observation=observation,
        )
        try:
            await inbox.insert()
            return True
        except DuplicateKeyError:
            return False

    @staticmethod
    async def claim(worker_id: str) -> AlertObservationInboxModel | None:
        """原子声明一条待处理或租约过期的观测。"""
        now = utc_now()
        raw = await AlertObservationInboxModel.get_motor_collection().find_one_and_update(
            {
                "$or": [
                    {
                        "status": {
                            "$in": [
                                AlertInboxStatusEnum.PENDING.value,
                                AlertInboxStatusEnum.FAILED.value,
                            ]
                        },
                        "$and": [
                            {
                                "$or": [
                                    {"next_retry_at": None},
                                    {"next_retry_at": {"$lte": now}},
                                ]
                            },
                            {
                                "attempts": {
                                    "$lt": settings.ALERT_OBSERVATION_MAX_ATTEMPTS
                                }
                            },
                        ],
                    },
                    {
                        "status": AlertInboxStatusEnum.PROCESSING.value,
                        "lease_until": {"$lte": now},
                    },
                ]
            },
            {
                "$set": {
                    "status": AlertInboxStatusEnum.PROCESSING.value,
                    "claimed_by": worker_id,
                    "lease_until": now
                    + timedelta(seconds=settings.ALERT_OBSERVATION_LEASE_SECONDS),
                    "last_error": None,
                },
                "$inc": {"attempts": 1},
            },
            sort=[("created_at", 1)],
            return_document=ReturnDocument.AFTER,
        )
        return AlertObservationInboxModel.model_validate(raw) if raw else None

    @staticmethod
    async def mark_processed(inbox_id: str, worker_id: str) -> bool:
        """确认当前 Worker 已处理观测。"""
        now = utc_now()
        result = await AlertObservationInboxModel.get_motor_collection().update_one(
            {
                "_id": inbox_id,
                "status": AlertInboxStatusEnum.PROCESSING.value,
                "claimed_by": worker_id,
            },
            {
                "$set": {
                    "status": AlertInboxStatusEnum.PROCESSED.value,
                    "processed_at": now,
                    "expire_at": now
                    + timedelta(
                        days=max(1, settings.ALERT_OBSERVATION_RETENTION_DAYS)
                    ),
                    "lease_until": None,
                    "next_retry_at": None,
                    "last_error": None,
                }
            },
        )
        return result.modified_count == 1

    @staticmethod
    async def mark_failed(inbox_id: str, worker_id: str, error: Exception) -> bool:
        """记录观测失败并安排退避重试。"""
        now = utc_now()
        inbox = await AlertObservationInboxModel.find_one({"_id": inbox_id})
        attempts = inbox.attempts if inbox is not None else 1
        terminal = attempts >= settings.ALERT_OBSERVATION_MAX_ATTEMPTS
        result = await AlertObservationInboxModel.get_motor_collection().update_one(
            {
                "_id": inbox_id,
                "status": AlertInboxStatusEnum.PROCESSING.value,
                "claimed_by": worker_id,
            },
            {
                "$set": {
                    "status": AlertInboxStatusEnum.FAILED.value,
                    "lease_until": None,
                    "next_retry_at": (
                        None
                        if terminal
                        else now + timedelta(seconds=min(2 ** min(attempts, 8), 300))
                    ),
                    "last_error": str(error)[:2000],
                }
            },
        )
        return result.modified_count == 1
