from datetime import datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest

from app.api.v1.endpoints.action import blueprint as blueprint_endpoint
from app.api.v1.endpoints.action import instance as instance_endpoint
from app.models.action.action import ActionInstanceModel, ActionInstanceNodeModel
from app.models.action.blueprint import (
    ActionBlueprintModel,
    GraphModel,
    ViewportModel,
    create_blueprint_snapshot,
)
from app.models.action.blueprint_revision import ActionBlueprintRevisionModel
from app.models.action.node import ActionNodeModel
from app.models.action.component_run import ComponentRunModel
from app.models.action.node_execution import ActionNodeExecutionModel
from app.models.action.schedule import ActionScheduleModel
from app.schemas.general import PageParamsSchema
from app.schemas.action.blueprint import ActionBlueprintPinSchema, ActionBlueprintSchema
from app.schemas.constants import (
    ActionInstanceNodeStatusEnum,
    ActionSchedulingModeEnum,
)
from app.service.action import ActionInstanceService


def test_blueprint_schema_defaults_to_barrier_mode() -> None:
    request = ActionBlueprintSchema(
        name="兼容蓝图",
        version="1.0.0",
        description="",
        target="目标",
        graph={
            "nodes": [],
            "edges": [],
            "viewport": {"x": 0, "y": 0, "zoom": 1},
        },
    )

    assert request.default_scheduling_mode == ActionSchedulingModeEnum.BARRIER


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("is_pinned", "expected_filters"),
    [
        (None, {"is_deleted": False}),
        (True, {"is_deleted": False, "is_pinned": True}),
        (False, {"is_deleted": False, "is_pinned": {"$ne": True}}),
    ],
)
async def test_blueprint_list_filters_before_pagination(
    monkeypatch, is_pinned, expected_filters,
):
    """置顶筛选在分页前执行，未置顶筛选兼容旧文档缺字段。"""
    query = Mock()
    query.count = AsyncMock(return_value=105)
    query.sort.return_value = query
    query.skip.return_value = query
    query.limit.return_value = query
    query.to_list = AsyncMock(return_value=[])
    find = Mock(return_value=query)
    monkeypatch.setattr(ActionBlueprintModel, "find", find)

    response = await blueprint_endpoint.get_blueprints(
        PageParamsSchema(page=2, page_size=100), is_pinned=is_pinned,
    )

    find.assert_called_once_with(expected_filters)
    query.sort.assert_called_once_with("-created_at")
    query.skip.assert_called_once_with(100)
    query.limit.assert_called_once_with(100)
    assert response.total == 105
    assert response.total_pages == 2


def test_legacy_blueprint_defaults_to_unpinned_and_snapshot_excludes_pin(monkeypatch):
    """旧蓝图默认未置顶，置顶状态不进入执行快照或编辑请求。"""
    monkeypatch.setattr(
        ActionBlueprintModel, "get_motor_collection", classmethod(lambda _cls: object()),
    )
    blueprint = ActionBlueprintModel.model_validate({
        "_id": "legacy-blueprint",
        "name": "旧蓝图",
        "version": "1.0.0",
        "description": "描述",
        "target": "目标",
        "graph": {"nodes": [], "edges": [], "viewport": {"x": 0, "y": 0, "zoom": 1}},
    })

    assert blueprint.is_pinned is False
    assert blueprint_endpoint._blueprint_detail(blueprint).is_pinned is False
    blueprint.is_pinned = True
    assert blueprint_endpoint._blueprint_detail(blueprint).is_pinned is True
    assert "is_pinned" not in create_blueprint_snapshot(blueprint).model_dump()
    assert "is_pinned" not in ActionBlueprintSchema.model_fields


