from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from app.schemas.action.log import ComponentLogBatchRequest
from app.service import action_log


class FakeComponentRunQuery:
    def __init__(self) -> None:
        self.update = AsyncMock()


@pytest.mark.asyncio
async def test_log_ingest_uses_event_id_for_idempotency(monkeypatch) -> None:
    query = FakeComponentRunQuery()
    fake_es = SimpleNamespace(
        bulk=AsyncMock(
            return_value={
                "items": [
                    {"create": {"status": 201, "_id": "event-1"}},
                    {"create": {"status": 409, "_id": "event-2"}},
                ]
            }
        )
    )
    monkeypatch.setattr(action_log, "get_es", lambda: fake_es)
    monkeypatch.setattr(
        action_log.ComponentRunModel,
        "find_one",
        lambda *_args, **_kwargs: query,
    )
    component_run = SimpleNamespace(
        id="run-1",
        action_id="action-1",
        node_instance_id="node-1",
        component_id="component-1",
        attempt=1,
    )
    batch = ComponentLogBatchRequest(
        dropped_count=3,
        entries=[
            {
                "event_id": "event-1",
                "sequence": 1,
                "occurred_at": datetime.now(timezone.utc),
                "level": "ERROR",
                "source": "logging",
                "message": "错误",
            },
            {
                "event_id": "event-2",
                "sequence": 2,
                "occurred_at": datetime.now(timezone.utc),
                "level": "INFO",
                "source": "stdout",
                "message": "重复",
            },
        ],
    )

    result = await action_log.ActionLogService.ingest(component_run, batch)

    assert result.accepted == 1
    assert result.duplicated == 1
    operations = fake_es.bulk.await_args.kwargs["operations"]
    assert operations[0]["create"]["_id"] == "event-1"
    update = query.update.await_args.args[0]
    assert update["$inc"] == {"log_count": 1, "error_log_count": 1}
    assert update["$max"] == {"dropped_log_count": 3}


def test_log_cursor_round_trip_and_validation() -> None:
    sort = ["2026-07-20T00:00:00Z", "event-1"]
    cursor = action_log.ActionLogService._encode_cursor(sort)
    assert action_log.ActionLogService._decode_cursor(cursor) == sort
    with pytest.raises(ValueError, match="cursor"):
        action_log.ActionLogService._decode_cursor("invalid")

