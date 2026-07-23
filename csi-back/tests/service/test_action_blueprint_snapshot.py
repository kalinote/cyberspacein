from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest

from app.models.action.action import ActionInstanceModel
from app.models.action.blueprint import (
    GraphEdgeModel,
    GraphModel,
    ViewportModel,
    create_blueprint_snapshot,
)
from app.service import action as action_service
from app.service.action import ActionInstanceService
from app.utils.id_lib import generate_id


def blueprint_stub(*, name: str = "蓝图", edges=None):
    """构造不依赖数据库的蓝图测试对象。"""
    return SimpleNamespace(
        id="blueprint-1",
        name=name,
        version="1.0.0",
        description="描述",
        target="目标",
        implementation_period=60,
        resource={"key": "value"},
        graph=GraphModel(
            nodes=[],
            edges=edges or [],
            viewport=ViewportModel(x=0, y=0, zoom=1),
        ),
        is_template=False,
        template=None,
    )


@pytest.mark.asyncio
async def test_init_action_persists_blueprint_snapshot(monkeypatch):
    blueprint = blueprint_stub()
    action_instance = SimpleNamespace(insert=AsyncMock())
    action_factory = Mock(return_value=action_instance)
    monkeypatch.setattr(action_service, "ActionInstanceModel", action_factory)
    monkeypatch.setattr(
        ActionInstanceService,
        "get_blueprint",
        AsyncMock(return_value=blueprint),
    )

    result, action_id = await ActionInstanceService.init("blueprint-1")

    assert result is True
    assert action_id
    snapshot = action_factory.call_args.kwargs["blueprint_snapshot"]
    assert snapshot.blueprint_id == "blueprint-1"
    assert snapshot.name == "蓝图"
    assert snapshot.resource == {"key": "value"}
    action_instance.insert.assert_awaited_once()


@pytest.mark.asyncio
async def test_find_next_node_uses_action_snapshot(monkeypatch):
    old_edge = GraphEdgeModel(
        id="edge-old",
        source="node-1",
        sourceHandle="output",
        target="node-old",
        targetHandle="input",
    )
    new_edge = GraphEdgeModel(
        id="edge-new",
        source="node-1",
        sourceHandle="output",
        target="node-new",
        targetHandle="input",
    )
    action = SimpleNamespace(
        id="action-1",
        blueprint_id="blueprint-1",
        blueprint_snapshot=create_blueprint_snapshot(
            blueprint_stub(name="旧蓝图", edges=[old_edge])
        ),
    )
    monkeypatch.setattr(
        ActionInstanceModel,
        "find_one",
        AsyncMock(return_value=action),
    )
    get_blueprint = AsyncMock(return_value=blueprint_stub(name="新蓝图", edges=[new_edge]))
    monkeypatch.setattr(ActionInstanceService, "get_blueprint", get_blueprint)

    next_nodes = await ActionInstanceService.find_next_node("action-1", "node-1")

    assert generate_id("action-1node-old") in next_nodes
    assert generate_id("action-1node-new") not in next_nodes
    get_blueprint.assert_not_awaited()


@pytest.mark.asyncio
async def test_legacy_action_without_snapshot_falls_back_to_current_blueprint(monkeypatch):
    action = SimpleNamespace(
        blueprint_id="blueprint-1",
        blueprint_snapshot=None,
    )
    blueprint = blueprint_stub()
    get_blueprint = AsyncMock(return_value=blueprint)
    monkeypatch.setattr(ActionInstanceService, "get_blueprint", get_blueprint)

    result = await ActionInstanceService.get_action_blueprint(action)

    assert result is blueprint
    get_blueprint.assert_awaited_once_with("blueprint-1")
