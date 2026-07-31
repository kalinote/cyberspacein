from app.schemas.alert.constants import (
    AlertEvaluationModeEnum,
    AlertInitialEvaluationPolicyEnum,
    AlertOperatorEnum,
    AlertValueTypeEnum,
)
from app.schemas.alert.source import AlertEnumOption
from app.schemas.component_signal import ComponentSignalDefinition
from app.service.component_signal.registry import ComponentSignalDefinitionRegistry


def register_builtin_component_signals(
    registry: ComponentSignalDefinitionRegistry,
) -> None:
    """注册不依赖具体采集或代理业务的通用演示信号。"""
    registry.register(
        ComponentSignalDefinition(
            definition_key="component.demo.health",
            definition_version=1,
            source_schema_version=1,
            source_key="component.demo",
            module_key="component",
            module_name="基础组件",
            resource_type="component_demo_resource",
            resource_name="组件资源",
            field_key="health",
            field_name="健康状态",
            signal_key="component_health",
            value_type=AlertValueTypeEnum.ENUM,
            enum_options=[
                AlertEnumOption(value="normal", label="正常"),
                AlertEnumOption(value="abnormal", label="异常"),
            ],
            supported_operators=[
                AlertOperatorEnum.EQ,
                AlertOperatorEnum.NE,
                AlertOperatorEnum.IN,
                AlertOperatorEnum.NOT_IN,
            ],
            supported_evaluation_modes=[
                AlertEvaluationModeEnum.REALTIME,
                AlertEvaluationModeEnum.HYBRID,
            ],
            allowed_component_ids={"*"},
            allowed_metadata_keys={"message", "error_type", "elapsed_ms"},
            default_interval_seconds=300,
            initial_evaluation_policy=(
                AlertInitialEvaluationPolicyEnum.INCLUDE_EXISTING
            ),
        )
    )
