from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field, model_validator

from app.schemas.alert.condition import AlertExpression
from app.schemas.alert.constants import (
    AlertEvaluationModeEnum,
    AlertInitialEvaluationPolicyEnum,
    AlertRuleValidationStatusEnum,
    AlertSeverityEnum,
)


class AlertRuleBase(BaseModel):
    """告警规则共享字段。"""

    name: str = Field(min_length=1, max_length=200)
    description: str = Field(default="", max_length=2000)
    source_key: str = Field(min_length=1, max_length=100)
    field_key: str = Field(min_length=1, max_length=100)
    resource_scope: dict = Field(default_factory=lambda: {"type": "all"})
    trigger_expression: AlertExpression
    recovery_expression: AlertExpression | None = None
    severity: AlertSeverityEnum
    evaluation_mode: AlertEvaluationModeEnum
    interval_seconds: int | None = Field(default=None, ge=60, le=86400)
    initial_evaluation_policy: AlertInitialEvaluationPolicyEnum | None = None
    trigger_consecutive_count: int = Field(default=1, ge=1, le=100)
    recovery_consecutive_count: int = Field(default=1, ge=1, le=100)

    @model_validator(mode="after")
    def validate_schedule_and_scope(self) -> "AlertRuleBase":
        """校验第一版资源范围与周期字段。"""
        if self.resource_scope != {"type": "all"}:
            raise ValueError("第一版告警规则仅支持模块内全部资源")
        if self.evaluation_mode in {
            AlertEvaluationModeEnum.INTERVAL,
            AlertEvaluationModeEnum.HYBRID,
        } and self.interval_seconds is None:
            raise ValueError("周期或混合检测必须设置检测周期")
        if (
            self.evaluation_mode == AlertEvaluationModeEnum.REALTIME
            and self.interval_seconds is not None
        ):
            raise ValueError("实时检测不接受用户检测周期")
        return self


class AlertRuleCreateRequest(AlertRuleBase):
    """创建告警规则。"""

    enabled: bool = True


class AlertRuleUpdateRequest(BaseModel):
    """修改告警规则，未提供字段保持不变。"""

    name: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=2000)
    trigger_expression: AlertExpression | None = None
    recovery_expression: AlertExpression | None = None
    clear_recovery_expression: bool = False
    severity: AlertSeverityEnum | None = None
    evaluation_mode: AlertEvaluationModeEnum | None = None
    interval_seconds: int | None = Field(default=None, ge=60, le=86400)
    initial_evaluation_policy: AlertInitialEvaluationPolicyEnum | None = None
    trigger_consecutive_count: int | None = Field(default=None, ge=1, le=100)
    recovery_consecutive_count: int | None = Field(default=None, ge=1, le=100)
    expected_version: int = Field(ge=1)


class AlertRuleEnabledRequest(BaseModel):
    """启用或停用规则。"""

    enabled: bool
    expected_version: int = Field(ge=1)


class AlertRuleResponse(AlertRuleBase):
    """告警规则响应。"""

    id: str
    source_schema_version: int
    signal_key: str
    enabled: bool
    validation_status: AlertRuleValidationStatusEnum
    validation_message: str | None = None
    version: int
    active_from: datetime
    next_evaluate_at: datetime | None = None
    last_evaluate_at: datetime | None = None
    last_success_at: datetime | None = None
    last_error: str | None = None
    created_at: datetime
    updated_at: datetime


class AlertRuleValidationResponse(BaseModel):
    """规则保存前校验结果。"""

    valid: bool = True
    source_schema_version: int
    signal_key: str


class AlertRuleTestResponse(BaseModel):
    """规则试运行命中摘要。"""

    scanned: int
    matched: int
    truncated: bool
    samples: list[dict[str, Any]] = Field(default_factory=list)
