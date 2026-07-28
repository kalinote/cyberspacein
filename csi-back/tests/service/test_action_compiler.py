from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from app.models.action.blueprint import (
    GraphEdgeModel,
    GraphModel,
    GraphNodeModel,
    NodeDataModel,
    PositionModel,
    ViewportModel,
)
from app.models.action.configs import ActionNodesHandleConfigModel
from app.models.action.node import ActionNodeHandleModel, ActionNodeModel
from app.schemas.action.execution import (
    NativeNodeExtensionSpec,
    NodeExecutionContext,
    NodeExecutionSpec,
    default_component_execution,
)
from app.schemas.action.interface import BoundaryBinding, BoundaryPortMapping
from app.schemas.constants import (
    ActionConfigIOTypeEnum,
    ActionExecutionDriverEnum,
    ActionInvocationModeEnum,
    ActionNodeDefinitionOriginEnum,
    ActionNodeKindEnum,
)
from app.service.action_compiler import BlueprintCompiler
from app.service.boundary_binding_validator import (
    BlueprintBindingValidationError,
)
from app.service.native_nodes.definitions import register_builtin_native_nodes
from app.service.native_nodes.blueprint_output import BlueprintOutputHandler
from app.service.native_nodes.registry import native_definitions


register_builtin_native_nodes()


def _ordinary(
    definition_id: str,
    *,
    inputs: tuple[str, ...] = ("in",),
    outputs: tuple[str, ...] = ("out",),
) -> ActionNodeModel:
    handles = [
        ActionNodeHandleModel(
            id=f"{definition_id}.{port}",
            port_id=f"{definition_id}.{port}",
            interface_type_id="builtin.value",
            type="target",
            position="left",
        )
        for port in inputs
    ]
    handles.extend(
        ActionNodeHandleModel(
            id=f"{definition_id}.{port}",
            port_id=f"{definition_id}.{port}",
            interface_type_id="builtin.value",
            type="source",
            position="right",
        )
        for port in outputs
    )
    return ActionNodeModel.model_construct(
        id=definition_id,
        name=definition_id,
        description=definition_id,
        type="processor",
        category="processor",
        execution=default_component_execution(),
        version="1",
        handles=handles,
        inputs=[],
        related_components=["component"],
    )


def _builtin(builtin_key: str) -> ActionNodeModel:
    definition = native_definitions.require(builtin_key)
    return ActionNodeModel.model_construct(
        id=builtin_key,
        name=definition.name,
        description=definition.description,
        type=definition.category,
        category=definition.category,
        node_kind=ActionNodeKindEnum.BACKEND_NATIVE,
        execution=NodeExecutionSpec(
            driver=ActionExecutionDriverEnum.BACKEND_NATIVE,
            handler=definition.handler,
            schema_version=definition.handler_schema_version,
        ),
        extension=definition.extension,
        definition_origin=ActionNodeDefinitionOriginEnum.BACKEND_BUILTIN,
        builtin_key=builtin_key,
        version=str(definition.definition_version),
        handles=[
            ActionNodeHandleModel(
                id=handle.port_id,
                port_id=handle.port_id,
                interface_type_id=handle.interface_type_id,
                compatible_interface_type_ids=handle.other_compatible_interfaces,
                type=handle.direction,
                position=handle.position,
            )
            for handle in definition.handles
        ],
        inputs=[],
        related_components=[],
    )


def _node(
    node_id: str,
    definition_id: str,
    *,
    interface_port_id: str | None = None,
    interface_name: str | None = None,
    boundary_binding: BoundaryBinding | None = None,
) -> GraphNodeModel:
    instance_config = {}
    if interface_name is not None:
        instance_config = {"interface_name": interface_name}
    return GraphNodeModel(
        id=node_id,
        type="processor",
        position=PositionModel(x=0, y=0),
        data=NodeDataModel(
            definition_id=definition_id,
            version="1",
            form_data=[],
            instance_config=instance_config,
            interface_port_id=interface_port_id,
            boundary_binding=boundary_binding,
        ),
    )


def _edge(
    edge_id: str,
    source: str,
    source_port: str,
    target: str,
    target_port: str,
) -> GraphEdgeModel:
    return GraphEdgeModel(
        id=edge_id,
        source=source,
        sourceHandle=source_port,
        source_port_id=source_port,
        target=target,
        targetHandle=target_port,
        target_port_id=target_port,
    )


def _graph(
    nodes: list[GraphNodeModel],
    edges: list[GraphEdgeModel],
) -> GraphModel:
    return GraphModel(
        nodes=nodes,
        edges=edges,
        viewport=ViewportModel(x=0, y=0, zoom=1),
    )


