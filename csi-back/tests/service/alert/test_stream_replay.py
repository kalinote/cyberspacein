from unittest.mock import AsyncMock

import pytest

import app.service.alert.stream as stream_module
from app.service.alert.stream import AlertStreamService


@pytest.mark.asyncio
async def test_replay_status_detects_expired_and_invalid_cursor(monkeypatch):
    redis = AsyncMock()
    redis.xrange.return_value = [("100-0", {})]
    redis.xrevrange.return_value = [("200-5", {})]
    monkeypatch.setattr(stream_module, "get_redis", lambda: redis)

    assert await AlertStreamService.replay_status("99-9") == (
        True,
        "100-0",
        "200-5",
    )
    assert await AlertStreamService.replay_status("invalid") == (
        True,
        "100-0",
        "200-5",
    )
    assert await AlertStreamService.replay_status("100-0") == (
        False,
        "100-0",
        "200-5",
    )


@pytest.mark.asyncio
async def test_zero_cursor_replays_current_retention_window(monkeypatch):
    redis = AsyncMock()
    redis.xrange.return_value = [("100-0", {})]
    redis.xrevrange.return_value = [("200-5", {})]
    monkeypatch.setattr(stream_module, "get_redis", lambda: redis)

    assert await AlertStreamService.replay_status("0-0") == (
        False,
        "100-0",
        "200-5",
    )
