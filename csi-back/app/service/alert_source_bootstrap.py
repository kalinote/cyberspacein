from app.service.action.alert_source import ActionInstanceAlertSource
from app.service.alert.registry import alert_source_registry
from app.service.component_signal.bootstrap import register_component_signal_sources


def register_builtin_alert_sources() -> None:
    """幂等注册当前应用内置业务模块的告警源。"""
    alert_source_registry.register_or_replace(ActionInstanceAlertSource())
    register_component_signal_sources()
