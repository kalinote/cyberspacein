from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel, Field, field_validator

from app.schemas.alert.constants import AlertValueTypeEnum


class AlertObservation(BaseModel):
    """业务模块提交给告警引擎的统一观测值。"""

    observation_id: str = Field(min_length=1, max_length=300)
    source_key: str = Field(min_length=1, max_length=100)
    resource_type: str = Field(min_length=1, max_length=100)
    resource_id: str = Field(min_length=1, max_length=300)
    resource_name: str = Field(min_length=1, max_length=300)
    resource_url: str | None = Field(default=None, max_length=1000)
    field_key: str = Field(min_length=1, max_length=100)
    signal_key: str = Field(min_length=1, max_length=100)
    value_type: AlertValueTypeEnum
    value: Any
    observed_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    source_event_id: str | None = Field(default=None, max_length=500)
    ordering_key: str | None = Field(default=None, max_length=500)
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("observed_at")
    @classmethod
    def normalize_observed_at(cls, value: datetime) -> datetime:
        """将观测时间统一转换为 UTC。"""
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)

    @field_validator("resource_url")
    @classmethod
    def validate_resource_url(cls, value: str | None) -> str | None:
        """第一版只允许站内相对资源地址。"""
        if value is not None and (not value.startswith("/") or value.startswith("//")):
            raise ValueError("资源地址必须是站内相对路径")
        return value


class AlertObservationPage(BaseModel):
    """Provider 分页返回的资源观测。"""

    items: list[AlertObservation]
    next_cursor: str | None = None
