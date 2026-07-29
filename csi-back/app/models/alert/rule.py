from datetime import datetime, timezone
from typing import Any

from beanie import Document
from pydantic import Field
from pymongo import ASCENDING, DESCENDING, IndexModel

from app.schemas.alert.condition import AlertExpression
from app.schemas.alert.constants import (
    AlertEvaluationModeEnum,
    AlertInitialEvaluationPolicyEnum,
    AlertRuleValidationStatusEnum,
    AlertSeverityEnum,
)


def utc_now() -> datetime:
    """返回带 UTC 时区的当前时间。"""
    return datetime.now(timezone.utc)


class AlertRuleModel(Document):
    """模块级告警规则。"""

    id: str = Field(alias="_id")
    name: str
    description: str = ""
    source_key: str
    source_schema_version: int = 1
    field_key: str
    signal_key: str
    resource_scope: dict[str, Any] = Field(default_factory=lambda: {"type": "all"})
    trigger_expression: AlertExpression
    recovery_expression: AlertExpression | None = None
    severity: AlertSeverityEnum
    evaluation_mode: AlertEvaluationModeEnum
    interval_seconds: int | None = None
    reconciliation_interval_seconds: int | None = None
    initial_evaluation_policy: AlertInitialEvaluationPolicyEnum
    trigger_consecutive_count: int = 1
    recovery_consecutive_count: int = 1
    enabled: bool = True
    validation_status: AlertRuleValidationStatusEnum = (
        AlertRuleValidationStatusEnum.VALID
    )
    validation_message: str | None = None
    version: int = 1
    active_from: datetime = Field(default_factory=utc_now)
    next_evaluate_at: datetime | None = None
    last_evaluate_at: datetime | None = None
    last_success_at: datetime | None = None
    last_error: str | None = None
    is_deleted: bool = False
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)

    class Settings:
        name = "alert_rules"
        indexes = [
            IndexModel(
                [
                    ("source_key", ASCENDING),
                    ("signal_key", ASCENDING),
                    ("enabled", ASCENDING),
                ]
            ),
            IndexModel(
                [
                    ("enabled", ASCENDING),
                    ("is_deleted", ASCENDING),
                    ("next_evaluate_at", ASCENDING),
                ]
            ),
            "validation_status",
            IndexModel([("updated_at", DESCENDING)]),
        ]