def test_boundary_interface_type_is_internal_and_ignores_extra_form_value() -> None:
    """IO 接口类型不暴露为表单项，额外表单值也不能覆盖内置类型。"""
    for builtin_key in ("blueprint.input", "blueprint.output"):
        definition = native_definitions.require(builtin_key)
        assert "interface_type_id" not in {
            item.name for item in definition.instance_input_schema
        }

    boundary = _node(
        "input",
        "blueprint.input",
        interface_port_id="public.in",
        interface_name="输入",
    )
    boundary.data.instance_config["interface_type_id"] = "unused.custom"
    plan = BlueprintCompiler.compile(
        _graph([boundary], []),
        {"blueprint.input": _builtin("blueprint.input")},
        ActionInvocationModeEnum.SUBFLOW,
    )

    assert (
        plan.public_interface_snapshot["inputs"][0]["interface_type_id"]
        == "builtin.value"
    )


def test_standalone_skips_unbound_boundaries() -> None:
    definitions = {
        "blueprint.input": _builtin("blueprint.input"),
        "blueprint.output": _builtin("blueprint.output"),
        "work": _ordinary("work"),
    }
    graph = _graph(
        [
            _node(
                "input",
                "blueprint.input",
                interface_port_id="public.in",
                interface_name="输入",
            ),
            _node("work", "work"),
            _node(
                "output",
                "blueprint.output",
                interface_port_id="public.out",
                interface_name="输出",
            ),
        ],
        [
            _edge(
                "e1",
                "input",
                "builtin.blueprint.input.value",
                "work",
                "work.in",
            ),
            _edge(
                "e2",
                "work",
                "work.out",
                "output",
                "builtin.blueprint.output.value",
            ),
        ],
    )

    plan = BlueprintCompiler.compile(
        graph,
        definitions,
        ActionInvocationModeEnum.STANDALONE,
    )

    assert [node.id for node in plan.nodes] == ["work"]
    assert plan.edges == []
    assert {item.node_id for item in plan.skipped_nodes} == {"input", "output"}


def test_subflow_keeps_boundaries_and_public_interface() -> None:
    definitions = {
        "blueprint.input": _builtin("blueprint.input"),
        "blueprint.output": _builtin("blueprint.output"),
        "work": _ordinary("work"),
    }
    definitions["work"].handles[0].interface_type_id = "custom.input"
    definitions["work"].handles[1].interface_type_id = "custom.output"
    graph = _graph(
        [
            _node(
                "input",
                "blueprint.input",
                interface_port_id="public.in",
                interface_name="输入",
            ),
            _node("work", "work"),
            _node(
                "output",
                "blueprint.output",
                interface_port_id="public.out",
                interface_name="输出",
            ),
        ],
        [
            _edge(
                "e1",
                "input",
                "builtin.blueprint.input.value",
                "work",
                "work.in",
            ),
            _edge(
                "e2",
                "work",
                "work.out",
                "output",
                "builtin.blueprint.output.value",
            ),
        ],
    )

    plan = BlueprintCompiler.compile(
        graph,
        definitions,
        ActionInvocationModeEnum.SUBFLOW,
    )

    assert [node.id for node in plan.nodes] == ["input", "work", "output"]
    assert [edge.id for edge in plan.edges] == ["e1", "e2"]
    assert plan.public_interface_snapshot["inputs"][0]["id"] == "public.in"
    assert plan.public_interface_snapshot["outputs"][0]["id"] == "public.out"
    assert definitions["blueprint.input"].handles[0].compatible_interface_type_ids == ["*"]
    assert definitions["blueprint.output"].handles[0].compatible_interface_type_ids == ["*"]


def test_execution_plan_v2_freezes_reference_edge_contract() -> None:
    definitions = {
        "source": _ordinary("source", inputs=()),
        "target": _ordinary("target", outputs=()),
    }
    definitions["source"].handles[0].data_type = "reference"
    definitions["target"].handles[0].data_type = "reference"
    plan = BlueprintCompiler.compile(
        _graph(
            [_node("source", "source"), _node("target", "target")],
            [_edge("reference-edge", "source", "source.out", "target", "target.in")],
        ),
        definitions,
        ActionInvocationModeEnum.STANDALONE,
    )

    assert plan.plan_schema_version == 2
    assert plan.edges[0].data_type == "reference"
    assert plan.edges[0].reference_protocol == "eos-v1"
    assert plan.edges[0].source_handle_config_id == "source.out"
    assert plan.edges[0].target_handle_config_id == "target.in"


