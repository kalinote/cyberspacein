from datetime import datetime
from typing import Protocol, runtime_checkable

from app.schemas.alert.observation import AlertObservationPage
from app.schemas.alert.source import AlertSourceDescriptor


@runtime_checkable
class AlertSourceProvider(Protocol):
    """业务模块接入告警系统所需实现的查询契约。"""

    def describe(self) -> AlertSourceDescriptor:
        """返回模块支持的资源、字段和检测能力。"""
        ...

    async def iter_observations(
        self,
        *,
        field_key: str,
        active_from: datetime,
        cursor: str | None,
        limit: int,
    ) -> AlertObservationPage:
        """分页返回指定字段的当前观测。"""
        ...
