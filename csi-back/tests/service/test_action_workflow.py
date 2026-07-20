from types import SimpleNamespace

import pytest

from app.models.action.action import ActionInstanceNodeModel
from app.schemas.constants import ActionInstanceNodeStatusEnum
from app.service.action import ActionInstanceService


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


class _FindMany:
    def __init__(self, values):
        self.values = values

    async def to_list(self):
        return self.values


async def _node_definition(_definition_id):
    return SimpleNamespace(id="definition-1")


@pytest.mark.asyncio
async def test_run_node_dispatch_claim_accepts_pending_node(monkeypatch):
    node = SimpleNamespace(
        id="node-instance-1",
        node_id="target-node",
        definition_id="definition-1",
    )
    find_one_queries = []

    def find_one(query):
        find_one_queries.append(query)
        if len(find_one_queries) == 1:
            return _FindOne(node)
        return _FindOne(modified_count=0)

    monkeypatch.setattr(ActionInstanceNodeModel, "find_one", staticmethod(find_one))
    monkeypatch.setattr(
        ActionInstanceNodeModel,
        "find",
        staticmethod(lambda _query: _FindMany([])),
    )
    monkeypatch.setattr(
        ActionInstanceService,
        "get_node_definition",
        staticmethod(_node_definition),
    )

    async def no_previous_nodes(_action_id, _node_id):
        return []

    monkeypatch.setattr(
        ActionInstanceService,
        "find_all_previous_nodes",
        staticmethod(no_previous_nodes),
    )

    assert await ActionInstanceService.run_node("node-instance-1", "action-1") is False
    claim_statuses = find_one_queries[1]["status"]["$in"]
    assert ActionInstanceNodeStatusEnum.PENDING in claim_statuses


@pytest.mark.asyncio
async def test_run_node_can_move_pending_join_node_to_unready(monkeypatch):
    node = SimpleNamespace(
        id="node-instance-1",
        node_id="target-node",
        definition_id="definition-1",
    )
    previous = SimpleNamespace(
        id="previous-instance",
        node_id="previous-node",
        status=ActionInstanceNodeStatusEnum.RUNNING,
    )
    find_one_queries = []
    updates = []

    def find_one(query):
        find_one_queries.append(query)
        if len(find_one_queries) == 1:
            return _FindOne(node)
        return _FindOne(modified_count=1, updates=updates)

    monkeypatch.setattr(ActionInstanceNodeModel, "find_one", staticmethod(find_one))
    monkeypatch.setattr(
        ActionInstanceNodeModel,
        "find",
        staticmethod(lambda _query: _FindMany([previous])),
    )
    monkeypatch.setattr(
        ActionInstanceService,
        "get_node_definition",
        staticmethod(_node_definition),
    )

    async def previous_nodes(_action_id, _node_id):
        return ["previous-node"]

    monkeypatch.setattr(
        ActionInstanceService,
        "find_all_previous_nodes",
        staticmethod(previous_nodes),
    )

    assert await ActionInstanceService.run_node("node-instance-1", "action-1") is False
    waiting_statuses = find_one_queries[1]["status"]["$in"]
    assert ActionInstanceNodeStatusEnum.PENDING in waiting_statuses
    assert updates == [
        {"$set": {"status": ActionInstanceNodeStatusEnum.UNREADY}}
    ]
