from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from beanie import Document
from pydantic import BaseModel, Field
from pymongo import ASCENDING, DESCENDING, IndexModel


def _now() -> datetime:
    return datetime.now(timezone.utc)


class SystemConfigChangeModel(BaseModel):
    key: str
    apply_mode: str
    before: Any = None
    after: Any = None
    sensitive: bool = False


class SystemConfigCoordinationModel(BaseModel):
    file_version: int
    database_version: int
    file_checksum: str
    database_checksum: str
    file_fields: list[str] = Field(default_factory=list)
    database_fields: list[str] = Field(default_factory=list)
    discarded_outbox_ids: list[str] = Field(default_factory=list)


class SystemConfigVersionModel(Document):
    id: str = Field(alias="_id")
    event_id: str
    version: int
    parent_version: int | None = None
    operation: str
    status: str
    changes: list[SystemConfigChangeModel] = Field(default_factory=list)
    snapshot: dict[str, Any] = Field(default_factory=dict)
    snapshot_checksum: str
    created_by: str
    created_at: datetime = Field(default_factory=_now)
    applied_at: datetime | None = None
    boot_id: str | None = None
    restored_from_version: int | None = None
    baseline_fingerprint: str | None = None
    message: str | None = None
    coordination: SystemConfigCoordinationModel | None = None

    class Settings:
        name = "system_config_versions"
        indexes = [
            IndexModel([("version", ASCENDING)], unique=True),
            IndexModel([("event_id", ASCENDING)], unique=True),
            IndexModel([("created_at", DESCENDING)]),
            IndexModel([("status", ASCENDING), ("version", DESCENDING)]),
        ]
