from __future__ import annotations

import pytest

from app.service.system_config_history import SystemConfigHistoryService


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
