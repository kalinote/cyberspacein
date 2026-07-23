from datetime import datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest

from app.api.v1.endpoints.action import blueprint as blueprint_endpoint
from app.api.v1.endpoints.action import instance as instance_endpoint
from app.models.action.action import ActionInstanceModel, ActionInstanceNodeModel
from app.models.action.blueprint import ActionBlueprintModel, GraphModel, ViewportModel
from app.models.action.component_run import ComponentRunModel
from app.models.action.schedule import ActionScheduleModel
from app.schemas.general import PageParamsSchema
from app.schemas.action.blueprint import ActionBlueprintSchema
from app.service.action import ActionInstanceService


@pytest.mark.asyncio
async def test_blueprint_list_sorts_by_created_at_descending(monkeypatch):
    query = Mock()
    query.count = AsyncMock(return_value=0)
    query.sort.return_value = query
    query.skip.return_value = query
    query.limit.return_value = query
    query.to_list = AsyncMock(return_value=[])
    monkeypatch.setattr(ActionBlueprintModel, "find", Mock(return_value=query))

    await blueprint_endpoint.get_blueprints(PageParamsSchema())

    query.sort.assert_called_once_with("-created_at")


@pytest.mark.asyncio
async def test_action_history_sorts_by_created_at_descending(monkeypatch):
    query = Mock()
    query.count = AsyncMock(return_value=0)
    query.sort.return_value = query
    query.skip.return_value = query
    query.limit.return_value = query
    query.to_list = AsyncMock(return_value=[])
    monkeypatch.setattr(ActionInstanceModel, "find_all", Mock(return_value=query))

    await instance_endpoint.get_action_instances(PageParamsSchema())

    query.sort.assert_called_once_with("-created_at")


@pytest.mark.asyncio
async def test_delete_blueprint_rejects_associated_schedule(monkeypatch):
    blueprint = SimpleNamespace(save=AsyncMock(), delete=AsyncMock())
    monkeypatch.setattr(ActionBlueprintModel, "find_one", AsyncMock(return_value=blueprint))
    monkeypatch.setattr(ActionScheduleModel, "find_one", AsyncMock(return_value=SimpleNamespace()))

    response = await blueprint_endpoint.delete_blueprint("blueprint-1")

    assert response.code == 240423
    assert "调度计划" in response.message
    blueprint.save.assert_not_awaited()
    blueprint.delete.assert_not_awaited()


@pytest.mark.asyncio
async def test_delete_blueprint_rejects_unfinished_action(monkeypatch):
    blueprint = SimpleNamespace(is_deleted=False, updated_at=None, save=AsyncMock(), delete=AsyncMock())
    clear_cache = AsyncMock()
    monkeypatch.setattr(ActionBlueprintModel, "find_one", AsyncMock(return_value=blueprint))
    monkeypatch.setattr(ActionScheduleModel, "find_one", AsyncMock(return_value=None))
    monkeypatch.setattr(ActionInstanceModel, "find_one", AsyncMock(return_value=SimpleNamespace()))
    monkeypatch.setattr(ActionInstanceService, "_clear_cache", clear_cache)

    response = await blueprint_endpoint.delete_blueprint("blueprint-1")

    assert response.code == 240423
    assert "未结束" in response.message
    assert blueprint.is_deleted is False
    assert blueprint.save.await_count == 2
    assert clear_cache.await_count == 2
    blueprint.delete.assert_not_awaited()


@pytest.mark.asyncio
async def test_delete_blueprint_cascades_historical_action_data(monkeypatch):
    blueprint = SimpleNamespace(is_deleted=False, updated_at=None, save=AsyncMock(), delete=AsyncMock())
    action_list_query = Mock()
    action_list_query.to_list = AsyncMock(
        return_value=[SimpleNamespace(id="action-1"), SimpleNamespace(id="action-2")]
    )
    action_delete_query = Mock()
    action_delete_query.delete = AsyncMock()
    node_delete_query = Mock()
    node_delete_query.delete = AsyncMock()
    run_delete_query = Mock()
    run_delete_query.delete = AsyncMock()
    es = SimpleNamespace(delete_by_query=AsyncMock())
    clear_cache = AsyncMock()

    monkeypatch.setattr(ActionBlueprintModel, "find_one", AsyncMock(return_value=blueprint))
    monkeypatch.setattr(ActionScheduleModel, "find_one", AsyncMock(return_value=None))
    monkeypatch.setattr(ActionInstanceModel, "find_one", AsyncMock(return_value=None))
    monkeypatch.setattr(ActionInstanceModel, "find", Mock(side_effect=[action_list_query, action_delete_query]))
    monkeypatch.setattr(ActionInstanceNodeModel, "find", Mock(return_value=node_delete_query))
    monkeypatch.setattr(ComponentRunModel, "find", Mock(return_value=run_delete_query))
    monkeypatch.setattr(ActionInstanceService, "_clear_cache", clear_cache)
    monkeypatch.setattr(blueprint_endpoint, "get_es", Mock(return_value=es))

    response = await blueprint_endpoint.delete_blueprint("blueprint-1")

    assert response.code == 0
    assert response.message == "蓝图及历史行动已删除"
    assert blueprint.is_deleted is True
    blueprint.save.assert_awaited_once()
    blueprint.delete.assert_awaited_once()
    clear_cache.assert_awaited_once_with("blueprint", "blueprint-1")
    es.delete_by_query.assert_awaited_once()
    assert es.delete_by_query.await_args.kwargs["query"] == {
        "terms": {"action_id": ["action-1", "action-2"]}
    }
    run_delete_query.delete.assert_awaited_once()
    node_delete_query.delete.assert_awaited_once()
    action_delete_query.delete.assert_awaited_once()