def test_unbound_reference_input_inherits_adjacent_handle_contract() -> None:
    definitions = {
        "blueprint.input": _builtin("blueprint.input"),
        "target": _ordinary("target", outputs=()),
    }
    definitions["target"].handles[0].handle_config_id = "reference.input"
    definitions["target"].handles[0].interface_type_id = "custom.reference"
    definitions["target"].handles[0].data_type = "reference"
    graph = _graph(
        [
            _node(
                "input",
                "blueprint.input",
                interface_port_id="public.reference",
                interface_name="引用输入",
            ),
            _node("target", "target"),
        ],
        [
            _edge(
                "reference-edge",
                "input",
                "builtin.blueprint.input.value",
                "target",
                "target.in",
            )
        ],
    )

    plan = BlueprintCompiler.compile(
        graph,
        definitions,
        ActionInvocationModeEnum.SUBFLOW,
    )

    public_input = plan.public_interface_snapshot["inputs"][0]
    assert public_input["handle_config_id"] == "reference.input"
    assert public_input["interface_type_id"] == "custom.reference"
    assert public_input["data_type"] == "reference"
    assert plan.edges[0].data_type == "reference"
    assert plan.edges[0].reference_protocol == "eos-v1"
    assert plan.edges[0].source_handle_config_id == "reference.input"
    assert plan.edges[0].source_interface_type_id == "custom.reference"
    assert plan.edges[0].target_handle_config_id == "reference.input"
    assert plan.edges[0].target_interface_type_id == "custom.reference"


def test_unbound_reference_output_inherits_adjacent_handle_contract() -> None:
    definitions = {
        "blueprint.output": _builtin("blueprint.output"),
        "source": _ordinary("source", inputs=()),
    }
    definitions["source"].handles[0].handle_config_id = "reference.output"
    definitions["source"].handles[0].interface_type_id = "custom.reference"
    definitions["source"].handles[0].data_type = "reference"
    graph = _graph(
        [
            _node("source", "source"),
            _node(
                "output",
                "blueprint.output",
                interface_port_id="public.reference",
                interface_name="引用输出",
            ),
        ],
        [
            _edge(
                "reference-edge",
                "source",
                "source.out",
                "output",
                "builtin.blueprint.output.value",
            )
        ],
    )

    plan = BlueprintCompiler.compile(
        graph,
        definitions,
        ActionInvocationModeEnum.SUBFLOW,
    )

    public_output = plan.public_interface_snapshot["outputs"][0]
    assert public_output["handle_config_id"] == "reference.output"
    assert public_output["interface_type_id"] == "custom.reference"
    assert public_output["data_type"] == "reference"
    assert plan.edges[0].data_type == "reference"
    assert plan.edges[0].reference_protocol == "eos-v1"


@pytest.mark.asyncio
async def test_hydrate_allows_reference_handle_selection(monkeypatch) -> None:
    boundary = _node(
        "input",
        "blueprint.input",
        interface_port_id="public.reference",
        interface_name="引用输入",
    )
    boundary.data.instance_config["public_handle_config_id"] = "reference.input"
    usage = _ordinary("target", outputs=())
    usage.handles[0].handle_config_id = "reference.input"
    usage.handles[0].interface_type_id = "custom.reference"
    usage.handles[0].data_type = "reference"
    monkeypatch.setattr(
        ActionNodesHandleConfigModel,
        "find",
        staticmethod(
            lambda _query: SimpleNamespace(
                to_list=AsyncMock(
                    return_value=[
                        SimpleNamespace(
                            id="reference.input",
                            label="引用输入",
                            color="#7c3aed",
                            type=ActionConfigIOTypeEnum.REFERENCE,
                            other_compatible_interfaces=[],
                        )
                    ]
                )
            )
        ),
    )
    monkeypatch.setattr(
        ActionNodeModel,
        "find",
        staticmethod(
            lambda _query: SimpleNamespace(
                to_list=AsyncMock(return_value=[usage])
            )
        ),
    )

    await BlueprintCompiler.hydrate_interface_handle_selections(
        _graph([boundary], []),
        {"blueprint.input": _builtin("blueprint.input")},
    )

    selected = boundary.data.instance_config["_interface_handle"]
    assert selected["handle_config_id"] == "reference.input"
    assert selected["interface_type_id"] == "custom.reference"
    assert selected["data_type"] == "reference"


def test_bound_input_replaces_target_only_in_subflow() -> None:
    definitions = {
        "blueprint.input": _builtin("blueprint.input"),
        "source": _ordinary("source", inputs=()),
        "target": _ordinary("target"),
    }
    definitions["source"].handles[0].interface_type_id = "custom.source"
    definitions["target"].handles[0].interface_type_id = "custom.source"
    boundary = _node(
        "input",
        "blueprint.input",
        interface_port_id="public.in",
        interface_name="替代输入",
        boundary_binding=BoundaryBinding(
            bound_node_id="source",
            port_mappings=[
                BoundaryPortMapping(
                    interface_port_id="public.in",
                    target_port_id="source.out",
                )
            ],
        ),
    )
    graph = _graph(
        [boundary, _node("source", "source"), _node("target", "target")],
        [_edge("e1", "source", "source.out", "target", "target.in")],
    )

    standalone = BlueprintCompiler.compile(
        graph,
        definitions,
        ActionInvocationModeEnum.STANDALONE,
    )
    subflow = BlueprintCompiler.compile(
        graph,
        definitions,
        ActionInvocationModeEnum.SUBFLOW,
    )

    assert [node.id for node in standalone.nodes] == ["source", "target"]
    assert standalone.edges[0].source == "source"
    assert {item.node_id for item in subflow.skipped_nodes} == {"source"}
    assert [node.id for node in subflow.nodes] == ["input", "target"]
    assert subflow.edges[0].source == "input"
    assert subflow.edges[0].target == "target"
    public_input = subflow.public_interface_snapshot["inputs"][0]
    assert public_input["handle_config_id"] == "target.in"
    assert public_input["interface_type_id"] == "custom.source"


