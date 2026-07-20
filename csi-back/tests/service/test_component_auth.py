from unittest.mock import AsyncMock

import pytest

from app.core.exceptions import UnauthorizedException
from app.service import component_auth


class FakeRedis:
    def __init__(self):
        self.values: dict[str, str] = {}
        self.set = AsyncMock(side_effect=self._set)

    async def _set(self, key: str, value: str, **_: object) -> bool:
        self.values[key] = value
        return True

    async def eval(self, _: str, __: int, key: str):
        return self.values.pop(key, None)


@pytest.mark.asyncio
async def test_bootstrap_is_hashed_bound_and_one_time(monkeypatch: pytest.MonkeyPatch) -> None:
    redis = FakeRedis()
    monkeypatch.setattr(component_auth, "get_redis", lambda: redis)
    bootstrap = await component_auth.issue_component_bootstrap("action-1", "node-1", "run-1")
    assert bootstrap not in " ".join(redis.values.keys())
    assert bootstrap not in " ".join(redis.values.values())

    context = await component_auth.consume_component_bootstrap(bootstrap, "run-1")
    assert context.action_id == "action-1"
    assert context.node_instance_id == "node-1"
    assert context.component_run_id == "run-1"
    with pytest.raises(UnauthorizedException):
        await component_auth.consume_component_bootstrap(bootstrap, "run-1")


@pytest.mark.asyncio
async def test_bootstrap_rejects_cross_node(monkeypatch: pytest.MonkeyPatch) -> None:
    redis = FakeRedis()
    monkeypatch.setattr(component_auth, "get_redis", lambda: redis)
    bootstrap = await component_auth.issue_component_bootstrap("action-1", "node-1", "run-1")
    with pytest.raises(UnauthorizedException):
        await component_auth.consume_component_bootstrap(bootstrap, "run-2")


@pytest.mark.asyncio
async def test_bootstrap_retries_an_unexpected_key_collision(monkeypatch: pytest.MonkeyPatch) -> None:
    redis = FakeRedis()
    redis.set = AsyncMock(side_effect=[False, True])
    monkeypatch.setattr(component_auth, "get_redis", lambda: redis)
    bootstrap = await component_auth.issue_component_bootstrap("action-1", "node-1", "run-1")
    assert bootstrap
    assert redis.set.await_count == 2
