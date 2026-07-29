from app.schemas.alert.source import AlertFieldDescriptor, AlertSourceDescriptor
from app.service.alert.source_contract import AlertSourceProvider


class AlertSourceRegistry:
    """维护当前进程已注册的告警数据源。"""

    def __init__(self) -> None:
        self._providers: dict[str, AlertSourceProvider] = {}

    def register(self, provider: AlertSourceProvider) -> None:
        """注册一个告警源并拒绝重复键。"""
        if not isinstance(provider, AlertSourceProvider):
            raise TypeError("告警源必须实现 AlertSourceProvider")
        descriptor = provider.describe()
        if descriptor.source_key in self._providers:
            raise ValueError(f"告警源已注册: {descriptor.source_key}")
        self._providers[descriptor.source_key] = provider

    def register_or_replace(self, provider: AlertSourceProvider) -> None:
        """注册或替换同键 Provider，供测试和幂等引导使用。"""
        descriptor = provider.describe()
        self._providers[descriptor.source_key] = provider

    def get(self, source_key: str) -> AlertSourceProvider:
        """读取已注册 Provider。"""
        provider = self._providers.get(source_key)
        if provider is None:
            raise KeyError(f"告警源未注册: {source_key}")
        return provider

    def get_descriptor(self, source_key: str) -> AlertSourceDescriptor:
        """读取告警源描述。"""
        return self.get(source_key).describe()

    def get_field(self, source_key: str, field_key: str) -> AlertFieldDescriptor:
        """读取告警源中的指定字段。"""
        descriptor = self.get_descriptor(source_key)
        for field in descriptor.fields:
            if field.field_key == field_key:
                return field
        raise KeyError(f"告警字段未注册: {source_key}.{field_key}")

    def list_descriptors(self) -> list[AlertSourceDescriptor]:
        """按稳定键返回全部告警源。"""
        return [
            self._providers[key].describe()
            for key in sorted(self._providers)
        ]

    def clear(self) -> None:
        """清空注册表，仅供测试隔离。"""
        self._providers.clear()


alert_source_registry = AlertSourceRegistry()
