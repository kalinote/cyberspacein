from datetime import datetime, timezone
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.schemas.alert.constants import (
    AlertEvaluationModeEnum,
    AlertInitialEvaluationPolicyEnum,
    AlertOperatorEnum,
    AlertValueTypeEnum,
)
from app.schemas.alert.source import AlertEnumOption, AlertFieldDescriptor


class ComponentSignalResourceRef(BaseModel):
    """描述组件观测对应的稳定业务资源。"""

    model_config = ConfigDict(extra="forbid")

    resource_id: str = Field(min_length=1, max_length=300)
    resource_name: str | None = Field(default=None, max_length=300)

    @field_validator("resource_id", "resource_name")
    @classmethod
    def validate_resource_text(cls, value: str | None) -> str | None:
        """拒绝仅包含空白的资源标识和名称。"""
        if value is None:
            return None
        normalized = value.strip()
        if not normalized:
            raise ValueError("资源标识和名称不能仅包含空白")
        return normalized


class ResolvedComponentSignalResource(BaseModel):
    """表示服务端校验并解析后的组件信号资源。"""

    resource_id: str = Field(min_length=1, max_length=300)
    resource_name: str | None = Field(default=None, max_length=300)
    resource_url: str | None = Field(default=None, max_length=1000)

    @field_validator("resource_id", "resource_name")
    @classmethod
    def validate_resource_text(cls, value: str | None) -> str | None:
        """规范化解析器生成的资源标识和名称。"""
        if value is None:
            return None
        normalized = value.strip()
        if not normalized:
            raise ValueError("解析后的资源标识和名称不能仅包含空白")
        return normalized

    @field_validator("resource_url")
    @classmethod
    def validate_resource_url(cls, value: str | None) -> str | None:
        """只允许资源解析器生成站内相对地址。"""
        if value is not None and (
            not value.startswith("/") or value.startswith("//")
        ):
            raise ValueError("组件信号资源地址必须是站内相对路径")
        return value


class ComponentSignalReport(BaseModel):
    """组件提交的一条受控资源状态报告。"""

    model_config = ConfigDict(extra="forbid")

    report_id: str = Field(min_length=1, max_length=128)
    definition_key: str = Field(min_length=1, max_length=100)
    definition_version: int = Field(ge=1)
    resource: ComponentSignalResourceRef
    value: Any
    observed_at: datetime
    source_event_id: str | None = Field(default=None, max_length=500)
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("report_id", "definition_key", "source_event_id")
    @classmethod
    def validate_stable_text(cls, value: str | None) -> str | None:
        """规范化稳定标识并拒绝空白值。"""
        if value is None:
            return None
        normalized = value.strip()
        if not normalized:
            raise ValueError("稳定标识不能仅包含空白")
        return normalized

    @field_validator("observed_at")
    @classmethod
    def normalize_observed_at(cls, value: datetime) -> datetime:
        """将组件观测时间转换为 MongoDB 可稳定往返的 UTC 毫秒精度。"""
        if value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        else:
            value = value.astimezone(timezone.utc)
        return value.replace(microsecond=(value.microsecond // 1000) * 1000)


class ComponentSignalBatchRequest(BaseModel):
    """组件信号批量上报请求。"""

    model_config = ConfigDict(extra="forbid")

    reports: list[ComponentSignalReport] = Field(min_length=1, max_length=100)


class ComponentSignalReportResult(BaseModel):
    """单条组件信号的接收结果。"""

    report_id: str
    status: Literal["accepted", "duplicate", "stale"]
    observation_id: str | None = None


class ComponentSignalBatchResponse(BaseModel):
    """组件信号批量上报结果。"""

    results: list[ComponentSignalReportResult]


class ComponentSignalDefinition(BaseModel):
    """服务端注册并授权给组件使用的信号定义。"""

    model_config = ConfigDict(frozen=True)

    definition_key: str = Field(min_length=1, max_length=100)
    definition_version: int = Field(default=1, ge=1)
    source_schema_version: int = Field(default=1, ge=1)
    source_key: str = Field(min_length=1, max_length=100)
    module_key: str = Field(min_length=1, max_length=100)
    module_name: str = Field(min_length=1, max_length=100)
    resource_type: str = Field(min_length=1, max_length=100)
    resource_name: str = Field(min_length=1, max_length=100)
    field_key: str = Field(min_length=1, max_length=100)
    field_name: str = Field(min_length=1, max_length=100)
    signal_key: str = Field(min_length=1, max_length=100)
    value_type: AlertValueTypeEnum
    unit: str | None = None
    enum_options: list[AlertEnumOption] = Field(default_factory=list)
    supported_operators: list[AlertOperatorEnum]
    supported_evaluation_modes: list[AlertEvaluationModeEnum]
    allowed_component_ids: frozenset[str] = Field(min_length=1)
    allowed_metadata_keys: frozenset[str] = Field(default_factory=frozenset)
    max_metadata_bytes: int = Field(default=16384, ge=2)
    default_interval_seconds: int | None = Field(default=None, ge=1)
    initial_evaluation_policy: AlertInitialEvaluationPolicyEnum = (
        AlertInitialEvaluationPolicyEnum.INCLUDE_EXISTING
    )

    @model_validator(mode="after")
    def validate_definition(self) -> "ComponentSignalDefinition":
        """校验枚举、检测能力和授权集合。"""
        AlertFieldDescriptor(
            field_key=self.field_key,
            field_name=self.field_name,
            signal_key=self.signal_key,
            value_type=self.value_type,
            unit=self.unit,
            enum_options=self.enum_options,
            supported_operators=self.supported_operators,
            supported_evaluation_modes=self.supported_evaluation_modes,
            default_interval_seconds=self.default_interval_seconds,
            initial_evaluation_policy=self.initial_evaluation_policy,
        )
        if any(not item.strip() for item in self.allowed_component_ids):
            raise ValueError("组件授权标识不能为空")
        if any(not item.strip() for item in self.allowed_metadata_keys):
            raise ValueError("metadata 允许键不能为空")
        return self

    def to_field_descriptor(self) -> AlertFieldDescriptor:
        """转换为现有告警源字段描述。"""
        return AlertFieldDescriptor(
            field_key=self.field_key,
            field_name=self.field_name,
            signal_key=self.signal_key,
            value_type=self.value_type,
            unit=self.unit,
            enum_options=self.enum_options,
            supported_operators=self.supported_operators,
            supported_evaluation_modes=self.supported_evaluation_modes,
            default_interval_seconds=self.default_interval_seconds,
            initial_evaluation_policy=self.initial_evaluation_policy,
        )