def test_bound_reference_input_freezes_rewired_handle_contract() -> None:
    definitions = {
        "blueprint.input": _builtin("blueprint.input"),
        "source": _ordinary("source", inputs=()),
        "target": _ordinary("target", outputs=()),
    }
    definitions["source"].handles[0].interface_type_id = "custom.reference"
    definitions["source"].handles[0].data_type = "reference"
    definitions["target"].handles[0].handle_config_id = "reference.input"
    definitions["target"].handles[0].interface_type_id = "custom.reference"
    definitions["target"].handles[0].data_type = "reference"
    boundary = _node(
        "input",
        "blueprint.input",
        interface_port_id="public.reference",
        interface_name="替代引用输入",
        boundary_binding=BoundaryBinding(
            bound_node_id="source",
            port_mappings=[
                BoundaryPortMapping(
                    interface_port_id="public.reference",
                    target_port_id="source.out",
                )
            ],
        ),
    )
    plan = BlueprintCompiler.compile(
        _graph(
            [boundary, _node("source", "source"), _node("target", "target")],
            [
                _edge(
                    "reference-edge",
                    "source",
                    "source.out",
                    "target",
                    "target.in",
                )
            ],
        ),
        definitions,
        ActionInvocationModeEnum.SUBFLOW,
    )

    assert {item.node_id for item in plan.skipped_nodes} == {"source"}
    assert plan.public_interface_snapshot["inputs"][0]["data_type"] == "reference"
    assert plan.edges[0].data_type == "reference"
    assert plan.edges[0].reference_protocol == "eos-v1"
    assert plan.edges[0].source_handle_config_id == "reference.input"
    assert plan.edges[0].source_interface_type_id == "custom.reference"
    assert plan.edges[0].target_handle_config_id == "reference.input"
    assert plan.edges[0].target_interface_type_id == "custom.reference"


def test_multiple_boundaries_can_replace_distinct_ports_on_same_node() -> None:
    definitions = {
        "blueprint.input": _builtin("blueprint.input"),
        "source": _ordinary("source", inputs=(), outputs=("left", "right")),
        "left_target": _ordinary("left_target"),
        "right_target": _ordinary("right_target"),
    }
    boundaries = [
        _node(
            "left_input",
            "blueprint.input",
            interface_port_id="public.left",
            interface_name="左输入",
            boundary_binding=BoundaryBinding(
                bound_node_id="source",
                port_mappings=[
                    BoundaryPortMapping(
                        interface_port_id="public.left",
                        target_port_id="source.left",
                    )
                ],
            ),
        ),
        _node(
            "right_input",
            "blueprint.input",
            interface_port_id="public.right",
            interface_name="右输入",
            boundary_binding=BoundaryBinding(
                bound_node_id="source",
                port_mappings=[
                    BoundaryPortMapping(
                        interface_port_id="public.right",
                        target_port_id="source.right",
                    )
                ],
            ),
        ),
    ]
    graph = _graph(
        [
            *boundaries,
            _node("source", "source"),
            _node("left_target", "left_target"),
            _node("right_target", "right_target"),
        ],
        [
            _edge(
                "left_edge",
                "source",
                "source.left",
                "left_target",
                "left_target.in",
            ),
            _edge(
                "right_edge",
                "source",
                "source.right",
                "right_target",
                "right_target.in",
            ),
        ],
    )

    plan = BlueprintCompiler.compile(
        graph,
        definitions,
        ActionInvocationModeEnum.SUBFLOW,
    )

    assert {item.node_id for item in plan.skipped_nodes} == {"source"}
    assert {
        (edge.source, edge.target)
        for edge in plan.edges
    } == {
        ("left_input", "left_target"),
        ("right_input", "right_target"),
    }


