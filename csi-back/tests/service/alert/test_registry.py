from datetime import datetime

import pytest

from app.schemas.alert.constants import (
    AlertEvaluationModeEnum,
    AlertInitialEvaluationPolicyEnum,
    AlertOperatorEnum,
    AlertValueTypeEnum,
)
from app.schemas.alert.observation import AlertObservationPage
from app.schemas.alert.source import (
    AlertEnumOption,
    AlertFieldDescriptor,
    AlertSourceDescriptor,
)
from app.service.alert.registry import AlertSourceRegistry


class _Provider:
    def describe(self):
        return AlertSourceDescriptor(
            source_key="action.instance",
            module_key="action",
            module_name="行动系统",
            resource_type="action_instance",
            resource_name="行动",
            schema_version=1,
            fields=[
                AlertFieldDescriptor(
                    field_key="status",
                    field_name="状态",
                    signal_key="execution_status",
                    value_type=AlertValueTypeEnum.ENUM,
                    enum_options=[
                        AlertEnumOption(value="timeout", label="超时"),
                    ],
                    supported_operators=[
                        AlertOperatorEnum.EQ,
                        AlertOperatorEnum.NE,
                    ],
                    supported_evaluation_modes=[
                        AlertEvaluationModeEnum.REALTIME,
                        AlertEvaluationModeEnum.HYBRID,
                    ],
                    initial_evaluation_policy=(
                        AlertInitialEvaluationPolicyEnum.FROM_ACTIVATION
                    ),
                )
            ],
            supported_evaluation_modes=[
                AlertEvaluationModeEnum.REALTIME,
                AlertEvaluationModeEnum.HYBRID,
            ],
        )

    async def iter_observations(
        self,
        *,
        field_key: str,
        active_from: datetime,
        cursor: str | None,
        limit: int,
    ):
        return AlertObservationPage(items=[])


def test_registry_returns_registered_source_and_field():
    registry = AlertSourceRegistry()
    registry.register(_Provider())

    assert registry.get_descriptor("action.instance").module_name == "行动系统"
    assert registry.get_field("action.instance", "status").signal_key == "execution_status"


def test_registry_rejects_duplicate_source():
    registry = AlertSourceRegistry()
    registry.register(_Provider())

    with pytest.raises(ValueError, match="已注册"):
        registry.register(_Provider())


def test_registry_rejects_unknown_source_or_field():
    registry = AlertSourceRegistry()
    registry.register(_Provider())

    with pytest.raises(KeyError, match="未注册"):
        registry.get("proxy.resource")
    with pytest.raises(KeyError, match="告警字段"):
        registry.get_field("action.instance", "expires_at")
