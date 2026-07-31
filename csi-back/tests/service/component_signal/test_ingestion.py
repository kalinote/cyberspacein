from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from app.dependencies.auth import ComponentContext
from app.models.alert.observation import AlertObservationInboxModel
from app.models.component_signal import ComponentSignalSnapshotModel
from app.schemas.alert.constants import (
    AlertEvaluationModeEnum,
    AlertOperatorEnum,
    AlertValueTypeEnum,
)
from app.schemas.alert.source import AlertEnumOption
from app.schemas.component_signal import (
    ComponentSignalBatchRequest,
    ComponentSignalDefinition,
    ComponentSignalReport,
    ComponentSignalReportResult,
    ComponentSignalResourceRef,
)
from app.service.alert.observation_inbox import AlertObservationInboxService
from app.service.component_signal.ingestion import ComponentSignalIngestionService
from app.service.component_signal.registry import ComponentSignalDefinitionRegistry


@pytest.fixture(autouse=True)
def initialized_snapshot_model(monkeypatch):
    """为不连接 MongoDB 的模型构造提供最小集合占位。"""
    monkeypatch.setattr(
        ComponentSignalSnapshotModel,
        "get_motor_collection",
        staticmethod(lambda: SimpleNamespace()),
    )


def context(component_id: str = "component-a") -> ComponentContext:
    """构造绑定运行实例的组件身份。"""
    return ComponentContext(
        action_id="action-1",
        node_instance_id="node-1",
        component_run_id="run-1",
        component_id=component_id,
        scopes=frozenset({"sdk:signals"}),
        claims={},
    )


def service() -> ComponentSignalIngestionService:
    """构造仅允许测试组件上报的枚举信号服务。"""
    registry = ComponentSignalDefinitionRegistry()
    registry.register(
        ComponentSignalDefinition(
            definition_key="test.health",
            source_key="test.component",
            module_key="test",
            module_name="测试组件",
            resource_type="test_resource",
            resource_name="测试资源",
            field_key="health",
            field_name="健康状态",
            signal_key="health_status",
            value_type=AlertValueTypeEnum.ENUM,
            enum_options=[
                AlertEnumOption(value="normal", label="正常"),
                AlertEnumOption(value="abnormal", label="异常"),
            ],
            supported_operators=[
                AlertOperatorEnum.EQ,
                AlertOperatorEnum.NE,
            ],
            supported_evaluation_modes=[
                AlertEvaluationModeEnum.REALTIME,
                AlertEvaluationModeEnum.HYBRID,
            ],
            allowed_component_ids={"component-a", "component-b"},
            allowed_metadata_keys={"message"},
        )
    )
    return ComponentSignalIngestionService(registry)


def report(
    report_id: str,
    *,
    value: str = "abnormal",
    observed_at: datetime | None = None,
    metadata: dict | None = None,
) -> ComponentSignalReport:
    """构造测试组件信号报告。"""
    return ComponentSignalReport(
        report_id=report_id,
        definition_key="test.health",
        definition_version=1,
        resource=ComponentSignalResourceRef(
            resource_id="resource-1",
            resource_name="资源一",
        ),
        value=value,
        observed_at=observed_at or datetime.now(timezone.utc),
        source_event_id="event-1",
        metadata=metadata or {},
    )


@pytest.mark.asyncio
async def test_ingestion_accepts_then_deduplicates_same_report(
    monkeypatch,
) -> None:
    storage = {}

    async def find_one(query):
        return storage.get(query["_id"])

    async def insert(snapshot):
        storage[snapshot.id] = snapshot

    monkeypatch.setattr(
        ComponentSignalSnapshotModel,
        "find_one",
        staticmethod(find_one),
    )
    monkeypatch.setattr(ComponentSignalSnapshotModel, "insert", insert)
    publish = AsyncMock(return_value=True)
    monkeypatch.setattr(AlertObservationInboxService, "publish", publish)
    current_service = service()
    current_report = report("report-1")

    accepted = await current_service.ingest_report(context(), current_report)
    duplicate = await current_service.ingest_report(context(), current_report)

    assert accepted.status == "accepted"
    assert duplicate.status == "duplicate"
    assert duplicate.observation_id == accepted.observation_id
    assert storage[next(iter(storage))].version == 1
    assert publish.await_count == 2
    assert (
        publish.await_args_list[0].args[0].observation_id
        == publish.await_args_list[1].args[0].observation_id
    )


@pytest.mark.asyncio
async def test_ingestion_retry_completes_inbox_after_snapshot_failure(
    monkeypatch,
) -> None:
    storage = {}

    async def find_one(query):
        return storage.get(query["_id"])

    async def insert(snapshot):
        storage[snapshot.id] = snapshot

    monkeypatch.setattr(
        ComponentSignalSnapshotModel,
        "find_one",
        staticmethod(find_one),
    )
    monkeypatch.setattr(ComponentSignalSnapshotModel, "insert", insert)
    publish = AsyncMock(
        side_effect=[RuntimeError("Inbox 暂不可用"), True]
    )
    monkeypatch.setattr(AlertObservationInboxService, "publish", publish)
    current_service = service()
    current_report = report("report-retry")

    with pytest.raises(RuntimeError, match="Inbox"):
        await current_service.ingest_report(context(), current_report)
    retried = await current_service.ingest_report(context(), current_report)

    assert retried.status == "duplicate"
    assert publish.await_count == 2