@pytest.mark.asyncio
async def test_update_blueprint_keeps_id_snapshots_actions_and_disables_invalid_schedules(
    monkeypatch,
):
    created_at = datetime(2026, 1, 1)
    old_updated_at = datetime(2026, 1, 2)
    blueprint = SimpleNamespace(
        id="blueprint-1",
        name="旧蓝图",
        version="1.0.0",
        description="旧描述",
        target="旧目标",
        implementation_period=60,
        resource={"account": "old"},
        graph=GraphModel(
            nodes=[],
            edges=[],
            viewport=ViewportModel(x=0, y=0, zoom=1),
        ),
        is_template=True,
        template={
            "params": [
                {
                    "name": "keyword",
                    "type": "string",
                    "label": "关键词",
                    "required": True,
                    "description": None,
                }
            ],
            "bindings": {},
        },
        created_at=created_at,
        updated_at=old_updated_at,
        save=AsyncMock(),
    )
    schedule = SimpleNamespace(
        id="schedule-1",
        name="旧模板调度",
        params={"keyword": "test"},
        enabled=True,
        next_run_at=datetime(2026, 2, 1),
        last_trigger_status=None,
        last_error=None,
        updated_at=None,
        save=AsyncMock(),
    )
    action_query = Mock()
    action_query.update = AsyncMock(return_value=SimpleNamespace(modified_count=1))
    schedule_query = Mock()
    schedule_query.to_list = AsyncMock(return_value=[schedule])
    clear_cache = AsyncMock()

    monkeypatch.setattr(ActionBlueprintModel, "find_one", AsyncMock(return_value=blueprint))
    monkeypatch.setattr(ActionInstanceModel, "find", Mock(return_value=action_query))
    monkeypatch.setattr(ActionScheduleModel, "find", Mock(return_value=schedule_query))
    monkeypatch.setattr(ActionInstanceService, "_clear_cache", clear_cache)

    request = ActionBlueprintSchema(
        name="新蓝图",
        version="2.0.0",
        description="新描述",
        target="新目标",
        implementation_period=120,
        resource={"account": "new"},
        graph={
            "nodes": [],
            "edges": [],
            "viewport": {"x": 10, "y": 20, "zoom": 1.5},
        },
        is_template=False,
        template=None,
    )
    response = await blueprint_endpoint.update_blueprint("blueprint-1", request)

    assert response.code == 0
    assert response.data.blueprint.id == "blueprint-1"
    assert response.data.blueprint.created_at == created_at
    assert blueprint.name == "新蓝图"
    assert blueprint.version == "2.0.0"
    assert blueprint.template is None
    assert blueprint.created_at == created_at
    assert blueprint.updated_at != old_updated_at
    blueprint.save.assert_awaited_once()
    clear_cache.assert_awaited_once_with("blueprint", "blueprint-1")

    snapshot_payload = action_query.update.await_args.args[0]["$set"]["blueprint_snapshot"]
    assert snapshot_payload["name"] == "旧蓝图"
    assert snapshot_payload["version"] == "1.0.0"

    assert schedule.enabled is False
    assert schedule.next_run_at is None
    assert schedule.last_trigger_status == "invalid"
    assert "非模板蓝图" in schedule.last_error
    schedule.save.assert_awaited_once()
    assert response.data.disabled_schedules[0].id == "schedule-1"


@pytest.mark.asyncio
async def test_update_blueprint_rejects_template_without_spec(monkeypatch):
    blueprint = SimpleNamespace(id="blueprint-1")
    monkeypatch.setattr(ActionBlueprintModel, "find_one", AsyncMock(return_value=blueprint))

    request = ActionBlueprintSchema(
        name="模板蓝图",
        version="1.0.0",
        description="",
        target="目标",
        graph={
            "nodes": [],
            "edges": [],
            "viewport": {"x": 0, "y": 0, "zoom": 1},
        },
        is_template=True,
        template=None,
    )
    response = await blueprint_endpoint.update_blueprint("blueprint-1", request)

    assert response.code == 240001
    assert response.message == "模板蓝图必须提供模板配置"