def test_bound_output_replaces_target_in_subflow() -> None:
    definitions = {
        "blueprint.output": _builtin("blueprint.output"),
        "source": _ordinary("source", inputs=()),
        "sink": _ordinary("sink", outputs=()),
    }
    definitions["source"].handles[0].interface_type_id = "custom.sink"
    definitions["sink"].handles[0].interface_type_id = "custom.sink"
    boundary = _node(
        "output",
        "blueprint.output",
        interface_port_id="public.out",
        interface_name="替代输出",
        boundary_binding=BoundaryBinding(
            bound_node_id="sink",
            port_mappings=[
                BoundaryPortMapping(
                    interface_port_id="public.out",
                    target_port_id="sink.in",
                )
            ],
        ),
    )
    graph = _graph(
        [_node("source", "source"), _node("sink", "sink"), boundary],
        [_edge("e1", "source", "source.out", "sink", "sink.in")],
    )

    plan = BlueprintCompiler.compile(
        graph,
        definitions,
        ActionInvocationModeEnum.SUBFLOW,
    )

    assert {item.node_id for item in plan.skipped_nodes} == {"sink"}
    assert plan.edges[0].source == "source"
    assert plan.edges[0].target == "output"
    public_output = plan.public_interface_snapshot["outputs"][0]
    assert public_output["handle_config_id"] == "source.out"
    assert public_output["interface_type_id"] == "custom.sink"


def test_boundary_rejects_multiple_different_exposed_handle_types() -> None:
    definitions = {
        "blueprint.input": _builtin("blueprint.input"),
        "left": _ordinary("left"),
        "right": _ordinary("right"),
    }
    definitions["left"].handles[0].interface_type_id = "custom.left"
    definitions["right"].handles[0].interface_type_id = "custom.right"
    graph = _graph(
        [
            _node(
                "input",
                "blueprint.input",
                interface_port_id="public.in",
                interface_name="输入",
            ),
            _node("left", "left"),
            _node("right", "right"),
        ],
        [
            _edge(
                "left-edge",
                "input",
                "builtin.blueprint.input.value",
                "left",
                "left.in",
            ),
            _edge(
                "right-edge",
                "input",
                "builtin.blueprint.input.value",
                "right",
                "right.in",
            ),
        ],
    )

    with pytest.raises(ValueError, match="相邻Handle类型不一致"):
        BlueprintCompiler.compile(
            graph,
            definitions,
            ActionInvocationModeEnum.SUBFLOW,
        )


@pytest.mark.parametrize(
    ("graph", "message"),
    [
        (
            _graph(
                [_node("a", "a"), _node("b", "b")],
                [
                    _edge("e1", "a", "a.out", "b", "b.in"),
                    _edge("e2", "b", "b.out", "a", "a.in"),
                ],
            ),
            "循环",
        ),
        (
            _graph(
                [_node("a", "a"), _node("b", "b")],
                [_edge("e1", "a", "a.in", "b", "b.in")],
            ),
            "源端口",
        ),
        (
            _graph(
                [_node("a", "a"), _node("b", "b"), _node("c", "c")],
                [
                    _edge("e1", "a", "a.out", "c", "c.in"),
                    _edge("e2", "b", "b.out", "c", "c.in"),
                ],
            ),
            "只能连接一个上游",
        ),
    ],
)
def test_invalid_graphs_are_rejected(
    graph: GraphModel,
    message: str,
) -> None:
    definitions = {
        definition_id: _ordinary(definition_id)
        for definition_id in {"a", "b", "c"}
    }
    with pytest.raises(ValueError, match=message):
        BlueprintCompiler.compile(
            graph,
            definitions,
            ActionInvocationModeEnum.STANDALONE,
        )


def test_boundary_interface_names_must_be_unique_per_direction() -> None:
    definitions = {"blueprint.input": _builtin("blueprint.input")}
    graph = _graph(
        [
            _node(
                "input-1",
                "blueprint.input",
                interface_port_id="public.1",
                interface_name="重复",
            ),
            _node(
                "input-2",
                "blueprint.input",
                interface_port_id="public.2",
                interface_name="重复",
            ),
        ],
        [],
    )

    with pytest.raises(ValueError, match="接口名称必须唯一"):
        BlueprintCompiler.compile(
            graph,
            definitions,
            ActionInvocationModeEnum.SUBFLOW,
        )


def test_incompatible_ports_and_disabled_definitions_are_rejected() -> None:
    source = _ordinary("source")
    target = _ordinary("target")
    target.handles[0].interface_type_id = "custom.other"
    graph = _graph(
        [_node("source", "source"), _node("target", "target")],
        [_edge("edge", "source", "source.out", "target", "target.in")],
    )

    with pytest.raises(ValueError, match="接口类型不兼容"):
        BlueprintCompiler.compile(
            graph,
            {"source": source, "target": target},
            ActionInvocationModeEnum.STANDALONE,
        )

    source.enabled = False
    with pytest.raises(ValueError, match="资源已禁用"):
        BlueprintCompiler.compile(
            _graph([_node("source", "source")], []),
            {"source": source},
            ActionInvocationModeEnum.STANDALONE,
        )


