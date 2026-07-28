"""行动组件 SDK Reference 协议契约测试。"""

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from app.api.v1.endpoints.action import sdk as sdk_endpoint
from app.models.action.action import ActionConfigIOModel, ActionInstanceNodeModel
from app.schemas.action.reference import ReferenceQueueBinding
from app.schemas.constants import ActionConfigIOTypeEnum


class _FindMany:
    def __init__(self, values):
        self.values = values

    async def to_list(self):
        return self.values


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
