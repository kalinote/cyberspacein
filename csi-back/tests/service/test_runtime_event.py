from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from app.models.action.node_execution import ActionNodeExecutionModel
from app.models.runtime_event import RuntimeDomainEventModel
from app.schemas.constants import (
    ActionInstanceNodeStatusEnum,
    ActionVisibilityEnum,
)
from app.service.action import ActionInstanceService
from app.service.runtime_event import RuntimeDomainEventService


class _Query:
    def __init__(self, values):
        self.values = values

    def sort(self, *_args):
        return self

    def limit(self, *_args):
        return self

    async def to_list(self):
        return self.values


@pytest.mark.asyncio
async def test_embedded_action_terminal_event_is_published_and_consumed(
    monkeypatch,
) -> None:
    inserted = []

    async def insert(event):
        inserted.append(event)

    monkeypatch.setattr(
        RuntimeDomainEventModel,
        "get_motor_collection",
        classmethod(lambda _cls: object()),
    )
    monkeypatch.setattr(RuntimeDomainEventModel, "insert", insert)
    action = SimpleNamespace(
        id="child-action-1",
        visibility=ActionVisibilityEnum.EMBEDDED,
        parent_action_id="parent-action-1",
        parent_node_instance_id="parent-node-1",
        parent_node_execution_id="parent-execution-1",
    )

    published = await RuntimeDomainEventService.publish_action_terminal(
        action,
        "completed",
    )

    assert published is True
    stored_event = inserted[0]
    assert stored_event.id == "action.terminal:child-action-1"
    assert (
        stored_event.payload["parent_node_execution_id"]
        == "parent-execution-1"
    )

    event = SimpleNamespace(
        topic=stored_event.topic,
        aggregate_id=stored_event.aggregate_id,
        payload=stored_event.payload,
        update=AsyncMock(),
    )
    execution = SimpleNamespace(
        status=ActionInstanceNodeStatusEnum.RUNNING,
    )
    monkeypatch.setattr(
        RuntimeDomainEventModel,
        "find",
        staticmethod(lambda _query: _Query([event])),
    )
    monkeypatch.setattr(
        ActionNodeExecutionModel,
        "find_one",
        AsyncMock(return_value=execution),
    )
    reconcile = AsyncMock(return_value=True)
    monkeypatch.setattr(
        ActionInstanceService,
        "_reconcile_node_execution",
        reconcile,
    )

    consumed = await ActionInstanceService.consume_runtime_events()

    assert consumed == 1
    reconcile.assert_awaited_once_with(execution)
    event.update.assert_awaited_once_with(
        {"$addToSet": {"processed_by": "action-node-executor"}}
    )


@pytest.mark.asyncio
async def test_embedded_terminal_event_stays_pending_until_parent_reconciles(
    monkeypatch,
) -> None:
    event = SimpleNamespace(
        payload={"parent_node_execution_id": "parent-execution-1"},
        update=AsyncMock(),
    )
    execution = SimpleNamespace(status=ActionInstanceNodeStatusEnum.RUNNING)
    monkeypatch.setattr(
        RuntimeDomainEventModel,
        "find",
        staticmethod(lambda _query: _Query([event])),
    )
    monkeypatch.setattr(
        ActionNodeExecutionModel,
        "find_one",
        AsyncMock(return_value=execution),
    )
    monkeypatch.setattr(
        ActionInstanceService,
        "_reconcile_node_execution",
        AsyncMock(return_value=False),
    )

    consumed = await ActionInstanceService.consume_runtime_events()

    assert consumed == 0
    event.update.assert_not_awaited()
