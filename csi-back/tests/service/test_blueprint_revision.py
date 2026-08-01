from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from app.models.action.blueprint import (
    ActionBlueprintModel,
    GraphModel,
    GraphNodeModel,
    NodeDataModel,
    PositionModel,
    ViewportModel,
)
from app.models.action.blueprint_revision import ActionBlueprintRevisionModel
from app.models.action.node import ActionNodeModel
from app.schemas.action.execution import (
    BlueprintExecutionPlan,
    NativeNodeExtensionSpec,
    NodeExecutionSpec,
    default_component_execution,
)
from app.schemas.action.interface import (
    BlueprintInterfacePort,
    BlueprintInterfaceSpec,
)
from app.schemas.constants import (
    ActionExecutionDriverEnum,
    ActionInvocationModeEnum,
    ActionNodeDefinitionOriginEnum,
    ActionNodeKindEnum,
)
from app.service.blueprint_revision import BlueprintRevisionService


class _Query:
    def __init__(self, values):
        self.values = values

    async def to_list(self):
        return self.values

    def sort(self, *_args):
        return self

    async def first_or_none(self):
        return self.values[0] if self.values else None


def _snapshot(
    *,
    name: str,
    origin: ActionNodeDefinitionOriginEnum = ActionNodeDefinitionOriginEnum.USER,
) -> dict:
    is_builtin = origin == ActionNodeDefinitionOriginEnum.BACKEND_BUILTIN
    node = ActionNodeModel.model_construct(
        id="definition-1",
        name=name,
        description="快照",
        type="processor",
        category="processor",
        node_kind=(
            ActionNodeKindEnum.BACKEND_NATIVE
            if is_builtin
            else ActionNodeKindEnum.ORDINARY
        ),
        execution=(
            NodeExecutionSpec(
                driver=ActionExecutionDriverEnum.BACKEND_NATIVE,
                handler="test.native",
            )
            if is_builtin
            else default_component_execution()
        ),
        extension=NativeNodeExtensionSpec() if is_builtin else None,
        definition_origin=origin,
        builtin_key="test.native" if is_builtin else None,
        version="1",
        handles=[],
        inputs=[],
        related_components=[],
    )
    return node.model_dump(mode="python", by_alias=True)


@pytest.mark.asyncio
async def test_revision_restores_immutable_definition_snapshot(monkeypatch) -> None:
    monkeypatch.setattr(
        ActionNodeModel,
        "get_motor_collection",
        classmethod(lambda _cls: object()),
    )
    monkeypatch.setattr(
        ActionNodeModel,
        "find",
        staticmethod(lambda _query: _Query([])),
    )
    revision = SimpleNamespace(
        definition_snapshots={"definition-1": _snapshot(name="发布时名称")}
    )

    definitions = await BlueprintRevisionService.load_revision_definitions(revision)

    assert definitions["definition-1"].name == "发布时名称"
    assert definitions["definition-1"].execution.handler == "component.run"


@pytest.mark.asyncio
async def test_disabled_builtin_blocks_new_action_from_old_revision(
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        ActionNodeModel,
        "get_motor_collection",
        classmethod(lambda _cls: object()),
    )
    monkeypatch.setattr(
        ActionNodeModel,
        "find",
        staticmethod(
            lambda _query: _Query(
                [SimpleNamespace(id="definition-1", enabled=False)]
            )
        ),
    )
    revision = SimpleNamespace(
        definition_snapshots={
            "definition-1": _snapshot(
                name="分析节点",
                origin=ActionNodeDefinitionOriginEnum.BACKEND_BUILTIN,
            )
        }
    )

    with pytest.raises(ValueError, match="已禁用"):
        await BlueprintRevisionService.load_revision_definitions(revision)


