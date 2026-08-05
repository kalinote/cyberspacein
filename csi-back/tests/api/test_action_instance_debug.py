from datetime import datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from fastapi import BackgroundTasks

from app.api.v1.endpoints.action import instance as instance_endpoint
from app.models.action.action import ActionInstanceModel
from app.models.action.blueprint import ActionBlueprintModel
from app.schemas.action.action import StartActionRequest
from app.schemas.action.sdk import SDKResultRequest
from app.schemas.general import PageParamsSchema
from app.schemas.constants import ActionFlowStatusEnum, ActionSchedulingModeEnum
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
    assert request.scheduling_mode is None


def test_sdk_result_success_marker_is_backward_compatible() -> None:
    legacy = SDKResultRequest(
        result_id="result-1",
        attempt=1,
        status="success",
    )
    marked = SDKResultRequest(
        result_id="result-2",
        attempt=1,
        status="failed",
        has_successful_result=True,
    )

    assert legacy.has_successful_result is False
    assert marked.has_successful_result is True


@pytest.mark.asyncio
async def test_start_action_passes_debug_mode_to_service(monkeypatch) -> None:
    monkeypatch.setattr(
        ActionBlueprintModel,
        "find_one",
        AsyncMock(return_value=SimpleNamespace(id="blueprint-1")),
    )
    init = AsyncMock(return_value=(True, "action-1"))
    monkeypatch.setattr(ActionInstanceService, "init", init)
    monkeypatch.setattr(
        ActionInstanceModel,
        "find_one",
        AsyncMock(
            return_value=SimpleNamespace(
                execution_plan_snapshot=SimpleNamespace(
                    plan_schema_version=3,
                    scheduling_mode=ActionSchedulingModeEnum.BARRIER,
                )
            )
        ),
    )
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
    assert response.data.scheduling_mode == ActionSchedulingModeEnum.BARRIER
    assert init.await_args.kwargs == {
        "initiator_user_id": "user-1",
        "debug": True,
        "scheduling_mode": None,
    }
    assert init.await_args.args == ("blueprint-1", None)
    assert len(background_tasks.tasks) == 1


@pytest.mark.asyncio
async def test_start_action_response_uses_frozen_plan_mode(monkeypatch) -> None:
    monkeypatch.setattr(
        ActionBlueprintModel,
        "find_one",
        AsyncMock(
            return_value=SimpleNamespace(
                id="blueprint-1",
                default_scheduling_mode=ActionSchedulingModeEnum.BARRIER,
            )
        ),
    )
    monkeypatch.setattr(
        ActionInstanceService,
        "init",
        AsyncMock(return_value=(True, "action-1")),
    )
    monkeypatch.setattr(
        ActionInstanceModel,
        "find_one",
        AsyncMock(
            return_value=SimpleNamespace(
                execution_plan_snapshot=SimpleNamespace(
                    plan_schema_version=3,
                    scheduling_mode=ActionSchedulingModeEnum.STREAMING,
                )
            )
        ),
    )

    response = await instance_endpoint.start_action(
        StartActionRequest(blueprint_id="blueprint-1"),
        BackgroundTasks(),
        SimpleNamespace(state=SimpleNamespace(auth_context=None)),
    )

    assert response.data.scheduling_mode == ActionSchedulingModeEnum.STREAMING


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
    assert [item.scheduling_mode for item in response.items] == [
        ActionSchedulingModeEnum.BARRIER,
        ActionSchedulingModeEnum.BARRIER,
    ]


@pytest.mark.asyncio
async def test_action_list_applies_server_side_history_filters(monkeypatch) -> None:
    captured_queries = []
    query = _ActionQuery([])
    monkeypatch.setattr(
        ActionInstanceModel,
        "find",
        staticmethod(lambda value: captured_queries.append(value) or query),
    )
    created_from = datetime(2026, 8, 1)
    created_to = datetime(2026, 8, 5, 23, 59, 59)

    response = await instance_endpoint.get_action_instances(
        PageParamsSchema(page=1, page_size=10),
        status=ActionFlowStatusEnum.PARTIALLY_COMPLETED,
        keyword="测试行动",
        created_from=created_from,
        created_to=created_to,
    )

    assert response.total == 0
    assert len(captured_queries) == 1
    filters = captured_queries[0]
    assert filters["status"] == ActionFlowStatusEnum.PARTIALLY_COMPLETED
    assert filters["created_at"] == {
        "$gte": created_from,
        "$lte": created_to,
    }
    assert filters["$or"][0]["blueprint_snapshot.name"]["$regex"].pattern == "测试行动"
    assert filters["$or"][1]["blueprint_snapshot.description"]["$regex"].pattern == "测试行动"


@pytest.mark.asyncio
async def test_action_history_summary_counts_partial_separately(monkeypatch) -> None:
    def find_actions(filters):
        status = filters.get("status")
        if status == ActionFlowStatusEnum.COMPLETED:
            count = 4
        elif status == ActionFlowStatusEnum.PARTIALLY_COMPLETED:
            count = 2
        elif status == ActionFlowStatusEnum.RUNNING:
            count = 1
        elif isinstance(status, dict):
            count = 3
        else:
            count = 10
        return _ActionQuery([object()] * count)

    monkeypatch.setattr(
        ActionInstanceModel,
        "find",
        staticmethod(find_actions),
    )

    response = await instance_endpoint.get_action_history_summary()

    assert response.code == 0
    assert response.data.total == 10
    assert response.data.completed == 4
    assert response.data.partially_completed == 2
    assert response.data.running == 1
    assert response.data.failed == 3