def test_boundary_cannot_bind_boundary_or_duplicate_target_port() -> None:
    boundary_definition = _builtin("blueprint.input")
    source = _ordinary("source", inputs=())
    boundary_target = _node(
        "target-boundary",
        "blueprint.input",
        interface_port_id="public.target",
        interface_name="目标边界",
    )
    invalid_boundary = _node(
        "source-boundary",
        "blueprint.input",
        interface_port_id="public.source",
        interface_name="源边界",
        boundary_binding=BoundaryBinding(
            bound_node_id="target-boundary",
            port_mappings=[
                BoundaryPortMapping(
                    interface_port_id="public.source",
                    target_port_id="builtin.blueprint.input.value",
                )
            ],
        ),
    )
    with pytest.raises(ValueError, match="不能绑定另一个边界节点"):
        BlueprintCompiler.compile(
            _graph([invalid_boundary, boundary_target], []),
            {"blueprint.input": boundary_definition},
            ActionInvocationModeEnum.SUBFLOW,
        )

    duplicate_boundaries = [
        _node(
            boundary_id,
            "blueprint.input",
            interface_port_id=port_id,
            interface_name=name,
            boundary_binding=BoundaryBinding(
                bound_node_id="source",
                port_mappings=[
                    BoundaryPortMapping(
                        interface_port_id=port_id,
                        target_port_id="source.out",
                    )
                ],
            ),
        )
        for boundary_id, port_id, name in (
            ("first", "public.first", "第一输入"),
            ("second", "public.second", "第二输入"),
        )
    ]
    with pytest.raises(ValueError, match="重复替换"):
        BlueprintCompiler.compile(
            _graph([*duplicate_boundaries, _node("source", "source")], []),
            {
                "blueprint.input": boundary_definition,
                "source": source,
            },
            ActionInvocationModeEnum.SUBFLOW,
        )


@pytest.mark.parametrize(
    ("boundary_definition_id", "target_port_id", "expected_code"),
    [
        ("blueprint.input", "middle.out", "binding_target_not_start"),
        ("blueprint.output", "middle.in", "binding_target_not_end"),
    ],
)
def test_boundary_cannot_replace_middle_node(
    boundary_definition_id: str,
    target_port_id: str,
    expected_code: str,
) -> None:
    definitions = {
        boundary_definition_id: _builtin(boundary_definition_id),
        "source": _ordinary("source", inputs=()),
        "middle": _ordinary("middle"),
        "sink": _ordinary("sink", outputs=()),
    }
    direction = (
        "input" if boundary_definition_id == "blueprint.input" else "output"
    )
    boundary = _node(
        f"{direction}-boundary",
        boundary_definition_id,
        interface_port_id=f"public.{direction}",
        interface_name=f"{direction}接口",
        boundary_binding=BoundaryBinding(
            bound_node_id="middle",
            port_mappings=[
                BoundaryPortMapping(
                    interface_port_id=f"public.{direction}",
                    target_port_id=target_port_id,
                )
            ],
        ),
    )
    graph = _graph(
        [
            _node("source", "source"),
            _node("middle", "middle"),
            _node("sink", "sink"),
            boundary,
        ],
        [
            _edge("e1", "source", "source.out", "middle", "middle.in"),
            _edge("e2", "middle", "middle.out", "sink", "sink.in"),
        ],
    )

    with pytest.raises(BlueprintBindingValidationError) as error:
        BlueprintCompiler.compile(
            graph,
            definitions,
            ActionInvocationModeEnum.SUBFLOW,
        )

    assert expected_code in {issue.code for issue in error.value.issues}


def test_immutable_revision_keeps_published_binding_semantics() -> None:
    definitions = {
        "blueprint.input": _builtin("blueprint.input"),
        "source": _ordinary("source", inputs=()),
        "middle": _ordinary("middle"),
        "sink": _ordinary("sink", outputs=()),
    }
    boundary = _node(
        "input-boundary",
        "blueprint.input",
        interface_port_id="public.in",
        interface_name="历史输入",
        boundary_binding=BoundaryBinding(
            bound_node_id="middle",
            port_mappings=[
                BoundaryPortMapping(
                    interface_port_id="public.in",
                    target_port_id="middle.out",
                )
            ],
        ),
    )
    graph = _graph(
        [
            _node("source", "source"),
            _node("middle", "middle"),
            _node("sink", "sink"),
            boundary,
        ],
        [
            _edge("e1", "source", "source.out", "middle", "middle.in"),
            _edge("e2", "middle", "middle.out", "sink", "sink.in"),
        ],
    )

    plan = BlueprintCompiler.compile(
        graph,
        definitions,
        ActionInvocationModeEnum.SUBFLOW,
        revision_id="revision-1",
    )

    assert plan.revision_id == "revision-1"
    assert {item.node_id for item in plan.skipped_nodes} == {"middle"}
    assert [(edge.source, edge.target) for edge in plan.edges] == [
        ("input-boundary", "sink")
    ]


