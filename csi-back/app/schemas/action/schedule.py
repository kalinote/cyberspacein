from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel, Field, model_validator

from app.schemas.constants import (
    ActionFlowStatusEnum,
    ActionScheduleMisfirePolicyEnum,
    ActionScheduleOverlapPolicyEnum,
    ActionScheduleTypeEnum,
)


class ActionSchedulePayload(BaseModel):
    """创建和预览行动计划的公共字段。"""

    name: str = Field(min_length=1, max_length=100)
    description: str = Field(default="", max_length=500)
    blueprint_id: str = Field(min_length=1)
    params: dict[str, Any] = Field(default_factory=dict)
    schedule_type: ActionScheduleTypeEnum
    cron_expression: str | None = None
    interval_seconds: int | None = Field(default=None, ge=60)
    timezone: str = "Asia/Shanghai"
    start_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    end_at: datetime | None = None
    enabled: bool = True
    priority: int = Field(default=5, ge=1, le=10)
    overlap_policy: ActionScheduleOverlapPolicyEnum = ActionScheduleOverlapPolicyEnum.FORBID
    misfire_policy: ActionScheduleMisfirePolicyEnum = ActionScheduleMisfirePolicyEnum.FIRE_ONCE

    @model_validator(mode="after")
    def validate_schedule_fields(self):
        """校验调度类型对应的必填字段。"""
        if self.schedule_type == ActionScheduleTypeEnum.CRON:
            if not self.cron_expression or not self.cron_expression.strip():
                raise ValueError("Cron 计划必须填写 cron_expression")
            if self.interval_seconds is not None:
                raise ValueError("Cron 计划不能填写 interval_seconds")
        else:
            if self.interval_seconds is None:
                raise ValueError("固定间隔计划必须填写 interval_seconds")
            if self.cron_expression:
                raise ValueError("固定间隔计划不能填写 cron_expression")
        if self.end_at is not None and self.end_at <= self.start_at:
            raise ValueError("end_at 必须晚于 start_at")
        return self


class ActionScheduleCreateRequest(ActionSchedulePayload):
    """创建行动计划。"""


class ActionScheduleUpdateRequest(BaseModel):
    """更新行动计划。"""

    name: str | None = Field(default=None, min_length=1, max_length=100)
    description: str | None = Field(default=None, max_length=500)
    blueprint_id: str | None = None
    params: dict[str, Any] | None = None
    schedule_type: ActionScheduleTypeEnum | None = None
    cron_expression: str | None = None
    interval_seconds: int | None = Field(default=None, ge=60)
    timezone: str | None = None
    start_at: datetime | None = None
    end_at: datetime | None = None
    enabled: bool | None = None
    priority: int | None = Field(default=None, ge=1, le=10)
    overlap_policy: ActionScheduleOverlapPolicyEnum | None = None
    misfire_policy: ActionScheduleMisfirePolicyEnum | None = None


class ActionSchedulePreviewRequest(BaseModel):
    """预览周期配置的未来执行时刻。"""

    schedule_type: ActionScheduleTypeEnum
    cron_expression: str | None = None
    interval_seconds: int | None = Field(default=None, ge=60)
    timezone: str = "Asia/Shanghai"
    start_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    end_at: datetime | None = None

    @model_validator(mode="after")
    def validate_preview_fields(self):
        """校验预览参数的调度字段和有效期。"""
        if self.schedule_type == ActionScheduleTypeEnum.CRON and not self.cron_expression:
            raise ValueError("Cron 计划必须填写 cron_expression")
        if self.schedule_type == ActionScheduleTypeEnum.INTERVAL and self.interval_seconds is None:
            raise ValueError("固定间隔计划必须填写 interval_seconds")
        if self.end_at is not None and self.end_at <= self.start_at:
            raise ValueError("end_at 必须晚于 start_at")
        return self


class ActionSchedulePreviewResponse(BaseModel):
    next_runs: list[datetime]


class ActionScheduleResponse(ActionSchedulePayload):
    id: str
    blueprint_name: str
    blueprint_version: str
    next_run_at: datetime | None = None
    last_scheduled_for: datetime | None = None
    last_action_id: str | None = None
    last_trigger_status: str | None = None
    last_error: str | None = None
    created_at: datetime
    updated_at: datetime


class ActionScheduleRunResponse(BaseModel):
    action_id: str
    schedule_id: str
    schedule_name: str
    blueprint_id: str
    blueprint_name: str
    priority: int
    status: ActionFlowStatusEnum
    progress: float
    scheduled_for: datetime | None = None
    created_at: datetime
    start_at: datetime | None = None
    finished_at: datetime | None = None
    duration: float
    completed_steps: int
    total_steps: int
    error_message: str | None = None


class ActionScheduleSummaryResponse(BaseModel):
    schedule_count: int
    enabled_schedule_count: int
    task_count: int
    running_count: int
    pending_count: int
    failed_count: int
    recent_runs: list[ActionScheduleRunResponse]


class ActionSchedulerStatusResponse(BaseModel):
    online: bool
    last_heartbeat_at: datetime | None = None
    last_scan_at: datetime | None = None
