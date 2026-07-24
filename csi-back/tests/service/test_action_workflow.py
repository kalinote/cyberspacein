from datetime import datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.models.action.action import ActionInstanceModel, ActionInstanceNodeModel
from app.schemas.action.node import ActionNode
from app.schemas.constants import ActionInstanceNodeStatusEnum, ActionNodeTypeEnum
from app.service import action as action_service
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


def test_action_node_uses_default_component_command():
    node = ActionNode(
        name="分析节点",
        description="测试默认运行命令",
        type=ActionNodeTypeEnum.PROCESSOR,
        version="1.0.0",
        handles=[],
        inputs=[],
        related_components=[],
    )

    assert node.command == "csi-component"
    assert node.command_args == ["main:run"]


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
    monkeypatch.setattr(
        ActionInstanceModel,
        "find_one",
        AsyncMock(
            return_value=SimpleNamespace(
                status=action_service.ActionFlowStatusEnum.RUNNING
            )
        ),
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
    monkeypatch.setattr(
        ActionInstanceModel,
        "find_one",
        AsyncMock(
            return_value=SimpleNamespace(
                status=action_service.ActionFlowStatusEnum.RUNNING
            )
        ),
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


@pytest.mark.asyncio
async def test_run_node_dispatches_custom_command_and_keeps_bootstrap_value(monkeypatch):
    node = SimpleNamespace(
        id="node-instance-1",
        node_id="start-node",
        definition_id="definition-1",
        reference_queues={},
        status=ActionInstanceNodeStatusEnum.READY,
        start_at=datetime.now(),
        save=AsyncMock(),
    )
    node_definition = SimpleNamespace(
        command="python",
        command_args=["worker.py"],
        related_components=["component-1"],
        component_timeouts={"component-1": 30},
    )
    action = SimpleNamespace(
        id="action-1",
        blueprint_id="blueprint-1",
        schedule_priority=5,
        status=action_service.ActionFlowStatusEnum.RUNNING,
    )
    find_one_calls = 0

    def find_one(_query):
        nonlocal find_one_calls
        find_one_calls += 1
        if find_one_calls in {2, 4}:
            return _FindOne(modified_count=1)
        return _FindOne(node)

    monkeypatch.setattr(ActionInstanceNodeModel, "find_one", staticmethod(find_one))
    monkeypatch.setattr(
        ActionInstanceNodeModel,
        "find",
        staticmethod(lambda _query: _FindMany([])),
    )
    monkeypatch.setattr(
        ActionInstanceModel,
        "find_one",
        AsyncMock(return_value=action),
    )
    monkeypatch.setattr(
        ActionInstanceService,
        "get_node_definition",
        AsyncMock(return_value=node_definition),
    )
    monkeypatch.setattr(
        ActionInstanceService,
        "find_all_previous_nodes",
        AsyncMock(return_value=[]),
    )
    monkeypatch.setattr(
        ActionInstanceService,
        "get_blueprint",
        AsyncMock(return_value=SimpleNamespace(graph=SimpleNamespace(edges=[]))),
    )
    component_run = SimpleNamespace(id="component-run-1", insert=AsyncMock())
    component_run_factory = MagicMock(return_value=component_run)
    monkeypatch.setattr(action_service, "ComponentRunModel", component_run_factory)
    monkeypatch.setattr(
        action_service,
        "issue_component_bootstrap",
        AsyncMock(return_value="-bootstrap"),
    )
    dispatch = AsyncMock(return_value=True)
    monkeypatch.setattr(action_service, "dispatch_component_run", dispatch)

    assert await ActionInstanceService.run_node(node.id, action.id) is True
    assert component_run_factory.call_args.kwargs["timeout_seconds"] == 30
    assert dispatch.await_args.args[1] == "python"
    command_args = dispatch.await_args.args[2]
    assert "worker.py" in command_args
    assert "--component-bootstrap=-bootstrap" in command_args
    assert "--component-bootstrap" not in command_args
