"""组件信号源引导服务。"""

from app.service.alert.registry import alert_source_registry
from app.service.component_signal.definitions import register_builtin_component_signals
from app.service.component_signal.registry import component_signal_definition_registry
from app.service.component_signal.snapshot_provider import (
    ComponentSignalSnapshotProvider,
)


def register_component_signal_sources() -> None:
    """幂等注册组件信号定义及其快照告警源。"""
    register_builtin_component_signals(component_signal_definition_registry)
    for source_key in component_signal_definition_registry.list_source_keys():
        alert_source_registry.register_or_replace(
            ComponentSignalSnapshotProvider(
                source_key,
                component_signal_definition_registry,
            )
        )
