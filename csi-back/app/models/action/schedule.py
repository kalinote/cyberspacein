from datetime import datetime, timezone
from typing import Any

from beanie import Document
from pydantic import Field
from pymongo import ASCENDING, DESCENDING, IndexModel

from app.schemas.constants import (
    ActionScheduleMisfirePolicyEnum,
    ActionScheduleOverlapPolicyEnum,
    ActionScheduleTypeEnum,
)


class ActionScheduleModel(Document):
    """完整行动的周期执行计划。"""

    id: str = Field(alias="_id")
    name: str
    description: str = ""
    blueprint_id: str
    params: dict[str, Any] = Field(default_factory=dict)
    schedule_type: ActionScheduleTypeEnum
    cron_expression: str | None = None
    interval_seconds: int | None = None
    timezone: str = "Asia/Shanghai"
    start_at: datetime
    end_at: datetime | None = None
    enabled: bool = True
    priority: int = 5
    overlap_policy: ActionScheduleOverlapPolicyEnum = ActionScheduleOverlapPolicyEnum.FORBID
    misfire_policy: ActionScheduleMisfirePolicyEnum = ActionScheduleMisfirePolicyEnum.FIRE_ONCE
    next_run_at: datetime | None = None
    last_scheduled_for: datetime | None = None
    last_action_id: str | None = None
    last_trigger_status: str | None = None
    last_error: str | None = None
    is_deleted: bool = False
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    class Settings:
        name = "action_schedules"
        indexes = [
            "blueprint_id",
            IndexModel(
                [("enabled", ASCENDING), ("is_deleted", ASCENDING), ("next_run_at", ASCENDING), ("priority", DESCENDING)]
            ),
        ]
