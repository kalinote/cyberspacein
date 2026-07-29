from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from app.schemas.alert.constants import (
    AlertEventTypeEnum,
    AlertResolutionTypeEnum,
    AlertSeverityEnum,
    AlertStatusEnum,
    AlertValueTypeEnum,
)


class AlertAcknowledgeRequest(BaseModel):
    """确认告警。"""

    expected_version: int = Field(ge=1)


class AlertResolveRequest(BaseModel):
    """手动解决告警。"""

    expected_version: int = Field(ge=1)
    note: str | None = Field(default=None, max_length=2000)


class AlertInstanceResponse(BaseModel):
    """告警实例列表与详情响应。"""

    id: str
    source_key: str
    resource_type: str
    resource_id: str
    resource_name: str
    resource_url: str | None = None
    field_key: str
    signal_key: str
    title: str
    detail: str
    status: AlertStatusEnum
    initial_severity: AlertSeverityEnum
    current_severity: AlertSeverityEnum
    active_rule_ids: list[str]
    trigger_value: Any
    trigger_value_type: AlertValueTypeEnum
    latest_value: Any
    latest_observed_at: datetime
    acknowledged_at: datetime | None = None
    resolved_at: datetime | None = None
    resolution_type: AlertResolutionTypeEnum | None = None
    resolution_note: str | None = None
    version: int
    triggered_at: datetime
    created_at: datetime
    updated_at: datetime


class AlertEventResponse(BaseModel):
    """告警永久事件响应。"""

    id: str
    alert_id: str
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
    created_at: datetime


class AlertStatsResponse(BaseModel):
    """告警中心统计。"""

    firing: int = 0
    acknowledged: int = 0
    resolved_today_auto: int = 0
    resolved_today_manual: int = 0
    by_severity: dict[AlertSeverityEnum, int] = Field(default_factory=dict)
    stream_cursor: str = "0-0"
