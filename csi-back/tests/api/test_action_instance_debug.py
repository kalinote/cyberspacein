from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from fastapi import BackgroundTasks

from app.api.v1.endpoints.action import instance as instance_endpoint
from app.models.action.action import ActionInstanceModel
from app.models.action.blueprint import ActionBlueprintModel
from app.schemas.action.action import StartActionRequest
from app.schemas.general import PageParamsSchema
from app.schemas.constants import ActionFlowStatusEnum
from app.service.action import ActionInstanceService


class _ActionQuery:
    """提供行动列表接口测试所需的最小查询链。"""

    def __init__(self, values):
        self.values = values

    async def count(self):
        return len(self.values)

    def sort(self, *_args):
        return self

    def skip(self, *_args):
        return self

    def limit(self, *_args):
        return self

    async def to_list(self):
        return self.values


def test_start_action_request_defaults_to_normal_mode() -> None:
    request = StartActionRequest(blueprint_id="blueprint-1")

    assert request.debug is False


@pytest.mark.asyncio
async def test_start_action_passes_debug_mode_to_service(monkeypatch) -> None:
    monkeypatch.setattr(
        ActionBlueprintModel,
        "find_one",
        AsyncMock(return_value=SimpleNamespace(id="blueprint-1")),
    )
    init = AsyncMock(return_value=(True, "action-1"))
    monkeypatch.setattr(ActionInstanceService, "init", init)
    background_tasks = BackgroundTasks()

    response = await instance_endpoint.start_action(
        StartActionRequest(blueprint_id="blueprint-1", debug=True),
        background_tasks,
        SimpleNamespace(
            state=SimpleNamespace(
                auth_context=SimpleNamespace(
                    user=SimpleNamespace(id="user-1")
                )
            )
        ),
    )

    assert response.code == 0
    assert response.data.action_id == "action-1"
    assert init.await_args.kwargs == {
        "initiator_user_id": "user-1",
        "debug": True,
    }
    assert init.await_args.args == ("blueprint-1", None)
    assert len(background_tasks.tasks) == 1


@pytest.mark.asyncio
async def test_action_list_returns_debug_flag_with_old_action_fallback(
    monkeypatch,
) -> None:
    common = {
        "status": ActionFlowStatusEnum.RUNNING,
        "start_at": None,
        "paused_at": None,
        "finished_at": None,
        "duration": 0,
        "progress": 0,
        "finished_nodes_instance": [],
        "execution_plan_snapshot": SimpleNamespace(nodes=[]),
        "schedule_id": None,
        "schedule_name": None,
        "schedule_priority": 5,
        "scheduled_for": None,
        "created_at": None,
    }
    actions = [
        SimpleNamespace(id="debug-action", debug=True, **common),
        SimpleNamespace(id="legacy-action", **common),
    ]
    query = _ActionQuery(actions)
    monkeypatch.setattr(
        ActionInstanceModel,
        "find_all",
        staticmethod(lambda: query),
    )
    monkeypatch.setattr(
        ActionInstanceModel,
        "find",
        staticmethod(lambda _query: query),
    )
    monkeypatch.setattr(
        ActionInstanceService,
        "get_action_blueprint",
        AsyncMock(
            return_value=SimpleNamespace(
                name="测试行动",
                description="测试描述",
            )
        ),
    )

    response = await instance_endpoint.get_action_instances(
        PageParamsSchema(page=1, page_size=10)
    )

    assert [item.debug for item in response.items] == [True, False]