@pytest.mark.asyncio
async def test_publish_hash_includes_runtime_definition_snapshot(
    monkeypatch,
) -> None:
    for model in (
        ActionBlueprintModel,
        ActionBlueprintRevisionModel,
        ActionNodeModel,
    ):
        monkeypatch.setattr(
            model,
            "get_motor_collection",
            classmethod(lambda _cls: object()),
        )
    graph = GraphModel(
        nodes=[
            GraphNodeModel(
                id="node-1",
                type="processor",
                position=PositionModel(x=0, y=0),
                data=NodeDataModel(
                    definition_id="definition-1",
                    version="1",
                    form_data=[],
                ),
            )
        ],
        edges=[],
        viewport=ViewportModel(x=0, y=0, zoom=1),
    )
    blueprint = ActionBlueprintModel(
        _id="blueprint-1",
        name="蓝图",
        version="1",
        description="测试",
        target="测试",
        graph=graph,
    )
    definition = ActionNodeModel.model_validate(
        {
            **_snapshot(name="组件节点"),
            "command": "runner-one",
            "command_args": ["main:run"],
        }
    )
    standalone = BlueprintExecutionPlan(
        plan_schema_version=2,
        invocation_mode=ActionInvocationModeEnum.STANDALONE,
        nodes=[],
        edges=[],
    )
    subflow = BlueprintExecutionPlan(
        plan_schema_version=2,
        invocation_mode=ActionInvocationModeEnum.SUBFLOW,
        nodes=[],
        edges=[],
        public_interface_snapshot=BlueprintInterfaceSpec().model_dump(),
    )

    async def fake_validate(_blueprint):
        return standalone, subflow, {"definition-1": definition}

    async def find_one(_query):
        return None

    inserted = []

    async def insert(revision):
        inserted.append(revision)
        return revision

    async def save(_blueprint):
        return _blueprint

    monkeypatch.setattr(
        BlueprintRevisionService,
        "validate",
        staticmethod(fake_validate),
    )
    monkeypatch.setattr(
        ActionBlueprintRevisionModel,
        "find_one",
        staticmethod(find_one),
    )
    monkeypatch.setattr(
        ActionBlueprintRevisionModel,
        "find",
        staticmethod(lambda _query: _Query([])),
    )
    monkeypatch.setattr(ActionBlueprintRevisionModel, "insert", insert)
    monkeypatch.setattr(ActionBlueprintModel, "save", save)

    await BlueprintRevisionService.publish(blueprint)
    definition.command = "runner-two"
    await BlueprintRevisionService.publish(blueprint)

    assert len(inserted) == 2
    assert inserted[0].content_hash != inserted[1].content_hash
    assert inserted[0].runtime_contract_version == 2
    assert inserted[0].reference_protocol_version == "eos-v1"


def test_revision_records_current_runtime_contract() -> None:
    revision = ActionBlueprintRevisionModel.model_construct(
        id="revision",
        blueprint_id="blueprint-1",
        version="1.0.0",
        revision_number=1,
        graph_snapshot=GraphModel(
            nodes=[],
            edges=[],
            viewport=ViewportModel(x=0, y=0, zoom=1),
        ),
        runtime_contract_version=2,
        reference_protocol_version="eos-v1",
        content_hash="current",
    )

    assert revision.runtime_contract_version == 2
    assert revision.reference_protocol_version == "eos-v1"


@pytest.mark.asyncio
async def test_recreate_deleted_family_starts_new_family_from_version_one(
    monkeypatch,
) -> None:
    blueprint = SimpleNamespace(
        id="blueprint-1",
        is_template=False,
        template=None,
    )
    revision = SimpleNamespace(
        id="revision-4",
        interface_snapshot=BlueprintInterfaceSpec(
            inputs=[
                BlueprintInterfacePort(
                    id="reference-in",
                    name="引用输入",
                    direction="input",
                    handle_config_id="reference.input",
                    interface_type_id="custom.reference",
                    data_type="reference",
                )
            ],
            outputs=[
                BlueprintInterfacePort(
                    id="reference-out",
                    name="引用输出",
                    direction="output",
                    handle_config_id="reference.output",
                    interface_type_id="custom.reference",
                    data_type="reference",
                )
            ],
        ),
    )
    inserted = []
    monkeypatch.setattr(
        ActionNodeModel,
        "get_motor_collection",
        classmethod(lambda _cls: object()),
    )

    async def insert(node):
        inserted.append(node)
        return node

    monkeypatch.setattr(
        ActionNodeModel,
        "find_one",
        AsyncMock(return_value=None),
    )
    monkeypatch.setattr(
        ActionNodeModel,
        "insert",
        insert,
    )
    next_version = AsyncMock(return_value=1)
    normalize_latest = AsyncMock()
    monkeypatch.setattr(
        "app.service.blueprint_revision.next_encapsulated_definition_version",
        next_version,
    )
    monkeypatch.setattr(
        "app.service.blueprint_revision.normalize_encapsulated_latest",
        normalize_latest,
    )

    node = await BlueprintRevisionService.encapsulate(
        blueprint,
        revision,
        node_name="采集子流程",
        description="重新封装",
        category="subflow",
        mode="create",
        target_encapsulated_node_id=None,
    )

    assert node.definition_version == 1
    assert node.version == "1"
    assert node.node_family_id
    assert {handle.data_type for handle in node.handles} == {"reference"}
    assert {handle.port_id for handle in node.handles} == {
        "reference-in",
        "reference-out",
    }
    assert inserted == [node]
    next_version.assert_awaited_once_with(node.node_family_id)
    normalize_latest.assert_awaited_once_with(
        node.node_family_id,
        preferred_node_id=node.id,
    )
