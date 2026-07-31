from datetime import datetime, timezone

from app.models.component_signal import ComponentSignalSnapshotModel
from app.schemas.alert.observation import AlertObservation, AlertObservationPage
from app.schemas.alert.source import AlertSourceDescriptor
from app.service.component_signal.registry import ComponentSignalDefinitionRegistry
from app.utils.id_lib import generate_id


class ComponentSignalSnapshotProvider:
    """将组件最新信号快照作为告警周期补偿数据源。"""

    def __init__(
        self,
        source_key: str,
        registry: ComponentSignalDefinitionRegistry,
    ) -> None:
        self.source_key = source_key
        self.registry = registry

    def describe(self) -> AlertSourceDescriptor:
        """返回当前组件信号告警源描述。"""
        return self.registry.get_source_descriptor(self.source_key)

    async def iter_observations(
        self,
        *,
        field_key: str,
        active_from: datetime,
        cursor: str | None,
        limit: int,
    ) -> AlertObservationPage:
        """分页读取规则范围内的最新组件信号快照。"""
        self.registry.get_source_descriptor(self.source_key)
        if not any(
            item.field_key == field_key
            for item in self.describe().fields
        ):
            raise ValueError(
                f"组件信号告警源不支持字段: {self.source_key}.{field_key}"
            )
        normalized_active_from = (
            active_from.replace(tzinfo=timezone.utc)
            if active_from.tzinfo is None
            else active_from.astimezone(timezone.utc)
        )
        query: dict = {
            "source_key": self.source_key,
            "field_key": field_key,
            "observed_at": {"$gte": normalized_active_from},
        }
        if cursor:
            query["_id"] = {"$gt": cursor}
        snapshots = (
            await ComponentSignalSnapshotModel.find(query)
            .sort("+_id")
            .limit(limit)
            .to_list()
        )
        items = [
            AlertObservation(
                observation_id=generate_id(
                    f"component-snapshot:{snapshot.id}:v{snapshot.version}"
                ),
                source_key=snapshot.source_key,
                resource_type=snapshot.resource_type,
                resource_id=snapshot.resource_id,
                resource_name=snapshot.resource_name,
                resource_url=snapshot.resource_url,
                field_key=snapshot.field_key,
                signal_key=snapshot.signal_key,
                value_type=snapshot.value_type,
                value=snapshot.current_value,
                observed_at=snapshot.observed_at,
                source_event_id=(
                    snapshot.last_source_event_id
                    or f"component-report:{snapshot.last_report_id}"
                ),
                ordering_key=snapshot.last_report_id,
                metadata=snapshot.metadata,
            )
            for snapshot in snapshots
        ]
        return AlertObservationPage(
            items=items,
            next_cursor=snapshots[-1].id if len(snapshots) == limit else None,
        )
