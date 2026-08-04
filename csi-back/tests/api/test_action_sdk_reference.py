"""行动组件 SDK Reference 协议契约测试。"""

from datetime import datetime, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from app.api.v1.endpoints.action import sdk as sdk_endpoint
from app.models.action.action import ActionConfigIOModel, ActionInstanceNodeModel
from app.models.action.component_run import ComponentRunModel
from app.schemas.action.reference import ReferenceQueueBinding
from app.schemas.action.sdk import SDKHeartbeatRequest
from app.schemas.constants import ActionConfigIOTypeEnum, ComponentRunStatusEnum


class _FindMany:
    def __init__(self, values):
        self.values = values

    async def to_list(self):
        return self.values


class _FindOne:
    def __init__(self, value=None, *, modified_count=0, updates=None):
        self.value = value
        self.modified_count = modified_count
        self.updates = updates

    def __await__(self):
        async def resolve():
            return self.value

        return resolve().__await__()

    async def update(self, payload):
        if self.updates is not None:
            self.updates.append(payload)
        return SimpleNamespace(modified_count=self.modified_count)


@pytest.mark.asyncio
async def test_token_exchange_returns_component_attempt(monkeypatch):
    request = SimpleNamespace(
        state=SimpleNamespace(
            component_bootstrap_context=SimpleNamespace(
                action_id="action-1",
                node_instance_id="node-1",
            )
        )
    )
    monkeypatch.setattr(
        sdk_endpoint.ComponentRunModel,
        "find_one",
        AsyncMock(return_value=SimpleNamespace(attempt=3)),
    )
    monkeypatch.setattr(
        sdk_endpoint,
        "create_component_token",
        lambda *_args: "component-token",
    )

    response = await sdk_endpoint.exchange_component_token("run-1", request)

    assert response.data == {
        "component_token": "component-token",
        "attempt": 3,
    }


@pytest.mark.asyncio
async def test_heartbeat_renews_lease_with_atomic_active_status_guard(monkeypatch):
    before = datetime.now()
    initial = SimpleNamespace(
        id="run-1",
        action_id="action-1",
        node_instance_id="node-1",
        status=ComponentRunStatusEnum.RUNNING,
        cancel_requested=False,
        lease_expires_at=before + timedelta(seconds=10),
    )
    updated = SimpleNamespace(
        **initial.__dict__,
        progress=40,
    )
    queries = []
    updates = []
    find_one_calls = 0

    def find_run(query):
        nonlocal find_one_calls
        find_one_calls += 1
        queries.append(query)
        if find_one_calls == 2:
            return _FindOne(modified_count=1, updates=updates)
        return _FindOne(initial if find_one_calls == 1 else updated)

    monkeypatch.setattr(ComponentRunModel, "find_one", staticmethod(find_run))
    monkeypatch.setattr(
        ComponentRunModel,
        "find",
        staticmethod(lambda _query: _FindMany([updated])),
    )
    update_progress = AsyncMock()
    monkeypatch.setattr(
        sdk_endpoint.ActionInstanceService,
        "update_progress",
        update_progress,
    )
    monkeypatch.setattr(
        sdk_endpoint,
        "create_component_token",
        lambda *_args: "refreshed-token",
    )

    response = await sdk_endpoint.heartbeat(
        "run-1",
        SDKHeartbeatRequest(progress=40, message="运行中"),
    )

    assert response.data.command == "continue"
    assert response.data.component_token == "refreshed-token"
    assert queries[1]["status"]["$in"] == [
        ComponentRunStatusEnum.DISPATCHED,
        ComponentRunStatusEnum.RUNNING,
    ]
    assert updates[0]["$set"]["progress"] == 40
    lease_expires_at = updates[0]["$set"]["lease_expires_at"]
    assert timedelta(seconds=29) <= lease_expires_at - before <= timedelta(seconds=31)
    update_progress.assert_awaited_once_with("node-1", 40)


@pytest.mark.asyncio
async def test_heartbeat_cannot_resurrect_terminal_component(monkeypatch):
    now = datetime.now()
    active = SimpleNamespace(
        id="run-1",
        status=ComponentRunStatusEnum.RUNNING,
        lease_expires_at=now + timedelta(seconds=10),
    )
    terminal = SimpleNamespace(
        id="run-1",
        status=ComponentRunStatusEnum.TIMED_OUT,
        lease_expires_at=now,
    )
    find_one_calls = 0

    def find_run(_query):
        nonlocal find_one_calls
        find_one_calls += 1
        if find_one_calls == 1:
            return _FindOne(active)
        if find_one_calls == 2:
            return _FindOne(modified_count=0)
        return _FindOne(terminal)

    monkeypatch.setattr(ComponentRunModel, "find_one", staticmethod(find_run))
    update_progress = AsyncMock()
    monkeypatch.setattr(
        sdk_endpoint.ActionInstanceService,
        "update_progress",
        update_progress,
    )

    response = await sdk_endpoint.heartbeat(
        "run-1",
        SDKHeartbeatRequest(progress=40, message="运行中"),
    )

    assert response.data.command == "cancel"
    update_progress.assert_not_awaited()


