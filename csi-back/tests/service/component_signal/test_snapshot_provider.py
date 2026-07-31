from datetime import datetime, timezone
from types import SimpleNamespace

import pytest

from app.models.component_signal import ComponentSignalSnapshotModel
from app.schemas.alert.constants import (
    AlertEvaluationModeEnum,
    AlertOperatorEnum,
    AlertValueTypeEnum,
)
from app.schemas.component_signal import ComponentSignalDefinition
from app.service.component_signal.registry import ComponentSignalDefinitionRegistry
from app.service.component_signal.snapshot_provider import (
    ComponentSignalSnapshotProvider,
)


@pytest.fixture(autouse=True)
def initialized_snapshot_model(monkeypatch):
    """为不连接 MongoDB 的模型构造提供最小集合占位。"""
    monkeypatch.setattr(
        ComponentSignalSnapshotModel,
        "get_motor_collection",
        staticmethod(lambda: SimpleNamespace()),
    )


class _SnapshotQuery:
    """模拟 Beanie 快照分页查询。"""

    def __init__(self, items):
        self.items = items

    def sort(self, _value):
        return self

    def limit(self, _value):
        return self

    async def to_list(self):
        return self.items


@pytest.mark.asyncio
async def test_snapshot_provider_returns_stable_version_observation(
    monkeypatch,
) -> None:
    registry = ComponentSignalDefinitionRegistry()
    registry.register(
        ComponentSignalDefinition(
            definition_key="test.ready",
            source_key="test.component",
            module_key="test",
            module_name="测试组件",
            resource_type="test_resource",
            resource_name="测试资源",
            field_key="ready",
            field_name="就绪",
            signal_key="ready_status",
            value_type=AlertValueTypeEnum.BOOLEAN,
            supported_operators=[
                AlertOperatorEnum.EQ,
                AlertOperatorEnum.NE,
            ],
            supported_evaluation_modes=[
                AlertEvaluationModeEnum.REALTIME,
                AlertEvaluationModeEnum.HYBRID,
            ],
            allowed_component_ids={"component-a"},
        )
    )
    now = datetime.now(timezone.utc)
    snapshot = ComponentSignalSnapshotModel(
        id="snapshot-1",
        definition_key="test.ready",
        definition_version=1,
        source_schema_version=1,
        source_key="test.component",
        resource_type="test_resource",
        resource_id="resource-1",
        resource_name="资源一",
        field_key="ready",
        signal_key="ready_status",
        value_type=AlertValueTypeEnum.BOOLEAN,
        current_value=True,
        last_report_id="report-1",
        last_observation_id="observation-1",
        last_component_id="component-a",
        last_component_run_id="run-1",
        last_action_id="action-1",
        last_node_instance_id="node-1",
        observed_at=now,
        metadata={},
        version=3,
    )
    captured = {}

    def find(query):
        captured.update(query)
        return _SnapshotQuery([snapshot])

    monkeypatch.setattr(
        ComponentSignalSnapshotModel,
        "find",
        staticmethod(find),
    )
    provider = ComponentSignalSnapshotProvider("test.component", registry)

    page = await provider.iter_observations(
        field_key="ready",
        active_from=now,
        cursor=None,
        limit=1,
    )

    assert page.next_cursor == "snapshot-1"
    assert page.items[0].source_event_id == "component-report:report-1"
    assert page.items[0].value is True
    assert captured["source_key"] == "test.component"
