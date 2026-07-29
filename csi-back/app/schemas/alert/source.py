from pydantic import BaseModel, Field, model_validator

from app.schemas.alert.constants import (
    AlertEvaluationModeEnum,
    AlertInitialEvaluationPolicyEnum,
    AlertOperatorEnum,
    AlertValueTypeEnum,
)


class AlertEnumOption(BaseModel):
    """枚举字段的稳定值和显示名称。"""

    value: str
    label: str


class AlertFieldDescriptor(BaseModel):
    """业务模块可供规则选择的检测字段。"""

    field_key: str = Field(min_length=1, max_length=100)
    field_name: str = Field(min_length=1, max_length=100)
    signal_key: str = Field(min_length=1, max_length=100)
    value_type: AlertValueTypeEnum
    unit: str | None = None
    enum_options: list[AlertEnumOption] = Field(default_factory=list)
    supported_operators: list[AlertOperatorEnum]
    supported_evaluation_modes: list[AlertEvaluationModeEnum]
    default_interval_seconds: int | None = Field(default=None, ge=1)
    initial_evaluation_policy: AlertInitialEvaluationPolicyEnum = (
        AlertInitialEvaluationPolicyEnum.INCLUDE_EXISTING
    )

    @model_validator(mode="after")
    def validate_enum_options(self) -> "AlertFieldDescriptor":
        """确保枚举字段提供唯一且非空的选项。"""
        if self.value_type == AlertValueTypeEnum.ENUM and not self.enum_options:
            raise ValueError("枚举字段必须提供可选值")
        values = [item.value for item in self.enum_options]
        if len(values) != len(set(values)):
            raise ValueError("枚举字段存在重复选项")
        if not self.supported_operators:
            raise ValueError("字段必须提供至少一个运算符")
        if not self.supported_evaluation_modes:
            raise ValueError("字段必须提供至少一种检测方式")
        return self


class AlertSourceDescriptor(BaseModel):
    """业务模块注册到告警系统的资源描述。"""

    source_key: str = Field(min_length=1, max_length=100)
    module_key: str = Field(min_length=1, max_length=100)
    module_name: str = Field(min_length=1, max_length=100)
    resource_type: str = Field(min_length=1, max_length=100)
    resource_name: str = Field(min_length=1, max_length=100)
    schema_version: int = Field(default=1, ge=1)
    fields: list[AlertFieldDescriptor] = Field(min_length=1)
    supported_evaluation_modes: list[AlertEvaluationModeEnum]

    @model_validator(mode="after")
    def validate_fields(self) -> "AlertSourceDescriptor":
        """确保告警源字段键唯一且检测方式一致。"""
        keys = [field.field_key for field in self.fields]
        if len(keys) != len(set(keys)):
            raise ValueError("告警源存在重复字段")
        source_modes = set(self.supported_evaluation_modes)
        if not source_modes:
            raise ValueError("告警源必须支持至少一种检测方式")
        if any(
            not set(field.supported_evaluation_modes).issubset(source_modes)
            for field in self.fields
        ):
            raise ValueError("字段检测方式必须包含在告警源能力中")
        return self
