from typing import Any, Literal

from pydantic import BaseModel, Field, model_validator

from app.schemas.alert.constants import AlertOperatorEnum


class AlertThresholdValue(BaseModel):
    """保存规则阈值的规范值和可选显示单位。"""

    value: Any
    unit: str | None = None


class AlertCondition(BaseModel):
    """单个类型化告警条件。"""

    field_key: str = Field(min_length=1, max_length=100)
    operator: AlertOperatorEnum
    value: AlertThresholdValue


class AlertExpression(BaseModel):
    """预留多条件逻辑的告警表达式。"""

    logic: Literal["all", "any"] = "all"
    conditions: list[AlertCondition] = Field(min_length=1, max_length=1)

    @model_validator(mode="after")
    def validate_first_version_shape(self) -> "AlertExpression":
        """限制第一版只接收单条件表达式。"""
        if self.logic != "all" or len(self.conditions) != 1:
            raise ValueError("第一版告警规则仅支持一个条件")
        return self
