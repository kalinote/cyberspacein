"""app.utils.workflow 蓝图图论辅助函数测试。"""

from app.models.action.blueprint import (
    ActionBlueprintModel,
    GraphEdgeModel,
    GraphModel,
    GraphNodeModel,
    NodeDataModel,
    PositionModel,
    ViewportModel,
)
from app.schemas.action.blueprint import GraphSchema
from app.utils.workflow import count_workflow_paths, find_start_nodes, graph_model2schemas


def _node(nid: str) -> GraphNodeModel:
    return GraphNodeModel(
        id=nid,
        type="logic",
        position=PositionModel(x=0, y=0),
        data=NodeDataModel(definition_id="d", version="1", form_data=[]),
    )


def test_find_start_nodes_linear_chain():
    # 链式 A->B->C 仅 A 入度为 0
    g = GraphModel(
        nodes=[_node("a"), _node("b"), _node("c")],
        edges=[
            GraphEdgeModel(id="e1", source="a", sourceHandle="o", target="b", targetHandle="i"),
            GraphEdgeModel(id="e2", source="b", sourceHandle="o", target="c", targetHandle="i"),
        ],
        viewport=ViewportModel(x=0, y=0, zoom=1),
    )
    bp = ActionBlueprintModel.model_construct(
        id="bp1",
        name="n",
        version="1",
        description="d",
        target="t",
        implementation_period=1,
        graph=g,
    )
    starts = find_start_nodes(bp)
    assert [n.id for n in starts] == ["a"]


def test_count_workflow_paths_single_path():
    # 单链从起点到叶仅一条完整路径
    g = GraphModel(
        nodes=[_node("a"), _node("b")],
        edges=[
            GraphEdgeModel(id="e1", source="a", sourceHandle="o", target="b", targetHandle="i"),
        ],
        viewport=ViewportModel(x=0, y=0, zoom=1),
    )
    bp = ActionBlueprintModel.model_construct(
        id="bp2",
        name="n",
        version="1",
        description="d",
        target="t",
        implementation_period=1,
        graph=g,
    )
    assert count_workflow_paths(bp) == 1


def test_graph_model2schemas_shape():
    # GraphModel 转 API Schema 后节点与边数量一致
    g = GraphModel(
        nodes=[_node("n1")],
        edges=[],
        viewport=ViewportModel(x=1, y=2, zoom=0.5),
    )
    sch = graph_model2schemas(g)
    assert isinstance(sch, GraphSchema)
    assert len(sch.nodes) == 1
    assert sch.viewport.zoom == 0.5
