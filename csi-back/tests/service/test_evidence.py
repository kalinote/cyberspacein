from contextlib import asynccontextmanager
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
from pydantic import ValidationError

from app.core.exceptions import ApiException, BadRequestException, ForbiddenException
from app.schemas.evidence import EvidenceGraph, EvidenceNode, EvidenceVersionSource
from app.service import evidence


def note(node_id="n", **values):
    """构造用于多个用例的节点。"""
    return {"id": node_id, "kind": "note", "label": node_id, **values}


@pytest.mark.parametrize(
    "node",
    [
        note(kind="entity"),
        note(kind="chain"),
        note(kind="versions"),
        note(kind="collection"),
        note(
            kind="versions",
            version_source={
                "entity_type": "article",
                "source_id": "p",
                "platform": "站点",
            },
            members=[{"entity_type": "article", "uuid": "e1"}],
        ),
        note(kind="entity", entity={"entity_type": "private-index", "uuid": "e1"}),
    ],
)
def test_rejects_invalid_node_payload(node):
    """拒绝缺失的引用定义及动态节点中的物化成员。"""
    with pytest.raises(ValidationError):
        EvidenceNode.model_validate(node)


def test_graph_allows_relation_cycles_but_rejects_dangling_roots():
    """实体关系可以成环，端点根节点必须存在。"""
    graph = EvidenceGraph(
        title="分析",
        nodes=[note("a"), note("b")],
        edges=[
            {"id": "ab", "source": "a", "target": "b"},
            {"id": "ba", "source": "b", "target": "a"},
        ],
    )
    assert len(graph.edges) == 2
    with pytest.raises(ValidationError):
        EvidenceGraph(
            title="分析",
            nodes=[note("a")],
            edges=[{"id": "e", "source": "a", "target": "missing"}],
        )
    with pytest.raises(ValidationError):
        EvidenceGraph(title="分析", nodes=[note("a"), note("a")])


@pytest.mark.asyncio
async def test_dynamic_versions_requeries_and_never_changes_definition(monkeypatch):
    """新采集版本在下次读取时出现，不修改节点或已建立的关系。"""
    node = EvidenceNode.model_validate(
        note(
            kind="versions",
            version_source={
                "entity_type": "article",
                "source_id": "p",
                "platform": "站点A",
            },
        )
    )
    original = node.model_dump()
    es = SimpleNamespace(
        search=AsyncMock(
            side_effect=[
                {
                    "hits": {
                        "total": {"value": 1},
                        "hits": [{"_id": "e1", "_source": {"title": "初版"}}],
                    }
                },
                {
                    "hits": {
                        "total": {"value": 2},
                        "hits": [
                            {"_id": "e1", "_source": {"title": "初版"}},
                            {"_id": "e2", "_source": {"title": "修改版"}},
                        ],
                    }
                },
            ]
        )
    )
    monkeypatch.setattr(evidence, "get_es", lambda: es)
    monkeypatch.setattr(
        evidence, "has_backend_permissions", AsyncMock(return_value=True)
    )
    first = await evidence.resolve_node(node, object(), 1, 30)
    second = await evidence.resolve_node(node, object(), 1, 30)
    assert first["total"] == 1 and second["total"] == 2
    assert node.model_dump() == original
    assert es.search.await_count == 2
    body = es.search.call_args.kwargs["body"]
    assert {"term": {"source_id.keyword": "p"}} in body["query"]["bool"]["filter"]
    assert {"term": {"platform.keyword": "站点A"}} in body["query"]["bool"]["filter"]
    assert body["size"] == 30 and body["from"] == 0


@pytest.mark.asyncio
async def test_fixed_collection_resolves_only_selected_versions(monkeypatch):
    """固定集合保持选择的成员，不跟随未来版本扩展。"""
    node = EvidenceNode.model_validate(
        note(
            kind="collection",
            members=[
                {"entity_type": "article", "uuid": "e1"},
                {"entity_type": "article", "uuid": "e3"},
            ],
        )
    )
    reader = AsyncMock(
        side_effect=lambda ref, user: {**ref.model_dump(), "title": ref.uuid}
    )
    monkeypatch.setattr(evidence, "read_entity", reader)
    result = await evidence.resolve_node(node, object(), 1, 30)
    assert [item["uuid"] for item in result["items"]] == ["e1", "e3"]
    assert result["total"] == 2


@pytest.mark.asyncio
async def test_child_chain_is_live_reference(monkeypatch):
    """不同父链引用同一个子链时均读取其当前内容。"""
    node = EvidenceNode.model_validate(note(kind="chain", chain_id="child"))
    getter = AsyncMock(
        side_effect=[{"id": "child", "revision": 1}, {"id": "child", "revision": 2}]
    )
    monkeypatch.setattr(evidence, "get_chain", getter)
    monkeypatch.setattr(
        evidence, "has_backend_permissions", AsyncMock(return_value=True)
    )
    assert (await evidence.resolve_node(node, object(), 1, 30))["chain"][
        "revision"
    ] == 1
    assert (await evidence.resolve_node(node, object(), 1, 30))["chain"][
        "revision"
    ] == 2
    assert node.chain_id == "child"


