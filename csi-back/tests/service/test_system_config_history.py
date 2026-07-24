from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace

import pytest

from app.core.system_config import CONFIG_FIELDS, SystemConfigManager
from app.service.system_config_history import (
    HistoryVersionConflictError,
    SystemConfigHistoryService,
)


class FakeManager:
    def __init__(self, events):
        self.events = events
        self.acknowledged = []
        self.status = None

    def outbox(self):
        return list(self.events)

    def ack_outbox(self, ids):
        self.acknowledged.extend(ids)

    def set_history_sync_status(self, status):
        self.status = status


@pytest.mark.asyncio
async def test_flush_outbox_is_idempotent_and_acknowledges_after_write(monkeypatch):
    manager = FakeManager([
        {"outbox_id": "one", "kind": "version"},
        {"outbox_id": "two", "kind": "status"},
    ])
    written = []

    async def apply(event):
        written.append(event["outbox_id"])

    async def reconcile(_):
        return "ok"

    monkeypatch.setattr(SystemConfigHistoryService, "_apply_event", staticmethod(apply))
    monkeypatch.setattr(SystemConfigHistoryService, "reconcile", staticmethod(reconcile))

    result = await SystemConfigHistoryService.flush_outbox(manager)

    assert result == "ok"
    assert written == ["one", "two"]
    assert manager.acknowledged == ["one", "two"]


@pytest.mark.asyncio
async def test_flush_outbox_keeps_events_when_mongodb_write_fails(monkeypatch):
    manager = FakeManager([{"outbox_id": "one", "kind": "version"}])

    async def fail(_):
        raise RuntimeError("mongo unavailable")

    monkeypatch.setattr(SystemConfigHistoryService, "_apply_event", staticmethod(fail))

    result = await SystemConfigHistoryService.flush_outbox(manager)

    assert result == "pending"
    assert manager.acknowledged == []
    assert manager.status == "pending"


@pytest.mark.asyncio
async def test_flush_outbox_marks_version_collision_as_conflict(monkeypatch):
    manager = FakeManager([{"outbox_id": "one", "kind": "version"}])

    async def fail(_):
        raise HistoryVersionConflictError("版本冲突")

    monkeypatch.setattr(SystemConfigHistoryService, "_apply_event", staticmethod(fail))

    result = await SystemConfigHistoryService.flush_outbox(manager)

    assert result == "conflict"
    assert manager.acknowledged == []
    assert manager.status == "conflict"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("file_version", "database_version", "expected_version"),
    [(0, 5, 6), (7, 5, 8)],
)
async def test_coordination_preview_proposes_highest_version_and_masks_secrets(
    monkeypatch,
    file_version,
    database_version,
    expected_version,
):
    file_snapshot = {
        meta.key: None for meta in CONFIG_FIELDS if meta.apply_mode != "readonly"
    }
    file_snapshot["RRF_K"] = 60
    file_snapshot["CRAWLAB_TOKEN"] = "file-secret"
    database_snapshot = dict(file_snapshot)
    database_snapshot["RRF_K"] = 90
    database_snapshot["CRAWLAB_TOKEN"] = "database-secret"
    file_checksum = SystemConfigManager._checksum(file_snapshot)
    database_checksum = SystemConfigManager._checksum(database_snapshot)

    class CoordinationManager(FakeManager):
        def __init__(self):
            super().__init__([])

        def state(self):
            return {"version": file_version}

        def desired_snapshot_checksum(self):
            return file_checksum

        def coordination_source(self):
            return {
                "version": file_version,
                "signature": "file-signature",
                "active_checksum": file_checksum,
                "desired_checksum": file_checksum,
                "restart_required": False,
                "pending_version": None,
                "pending_status": None,
                "outbox_ids": [],
                "active_snapshot": file_snapshot,
                "desired_snapshot": file_snapshot,
            }

        _checksum = staticmethod(SystemConfigManager._checksum)

    latest_document = SimpleNamespace(
        version=database_version,
        event_id="database-event",
        status="applied",
        snapshot_checksum=database_checksum,
        snapshot=database_snapshot,
        operation="cancel_pending",
        created_at=datetime.now(timezone.utc),
    )

    async def latest():
        return latest_document

    monkeypatch.setattr(SystemConfigHistoryService, "latest_version", staticmethod(latest))

    preview = await SystemConfigHistoryService.coordination_preview(
        CoordinationManager()
    )

    assert preview["proposed_version"] == expected_version
    assert {item["key"] for item in preview["differences"]} == {
        "RRF_K",
        "CRAWLAB_TOKEN",
    }
    assert "file-secret" not in str(preview)
    assert "database-secret" not in str(preview)