@pytest.mark.asyncio
@pytest.mark.parametrize("pin_fields", [{}, {"is_pinned": True}])
async def test_blueprint_list_returns_pin_state(monkeypatch, pin_fields):
    """列表回显置顶状态，并兼容未包含置顶字段的旧对象。"""
    blueprint = SimpleNamespace(
        id="blueprint-1", name="蓝图", version="1.0.0", description="描述",
        target="目标", implementation_period=0, graph=SimpleNamespace(nodes=[]),
        created_at=datetime(2026, 1, 1), updated_at=datetime(2026, 1, 1),
        is_template=False, **pin_fields,
    )
    query = Mock()
    query.count = AsyncMock(return_value=1)
    query.sort.return_value = query
    query.skip.return_value = query
    query.limit.return_value = query
    query.to_list = AsyncMock(return_value=[blueprint])
    revision_query = Mock()
    revision_query.sort.return_value = revision_query
    revision_query.first_or_none = AsyncMock(return_value=None)
    node_query = Mock(count=AsyncMock(return_value=0))
    monkeypatch.setattr(ActionBlueprintModel, "find", Mock(return_value=query))
    monkeypatch.setattr(ActionBlueprintRevisionModel, "find", Mock(return_value=revision_query))
    monkeypatch.setattr(ActionNodeModel, "find", Mock(return_value=node_query))
    monkeypatch.setattr(blueprint_endpoint, "count_workflow_paths", Mock(return_value=0))

    response = await blueprint_endpoint.get_blueprints(PageParamsSchema())

    assert response.items[0].is_pinned is pin_fields.get("is_pinned", False)


@pytest.mark.asyncio
@pytest.mark.parametrize("is_pinned", [True, False])
@pytest.mark.parametrize("modified_count", [0, 1])
async def test_pin_update_is_atomic_and_idempotent(monkeypatch, is_pinned, modified_count):
    """置顶只原子更新单个字段，重复设置相同状态也成功。"""
    query = Mock(update=AsyncMock(return_value=SimpleNamespace(
        matched_count=1, modified_count=modified_count,
    )))
    find_one = Mock(return_value=query)
    monkeypatch.setattr(ActionBlueprintModel, "find_one", find_one)

    response = await blueprint_endpoint.update_blueprint_pin(
        "blueprint-1", ActionBlueprintPinSchema(is_pinned=is_pinned),
    )

    find_one.assert_called_once_with({"_id": "blueprint-1", "is_deleted": False})
    query.update.assert_awaited_once_with({"$set": {"is_pinned": is_pinned}})
    assert response.code == 0
    assert response.data.is_pinned is is_pinned


@pytest.mark.asyncio
async def test_pin_update_rejects_missing_or_deleted_blueprint(monkeypatch):
    """不存在或已删除的蓝图不能置顶。"""
    query = Mock(update=AsyncMock(return_value=SimpleNamespace(matched_count=0)))
    monkeypatch.setattr(ActionBlueprintModel, "find_one", Mock(return_value=query))

    response = await blueprint_endpoint.update_blueprint_pin(
        "missing", ActionBlueprintPinSchema(is_pinned=True),
    )

    assert response.code == 240411
    assert response.data is None


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
async def test_delete_blueprint_rejects_pending_queue_cleanup(monkeypatch):
    blueprint = SimpleNamespace(
        is_deleted=False,
        updated_at=None,
        save=AsyncMock(),
        delete=AsyncMock(),
    )
    find_action = AsyncMock(
        side_effect=[None, SimpleNamespace(id="action-pending-cleanup")]
    )
    clear_cache = AsyncMock()
    monkeypatch.setattr(ActionBlueprintModel, "find_one", AsyncMock(return_value=blueprint))
    monkeypatch.setattr(ActionScheduleModel, "find_one", AsyncMock(return_value=None))
    monkeypatch.setattr(ActionInstanceModel, "find_one", find_action)
    monkeypatch.setattr(ActionInstanceService, "_clear_cache", clear_cache)

    response = await blueprint_endpoint.delete_blueprint("blueprint-1")

    assert response.code == 240423
    assert "队列等待清理" in response.message
    assert find_action.await_args_list[1].args[0] == {
        "blueprint_id": "blueprint-1",
        "queue_cleanup_state": {"$exists": True, "$ne": "completed"},
    }
    assert blueprint.is_deleted is False
    assert blueprint.save.await_count == 2
    assert clear_cache.await_count == 2
    blueprint.delete.assert_not_awaited()


