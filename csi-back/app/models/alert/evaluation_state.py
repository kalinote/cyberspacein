from datetime import datetime, timezone
from typing import Any

from beanie import Document
from pydantic import Field
from pymongo import ASCENDING, IndexModel

from app.schemas.alert.constants import (
    AlertRuleStateEnum,
    AlertSeverityEnum,
    AlertValueTypeEnum,
)


def utc_now() -> datetime:
    """返回带 UTC 时区的当前时间。"""
    return datetime.now(timezone.utc)


class AlertRuleEvaluationStateModel(Document):
    """单条规则对单个资源的连续检测状态。"""

    id: str = Field(alias="_id")
    rule_id: str
    rule_version: int
    condition_fingerprint: str | None = None
    source_key: str
    resource_type: str
    resource_id: str
    signal_key: str
    incident_key: str
    state: AlertRuleStateEnum = AlertRuleStateEnum.NORMAL
    trigger_match_count: int = 0
    recovery_match_count: int = 0
    last_value: Any = None
    last_value_type: AlertValueTypeEnum
    last_observation_id: str
    last_observation_ordering_key: str | None = None
    last_source_event_id: str | None = None
    last_observed_at: datetime
    activated_at: datetime | None = None
    recovered_at: datetime | None = None
    updated_at: datetime = Field(default_factory=utc_now)

    class Settings:
        name = "alert_rule_evaluation_states"
        indexes = [
            IndexModel(
                [
                    ("rule_id", ASCENDING),
                    ("resource_type", ASCENDING),
                    ("resource_id", ASCENDING),
                ],
                unique=True,
            ),
            IndexModel([("incident_key", ASCENDING), ("state", ASCENDING)]),
            "updated_at",
        ]


class AlertSignalStateModel(Document):
    """同一资源信号的规则聚合、告警周期和抑制状态。"""

    id: str = Field(alias="_id")
    incident_key: str
    source_key: str
    resource_type: str
    resource_id: str
    signal_key: str
    armed: bool = True
    manual_suppressed: bool = False
    anomaly_sequence: int = 0
    active_rule_ids: list[str] = Field(default_factory=list)
    effective_severity: AlertSeverityEnum | None = None
    current_alert_id: str | None = None
    last_normal_at: datetime | None = None
    last_abnormal_at: datetime | None = None
    updated_at: datetime = Field(default_factory=utc_now)

    class Settings:
        name = "alert_signal_states"
        indexes = [
            IndexModel([("incident_key", ASCENDING)], unique=True),
            IndexModel([("source_key", ASCENDING), ("resource_type", ASCENDING)]),
            "current_alert_id",
        ]