@pytest.mark.asyncio
async def test_build_io_exposes_reference_input_stream_contract(monkeypatch):
    binding = ReferenceQueueBinding(
        edge_id="edge-a",
        stream_id="stream-a",
        queue_name="queue-a",
        owner_action_id="action-1",
        source_node_id="source",
        source_port_id="out",
        target_node_id="target",
        target_port_id="in",
        expected_producer_ids=["run-a", "run-b"],
    )
    source = SimpleNamespace(reference_queue_bindings={"edge-a": binding})
    target = SimpleNamespace(
        id="target-instance",
        action_id="action-1",
        node_id="target",
        inputs={
            "in": ActionConfigIOModel(
                type=ActionConfigIOTypeEnum.REFERENCE,
                key="items",
                value="queue-a",
            )
        },
        outputs={},
        reference_queue_bindings={},
    )
    monkeypatch.setattr(
        ActionInstanceNodeModel,
        "find",
        staticmethod(lambda _query: _FindMany([source, target])),
    )
    monkeypatch.setattr(
        sdk_endpoint.ActionInstanceModel,
        "find_one",
        AsyncMock(return_value=None),
    )

    inputs, outputs = await sdk_endpoint._build_io(target)

    assert outputs == {}
    assert inputs["items"] == {
        "type": "reference",
        "value": "queue-a",
        "streams": [
            {
                "queue_name": "queue-a",
                "stream_id": "stream-a",
                "protocol": "eos-v1",
                "expected_producer_ids": ["run-a", "run-b"],
            }
        ],
    }


@pytest.mark.asyncio
async def test_build_io_keeps_value_list_without_queue_lookup(monkeypatch):
    target = SimpleNamespace(
        id="target-instance",
        action_id="action-1",
        node_id="target",
        inputs={
            "keywords": ActionConfigIOModel(
                type=ActionConfigIOTypeEnum.VALUE,
                key="keywords",
                value=["莫菁"],
            ),
            "platforms": ActionConfigIOModel(
                type=ActionConfigIOTypeEnum.VALUE,
                key="platforms",
                value=["javbus"],
            ),
        },
        outputs={},
        reference_queue_bindings={},
    )
    find_nodes = AsyncMock()
    monkeypatch.setattr(ActionInstanceNodeModel, "find", find_nodes)
    monkeypatch.setattr(
        sdk_endpoint.ActionInstanceModel,
        "find_one",
        AsyncMock(return_value=None),
    )

    inputs, outputs = await sdk_endpoint._build_io(target)

    assert outputs == {}
    assert inputs == {
        "keywords": {"type": "value", "value": ["莫菁"]},
        "platforms": {"type": "value", "value": ["javbus"]},
    }
    find_nodes.assert_not_called()


@pytest.mark.asyncio
async def test_build_io_exposes_all_reference_input_streams(monkeypatch):
    bindings = [
        ReferenceQueueBinding(
            edge_id=f"edge-{suffix}",
            stream_id=f"stream-{suffix}",
            queue_name=f"queue-{suffix}",
            owner_action_id="action-1",
            source_node_id=f"source-{suffix}",
            source_port_id="out",
            target_node_id="target",
            target_port_id="in",
            expected_producer_ids=[f"run-{suffix}"],
        )
        for suffix in ("a", "b")
    ]
    source = SimpleNamespace(
        reference_queue_bindings={
            binding.edge_id: binding for binding in bindings
        }
    )
    target = SimpleNamespace(
        id="target-instance",
        action_id="action-1",
        node_id="target",
        inputs={
            "in": ActionConfigIOModel(
                type=ActionConfigIOTypeEnum.REFERENCE,
                key="items",
                value=["queue-a", "queue-b"],
            )
        },
        outputs={},
        reference_queue_bindings={},
    )
    monkeypatch.setattr(
        ActionInstanceNodeModel,
        "find",
        staticmethod(lambda _query: _FindMany([source, target])),
    )
    monkeypatch.setattr(
        sdk_endpoint.ActionInstanceModel,
        "find_one",
        AsyncMock(return_value=None),
    )

    inputs, _ = await sdk_endpoint._build_io(target)

    assert inputs["items"]["value"] == ["queue-a", "queue-b"]
    assert [stream["queue_name"] for stream in inputs["items"]["streams"]] == [
        "queue-a",
        "queue-b",
    ]