def test_target_cannot_mix_input_and_output_bindings() -> None:
    definitions = {
        "blueprint.input": _builtin("blueprint.input"),
        "blueprint.output": _builtin("blueprint.output"),
        "source": _ordinary("source", inputs=()),
        "middle": _ordinary("middle"),
        "sink": _ordinary("sink", outputs=()),
    }
    boundaries = [
        _node(
            "input-boundary",
            "blueprint.input",
            interface_port_id="public.in",
            interface_name="输入接口",
            boundary_binding=BoundaryBinding(
                bound_node_id="middle",
                port_mappings=[
                    BoundaryPortMapping(
                        interface_port_id="public.in",
                        target_port_id="middle.out",
                    )
                ],
            ),
        ),
        _node(
            "output-boundary",
            "blueprint.output",
            interface_port_id="public.out",
            interface_name="输出接口",
            boundary_binding=BoundaryBinding(
                bound_node_id="middle",
                port_mappings=[
                    BoundaryPortMapping(
                        interface_port_id="public.out",
                        target_port_id="middle.in",
                    )
                ],
            ),
        ),
    ]
    graph = _graph(
        [
            _node("source", "source"),
            _node("middle", "middle"),
            _node("sink", "sink"),
            *boundaries,
        ],
        [
            _edge("e1", "source", "source.out", "middle", "middle.in"),
            _edge("e2", "middle", "middle.out", "sink", "sink.in"),
        ],
    )

    with pytest.raises(BlueprintBindingValidationError) as error:
        BlueprintCompiler.compile(
            graph,
            definitions,
            ActionInvocationModeEnum.SUBFLOW,
        )

    assert "binding_mixed_direction" in {
        issue.code for issue in error.value.issues
    }


def test_bound_boundary_cannot_keep_data_edges() -> None:
    definitions = {
        "blueprint.input": _builtin("blueprint.input"),
        "source": _ordinary("source", inputs=()),
        "sink": _ordinary("sink"),
        "other": _ordinary("other"),
    }
    boundary = _node(
        "input",
        "blueprint.input",
        interface_port_id="public.in",
        interface_name="输入接口",
        boundary_binding=BoundaryBinding(
            bound_node_id="source",
            port_mappings=[
                BoundaryPortMapping(
                    interface_port_id="public.in",
                    target_port_id="source.out",
                )
            ],
        ),
    )
    graph = _graph(
        [
            boundary,
            _node("source", "source"),
            _node("sink", "sink"),
            _node("other", "other"),
        ],
        [
            _edge("e1", "source", "source.out", "sink", "sink.in"),
            _edge(
                "e2",
                "input",
                "builtin.blueprint.input.value",
                "other",
                "other.in",
            ),
        ],
    )

    with pytest.raises(BlueprintBindingValidationError) as error:
        BlueprintCompiler.compile(
            graph,
            definitions,
            ActionInvocationModeEnum.SUBFLOW,
        )

    assert "binding_boundary_has_data_edge" in {
        issue.code for issue in error.value.issues
    }


def test_bound_target_must_cover_all_connected_ports() -> None:
    definitions = {
        "blueprint.input": _builtin("blueprint.input"),
        "source": _ordinary(
            "source",
            inputs=(),
            outputs=("left", "right"),
        ),
        "left": _ordinary("left"),
        "right": _ordinary("right"),
    }
    boundary = _node(
        "input",
        "blueprint.input",
        interface_port_id="public.in",
        interface_name="输入接口",
        boundary_binding=BoundaryBinding(
            bound_node_id="source",
            port_mappings=[
                BoundaryPortMapping(
                    interface_port_id="public.in",
                    target_port_id="source.left",
                )
            ],
        ),
    )
    graph = _graph(
        [
            boundary,
            _node("source", "source"),
            _node("left", "left"),
            _node("right", "right"),
        ],
        [
            _edge("left", "source", "source.left", "left", "left.in"),
            _edge("right", "source", "source.right", "right", "right.in"),
        ],
    )

    with pytest.raises(BlueprintBindingValidationError) as error:
        BlueprintCompiler.compile(
            graph,
            definitions,
            ActionInvocationModeEnum.SUBFLOW,
        )

    coverage_issue = next(
        issue
        for issue in error.value.issues
        if issue.code == "binding_port_coverage_incomplete"
    )
    assert coverage_issue.details["target_port_ids"] == ["source.right"]