@pytest.mark.asyncio
async def test_old_duplicate_still_retries_inbox(monkeypatch) -> None:
    old_report = report(
        "report-old-retry",
        observed_at=datetime.now(timezone.utc) - timedelta(days=2),
    )
    snapshot = ComponentSignalSnapshotModel(
        id="snapshot-1",
        definition_key="test.health",
        definition_version=1,
        source_schema_version=1,
        source_key="test.component",
        resource_type="test_resource",
        resource_id="resource-1",
        resource_name="资源一",
        field_key="health",
        signal_key="health_status",
        value_type=AlertValueTypeEnum.ENUM,
        current_value="abnormal",
        last_report_id=old_report.report_id,
        last_observation_id="observation-old",
        last_source_event_id="event-1",
        last_component_id="component-a",
        last_component_run_id="run-1",
        last_action_id="action-1",
        last_node_instance_id="node-1",
        observed_at=old_report.observed_at,
        metadata={},
    )
    monkeypatch.setattr(
        ComponentSignalSnapshotModel,
        "find_one",
        AsyncMock(return_value=snapshot),
    )
    publish = AsyncMock(return_value=True)
    monkeypatch.setattr(AlertObservationInboxService, "publish", publish)

    result = await service().ingest_report(context(), old_report)

    assert result.status == "duplicate"
    publish.assert_awaited_once()


@pytest.mark.asyncio
async def test_ingestion_rejects_stale_and_unauthorized_reports(
    monkeypatch,
) -> None:
    newer = report("report-new", observed_at=datetime.now(timezone.utc))
    snapshot = ComponentSignalSnapshotModel(
        id="snapshot-1",
        definition_key="test.health",
        definition_version=1,
        source_schema_version=1,
        source_key="test.component",
        resource_type="test_resource",
        resource_id="resource-1",
        resource_name="资源一",
        field_key="health",
        signal_key="health_status",
        value_type=AlertValueTypeEnum.ENUM,
        current_value="abnormal",
        last_report_id=newer.report_id,
        last_observation_id="observation-new",
        last_source_event_id="event-1",
        last_component_id="component-a",
        last_component_run_id="run-1",
        last_action_id="action-1",
        last_node_instance_id="node-1",
        observed_at=newer.observed_at,
        metadata={},
    )
    monkeypatch.setattr(
        ComponentSignalSnapshotModel,
        "find_one",
        AsyncMock(return_value=snapshot),
    )
    monkeypatch.setattr(
        AlertObservationInboxModel,
        "find_one",
        AsyncMock(return_value=None),
    )
    current_service = service()
    stale = await current_service.ingest_report(
        context(),
        report(
            "report-old",
            observed_at=newer.observed_at - timedelta(seconds=1),
        ),
    )

    assert stale.status == "stale"
    with pytest.raises(PermissionError, match="无权上报"):
        await current_service.ingest_report(
            context("component-x"),
            report("report-x"),
        )


@pytest.mark.asyncio
async def test_older_report_is_duplicate_when_inbox_already_contains_it(
    monkeypatch,
) -> None:
    observed_at = datetime.now(timezone.utc)
    older_report = report(
        "report-a",
        observed_at=observed_at,
    )
    newer_snapshot = ComponentSignalSnapshotModel(
        id="snapshot-1",
        definition_key="test.health",
        definition_version=1,
        source_schema_version=1,
        source_key="test.component",
        resource_type="test_resource",
        resource_id="resource-1",
        resource_name="资源一",
        field_key="health",
        signal_key="health_status",
        value_type=AlertValueTypeEnum.ENUM,
        current_value="normal",
        last_report_id="report-b",
        last_observation_id="observation-b",
        last_source_event_id="event-2",
        last_component_id="component-b",
        last_component_run_id="run-2",
        last_action_id="action-2",
        last_node_instance_id="node-2",
        observed_at=older_report.observed_at,
        metadata={},
        version=2,
    )
    older_snapshot = newer_snapshot.model_copy(
        update={
            "current_value": "abnormal",
            "last_report_id": older_report.report_id,
            "last_observation_id": "observation-a",
            "last_source_event_id": older_report.source_event_id,
        }
    )
    monkeypatch.setattr(
        ComponentSignalSnapshotModel,
        "find_one",
        AsyncMock(return_value=newer_snapshot),
    )
    monkeypatch.setattr(
        AlertObservationInboxModel,
        "find_one",
        AsyncMock(
            return_value=SimpleNamespace(
                observation=(
                    ComponentSignalIngestionService._observation_from_snapshot(
                        older_snapshot
                    )
                )
            )
        ),
    )

    result = await service().ingest_report(context(), older_report)

    assert result.status == "duplicate"
    assert result.observation_id is not None


@pytest.mark.asyncio
async def test_ingestion_rejects_invalid_value_and_sensitive_metadata() -> None:
    current_service = service()

    with pytest.raises(ValueError, match="枚举值未注册"):
        await current_service.ingest_report(
            context(),
            report("report-invalid", value="unknown"),
        )
    with pytest.raises(ValueError, match="未允许字段"):
        await current_service.ingest_report(
            context(),
            report(
                "report-secret",
                metadata={"password": "secret"},
            ),
        )


@pytest.mark.asyncio
async def test_batch_uses_same_generic_channel_for_multiple_components(
    monkeypatch,
) -> None:
    current_service = service()

    async def ingest(_context, item):
        return ComponentSignalReportResult(
            report_id=item.report_id,
            status="accepted",
        )

    monkeypatch.setattr(current_service, "ingest_report", ingest)
    monkeypatch.setattr(current_service, "enforce_rate_limit", AsyncMock())
    batch = ComponentSignalBatchRequest(
        reports=[
            report("a"),
            report("b", value="normal"),
        ]
    )

    result_a = await current_service.ingest_batch(context("component-a"), batch)
    result_b = await current_service.ingest_batch(context("component-b"), batch)

    assert len(result_a.results) == 2
    assert len(result_b.results) == 2