@pytest.mark.asyncio
async def test_delete_blueprint_rejects_pending_embedded_action_reconciliation(
    monkeypatch,
):
    blueprint = SimpleNamespace(
        is_deleted=False,
        updated_at=None,
        save=AsyncMock(),
        delete=AsyncMock(),
    )
    action_list_query = Mock()
    action_list_query.to_list = AsyncMock(
        return_value=[SimpleNamespace(id="embedded-action-1")]
    )
    parent_execution = SimpleNamespace(
        id="parent-execution-1",
        status=ActionInstanceNodeStatusEnum.RUNNING,
    )
    find_parent_execution = AsyncMock(return_value=parent_execution)
    clear_cache = AsyncMock()
    monkeypatch.setattr(ActionBlueprintModel, "find_one", AsyncMock(return_value=blueprint))
    monkeypatch.setattr(ActionScheduleModel, "find_one", AsyncMock(return_value=None))
    monkeypatch.setattr(ActionInstanceModel, "find_one", AsyncMock(return_value=None))
    monkeypatch.setattr(ActionInstanceModel, "find", Mock(return_value=action_list_query))
    monkeypatch.setattr(ActionNodeExecutionModel, "find_one", find_parent_execution)
    monkeypatch.setattr(ActionInstanceService, "_clear_cache", clear_cache)

    response = await blueprint_endpoint.delete_blueprint("blueprint-1")

    assert response.code == 240423
    assert "等待父流程对账" in response.message
    assert find_parent_execution.await_args.args[0] == {
        "child_action_id": {"$in": ["embedded-action-1"]},
        "status": {
            "$nin": [
                ActionInstanceNodeStatusEnum.COMPLETED.value,
                ActionInstanceNodeStatusEnum.FAILED.value,
                ActionInstanceNodeStatusEnum.CANCELLED.value,
                ActionInstanceNodeStatusEnum.TIMEOUT.value,
            ]
        },
    }
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
    monkeypatch.setattr(ActionNodeExecutionModel, "find_one", AsyncMock(return_value=None))
    monkeypatch.setattr(ActionInstanceNodeModel, "find", Mock(return_value=node_delete_query))
    monkeypatch.setattr(ComponentRunModel, "find", Mock(return_value=run_delete_query))
    monkeypatch.setattr(ActionInstanceService, "_clear_cache", clear_cache)
    monkeypatch.setattr(blueprint_endpoint, "get_es", Mock(return_value=es))

    response = await blueprint_endpoint.delete_blueprint("blueprint-1")

    assert response.code == 0
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
async def test_update_blueprint_keeps_id_and_disables_invalid_schedules(
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
        is_pinned=True,
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
    schedule_query = Mock()
    schedule_query.to_list = AsyncMock(return_value=[schedule])
    clear_cache = AsyncMock()

    monkeypatch.setattr(ActionBlueprintModel, "find_one", AsyncMock(return_value=blueprint))
    monkeypatch.setattr(ActionScheduleModel, "find", Mock(return_value=schedule_query))
    monkeypatch.setattr(ActionInstanceService, "_clear_cache", clear_cache)

    request = ActionBlueprintSchema(
        name="新蓝图",
        version="2.0.0",
        description="新描述",
        target="新目标",
        implementation_period=120,
        default_scheduling_mode=ActionSchedulingModeEnum.STREAMING,
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
    assert blueprint.default_scheduling_mode == ActionSchedulingModeEnum.STREAMING
    assert (
        response.data.blueprint.default_scheduling_mode
        == ActionSchedulingModeEnum.STREAMING
    )
    assert blueprint.template is None
    assert blueprint.created_at == created_at
    assert blueprint.is_pinned is True
    assert response.data.blueprint.is_pinned is True
    assert blueprint.updated_at != old_updated_at
    blueprint.save.assert_awaited_once()
    clear_cache.assert_awaited_once_with("blueprint", "blueprint-1")

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