@pytest.mark.asyncio
async def test_content_permission_is_required_even_with_chain_access(monkeypatch):
    """证据链读取权限不能代替原始内容读取权限。"""
    es = SimpleNamespace(search=AsyncMock())
    monkeypatch.setattr(evidence, "get_es", lambda: es)
    monkeypatch.setattr(
        evidence, "has_backend_permissions", AsyncMock(return_value=False)
    )
    with pytest.raises(ForbiddenException):
        await evidence.query_versions(
            EvidenceVersionSource(
                entity_type="article", source_id="p", platform="站点"
            ),
            object(),
            1,
            30,
        )
    es.search.assert_not_called()


@pytest.mark.asyncio
async def test_indirect_child_cycle_and_missing_child_rejected(monkeypatch):
    """拒绝递归子链，但接受多父链共享子链。"""
    documents = {
        "B": {"_id": "B", "nodes": [{"chain_id": "C"}]},
        "C": {"_id": "C", "nodes": [{"chain_id": "A"}]},
    }
    collection = MagicMock()
    collection.find.side_effect = lambda query, projection: SimpleNamespace(
        to_list=AsyncMock(
            return_value=[
                documents[key] for key in query["_id"]["$in"] if key in documents
            ]
        )
    )
    monkeypatch.setattr(
        evidence.EvidenceChainModel, "get_motor_collection", lambda: collection
    )
    graph = EvidenceGraph(title="父链", nodes=[note(kind="chain", chain_id="B")])
    with pytest.raises(BadRequestException, match="引用自身"):
        await evidence.validate_references("A", graph)
    documents["C"]["nodes"] = []
    await evidence.validate_references("A", graph)
    del documents["C"]
    with pytest.raises(BadRequestException, match="不存在"):
        await evidence.validate_references("A", graph)


@asynccontextmanager
async def unlocked():
    """为不涉及租约的存储行为测试提供上下文。"""
    yield


@pytest.mark.asyncio
async def test_stale_write_does_not_overwrite_current_graph(monkeypatch):
    """并发修订冲突不会覆盖服务器数据。"""
    collection = SimpleNamespace(update_one=AsyncMock())
    monkeypatch.setattr(
        evidence.EvidenceChainModel, "get_motor_collection", lambda: collection
    )
    monkeypatch.setattr(evidence, "graph_write_lock", unlocked)
    monkeypatch.setattr(evidence, "get_chain", AsyncMock(return_value={"revision": 3}))
    with pytest.raises(ApiException, match="其他用户修改"):
        await evidence.write_chain(EvidenceGraph(title="旧编辑"), "u", "a", 2)
    collection.update_one.assert_not_called()


@pytest.mark.asyncio
async def test_saved_revision_is_read_before_releasing_write_lock(monkeypatch):
    """响应必须属于本次保存，避免误带入紧随其后的其他用户修订。"""
    collection = SimpleNamespace(insert_one=AsyncMock())
    lease = MagicMock()
    getter = AsyncMock(return_value={"revision": 1})
    events = MagicMock()
    events.attach_mock(getter, "read")
    events.attach_mock(lease.__aexit__, "release")
    monkeypatch.setattr(
        evidence.EvidenceChainModel, "get_motor_collection", lambda: collection
    )
    monkeypatch.setattr(evidence, "graph_write_lock", lambda: lease)
    monkeypatch.setattr(evidence, "get_chain", getter)
    result = await evidence.write_chain(EvidenceGraph(title="新图"), "u")
    assert result["revision"] == 1
    assert [call[0] for call in events.mock_calls] == ["read", "release"]


@pytest.mark.asyncio
async def test_referenced_chain_cannot_be_deleted(monkeypatch):
    """被引用的子链不会因删除操作造成悬空引用。"""
    collection = SimpleNamespace(
        find_one=AsyncMock(return_value={"title": "父链"}), update_one=AsyncMock()
    )
    monkeypatch.setattr(
        evidence.EvidenceChainModel, "get_motor_collection", lambda: collection
    )
    monkeypatch.setattr(evidence, "graph_write_lock", unlocked)
    monkeypatch.setattr(evidence, "get_chain", AsyncMock(return_value={"revision": 1}))
    with pytest.raises(BadRequestException, match="仍被证据链"):
        await evidence.delete_chain("child", 1)
    collection.update_one.assert_not_called()


@pytest.mark.asyncio
async def test_nested_endpoints_are_validated_and_existing_orphans_preserved(
    monkeypatch,
):
    """新关系不能连到不存在的内部节点，历史关系失效后仍保留依据。"""
    graph = EvidenceGraph(
        title="父链",
        nodes=[note(kind="chain", chain_id="child"), note("claim")],
        edges=[{"id": "edge", "source": "n/child-node", "target": "claim"}],
    )
    monkeypatch.setattr(
        evidence, "get_chain", AsyncMock(return_value={"nodes": [note("child-node")]})
    )
    await evidence.validate_endpoints(graph)
    monkeypatch.setattr(evidence, "get_chain", AsyncMock(return_value={"nodes": []}))
    with pytest.raises(BadRequestException, match="内部节点不存在"):
        await evidence.validate_endpoints(graph)
    await evidence.validate_endpoints(
        graph, {"edges": [{"source": "n/child-node", "target": "claim"}]}
    )
