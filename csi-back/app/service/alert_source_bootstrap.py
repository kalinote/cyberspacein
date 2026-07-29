from app.service.action_alert_source import ActionInstanceAlertSource
from app.service.alert.registry import alert_source_registry


def register_builtin_alert_sources() -> None:
    """幂等注册当前应用内置业务模块的告警源。"""
    alert_source_registry.register_or_replace(ActionInstanceAlertSource())
