from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator


LogLevel = Literal["TRACE", "DEBUG", "INFO", "WARNING", "ERROR", "FATAL"]
LogSource = Literal["sdk", "logging", "stdout", "stderr", "exception", "system"]


class ComponentLogEntry(BaseModel):
    event_id: str = Field(min_length=1, max_length=128)
    sequence: int = Field(ge=0)
    occurred_at: datetime
    level: LogLevel
    source: LogSource
    logger: str | None = Field(default=None, max_length=256)
    message: str = Field(max_length=32768)
    fields: dict[str, Any] = Field(default_factory=dict)
    exception: str | None = Field(default=None, max_length=32768)
    truncated: bool = False

    @field_validator("message")
    @classmethod
    def message_not_empty(cls, value: str) -> str:
        if not value:
            raise ValueError("日志消息不能为空")
        return value


class ComponentLogBatchRequest(BaseModel):
    entries: list[ComponentLogEntry] = Field(min_length=1, max_length=100)
    dropped_count: int = Field(default=0, ge=0)


class ComponentLogBatchResponse(BaseModel):
    accepted: int = 0
    duplicated: int = 0


class ActionNodeLogItem(ComponentLogEntry):
    ingested_at: datetime
    action_id: str
    node_instance_id: str
    component_run_id: str
    component_id: str
    attempt: int


class ActionNodeLogPage(BaseModel):
    items: list[ActionNodeLogItem] = Field(default_factory=list)
    next_cursor: str | None = None
    previous_cursor: str | None = None
    has_more: bool = False
