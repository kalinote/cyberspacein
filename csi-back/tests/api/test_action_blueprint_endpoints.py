from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest

from app.api.v1.endpoints.action import blueprint as blueprint_endpoint
from app.models.action.action import ActionInstanceModel, ActionInstanceNodeModel
from app.models.action.blueprint import ActionBlueprintModel
from app.models.action.component_run import ComponentRunModel
from app.models.action.schedule import ActionScheduleModel
from app.service.action import ActionInstanceService


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