def test_bound_port_must_have_rewritable_edge() -> None:
    definitions = {
        "blueprint.input": _builtin("blueprint.input"),
        "source": _ordinary(
            "source",
            inputs=(),
            outputs=("used", "unused"),
        ),
        "sink": _ordinary("sink"),
    }
    boundary = _node(
        "input",
        "blueprint.input",
        interface_port_id="public.in",
        interface_name="输入接口",
        boundary_binding=BoundaryBinding(
            bound_node_id="source",
            port_mappings=[
                BoundaryPortMapping(
                    interface_port_id="public.in",
                    target_port_id="source.unused",
                )
            ],
        ),
    )
    graph = _graph(
        [boundary, _node("source", "source"), _node("sink", "sink")],
        [_edge("used", "source", "source.used", "sink", "sink.in")],
    )

    with pytest.raises(BlueprintBindingValidationError) as error:
        BlueprintCompiler.compile(
            graph,
            definitions,
            ActionInvocationModeEnum.SUBFLOW,
        )

    assert {
        issue.code for issue in error.value.issues
    } >= {
        "binding_port_not_connected",
        "binding_port_coverage_incomplete",
    }


def test_multiple_outputs_can_replace_distinct_ports_on_same_sink() -> None:
    definitions = {
        "blueprint.output": _builtin("blueprint.output"),
        "left_source": _ordinary("left_source", inputs=()),
        "right_source": _ordinary("right_source", inputs=()),
        "sink": _ordinary("sink", inputs=("left", "right"), outputs=()),
    }
    boundaries = [
        _node(
            "left_output",
            "blueprint.output",
            interface_port_id="public.left",
            interface_name="左输出",
            boundary_binding=BoundaryBinding(
                bound_node_id="sink",
                port_mappings=[
                    BoundaryPortMapping(
                        interface_port_id="public.left",
                        target_port_id="sink.left",
                    )
                ],
            ),
        ),
        _node(
            "right_output",
            "blueprint.output",
            interface_port_id="public.right",
            interface_name="右输出",
            boundary_binding=BoundaryBinding(
                bound_node_id="sink",
                port_mappings=[
                    BoundaryPortMapping(
                        interface_port_id="public.right",
                        target_port_id="sink.right",
                    )
                ],
            ),
        ),
    ]
    graph = _graph(
        [
            *boundaries,
            _node("left_source", "left_source"),
            _node("right_source", "right_source"),
            _node("sink", "sink"),
        ],
        [
            _edge(
                "left",
                "left_source",
                "left_source.out",
                "sink",
                "sink.left",
            ),
            _edge(
                "right",
                "right_source",
                "right_source.out",
                "sink",
                "sink.right",
            ),
        ],
    )

    plan = BlueprintCompiler.compile(
        graph,
        definitions,
        ActionInvocationModeEnum.SUBFLOW,
    )

    assert {item.node_id for item in plan.skipped_nodes} == {"sink"}
    assert {
        (edge.source, edge.target)
        for edge in plan.edges
    } == {
        ("left_source", "left_output"),
        ("right_source", "right_output"),
    }


def test_compile_is_deterministic() -> None:
    definitions = {"a": _ordinary("a"), "b": _ordinary("b")}
    graph = _graph(
        [_node("a", "a"), _node("b", "b")],
        [_edge("e1", "a", "a.out", "b", "b.in")],
    )

    first = BlueprintCompiler.compile(
        graph,
        definitions,
        ActionInvocationModeEnum.STANDALONE,
    )
    second = BlueprintCompiler.compile(
        graph,
        definitions,
        ActionInvocationModeEnum.STANDALONE,
    )

    assert first.model_dump(mode="json") == second.model_dump(mode="json")


def test_unknown_extension_registrations_fail_clearly() -> None:
    definition = _ordinary("native")
    definition.node_kind = ActionNodeKindEnum.BACKEND_NATIVE
    definition.execution = NodeExecutionSpec(
        driver=ActionExecutionDriverEnum.BACKEND_NATIVE,
        handler="missing.handler",
    )
    definition.extension = NativeNodeExtensionSpec(
        compiler_adapter="missing.adapter",
        execution_policy="missing.policy",
    )
    graph = _graph([_node("native", "native")], [])

    with pytest.raises(ValueError, match="Handler 未注册"):
        BlueprintCompiler.compile(
            graph,
            {"native": definition},
            ActionInvocationModeEnum.STANDALONE,
        )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("values", "expected"),
    [
        (["单值"], "单值"),
        (["上游一", "上游二"], ["上游一", "上游二"]),
    ],
)
async def test_blueprint_output_preserves_single_and_multiple_inputs(
    values,
    expected,
) -> None:
    result = await BlueprintOutputHandler().start(
        NodeExecutionContext(
            action_id="action-1",
            node_instance_id="output-instance",
            node_id="output",
            input_groups={"blueprint_output": values},
            instance_config={
                "_compiler": {
                    "boundary": {"interface_port_id": "public.out"}
                }
            },
        ),
        NodeExecutionSpec(
            driver=ActionExecutionDriverEnum.BACKEND_NATIVE,
            handler="blueprint.output",
        ),
    )

    assert result.outputs == {"public.out": expected}
