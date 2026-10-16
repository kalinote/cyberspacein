"""证据链工具的批量编辑、权限、审批和来源校验回归测试。"""

import json
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
from pydantic import ValidationError

from app.core.exceptions import ForbiddenException
from app.schemas.agent.evidence import EvidenceCreateInput, EvidenceOperation
from app.schemas.evidence import EvidenceEntityRef, EvidenceGraph, EvidenceNode
from app.service import evidence
from app.service.analyst import context, evidence as access
from app.service.analyst.hitl import HitlOutcome
from app.service.analyst.tools import evidence as tool_module
from app.service.analyst.tools.registry import build_business_tools
from app.service.evidence_graph import apply_operations, create_graph, graph_diff


def graph_data(**values):
    """生成含真实模型默认值的测试图。"""
    return {
        "id": "chain",
        "revision": 1,
        **EvidenceGraph(title="测试", **values).model_dump(),
    }


def operations(*values):
    """将多种测试操作转换为执行使用的严格模型。"""
    return [EvidenceOperation.model_validate(value) for value in values]


def node(node_id, kind="note", **values):
    """构造各种节点并统一填充模型默认字段。"""
    return EvidenceNode(id=node_id, kind=kind, label=node_id, **values).model_dump()


@pytest.fixture
def validation_services(monkeypatch):
    """隔离源数据库，并允许测试按需替换具体读取行为。"""
    monkeypatch.setattr(evidence, "require_content_access", AsyncMock())
    monkeypatch.setattr(evidence, "validate_references", AsyncMock())
    monkeypatch.setattr(
        access,
        "referencing_chains",
        AsyncMock(return_value={"total": 0, "items": [], "truncated": False}),
    )
    reader = AsyncMock(
        return_value={
            "clean_content": "可核对的原文",
            "source_id": "post",
            "platform": "站点",
        }
    )
    monkeypatch.setattr(access, "read_source", reader)
    monkeypatch.setattr(
        evidence, "query_versions", AsyncMock(return_value={"total": 1, "items": []})
    )
    return reader


@pytest.fixture
def write_services(monkeypatch, validation_services):
    """提供可重复调用的幂等记录及审批上下文，不访问真实数据库。"""
    stored = {}
    records = MagicMock()
    records.find_one = AsyncMock(
        side_effect=lambda query: deepcopy(stored.get(query["_id"]))
    )

    async def insert(document):
        """模拟 MongoDB 默认唯一主键。"""
        if document["_id"] in stored:
            raise tool_module.DuplicateKeyError("重复请求")
        stored[document["_id"]] = deepcopy(document)

    async def update(query, update):
        """模拟幂等记录的原子字段更新。"""
        stored[query["_id"]].update(deepcopy(update["$set"]))

    records.insert_one = AsyncMock(side_effect=insert)
    records.update_one = AsyncMock(side_effect=update)
    monkeypatch.setattr(
        tool_module, "get_mongodb", lambda: {"evidence_agent_requests": records}
    )
    monkeypatch.setattr(tool_module, "get_current_agent_id", lambda: "agent")
    monkeypatch.setattr(tool_module, "get_current_session_id", lambda: "session")
    user = SimpleNamespace(id="user")
    monkeypatch.setattr(access, "require_evidence_user", AsyncMock(return_value=user))
    approval = AsyncMock(
        return_value=HitlOutcome(
            approved=[{"action": "approve"}],
            rejections=[],
            resolution="approved",
            approval_request_id="approval",
            raw={},
        )
    )
    monkeypatch.setattr(tool_module.HitlService, "request_approval", approval)
    writer = AsyncMock(
        side_effect=lambda graph, operator, **kwargs: {
            **graph.model_dump(),
            "id": kwargs.get("chain_id") or "created",
            "revision": (kwargs.get("expected_revision") or 0) + 1,
        }
    )
    monkeypatch.setattr(evidence, "write_chain", writer)
    return SimpleNamespace(
        stored=stored, records=records, approval=approval, writer=writer
    )


def test_tools_registered_with_write_isolation():
    """白名单能发现全部工具，读写调度属性正确。"""
    names = [
        f"evidence_{name}"
        for name in ("list", "read", "resolve", "create", "save", "validate", "delete")
    ]
    tools = build_business_tools(names)
    assert [tool.name for tool in tools] == names
    for tool in tools:
        writing = tool.name in {"evidence_create", "evidence_save", "evidence_delete"}
        assert tool.read_only is not writing
        assert tool.exclusive is writing
        assert tool.parameters["additionalProperties"] is False


@pytest.mark.parametrize(
    "template,labels",
    [
        ("blank", []),
        ("proof", ["支持材料", "待验证判断", "反证与疑点"]),
        ("expansion", ["核心线索", "相关背景", "外部影响"]),
        ("trace", ["事件起点", "后续变化", "当前状态"]),
    ],
)
def test_templates_initialize_drafts(template, labels):
    """模板初始化独立节点，时间先后不会自动标记为事实确认。"""
    data = EvidenceCreateInput(
        title="分析", template=template, request_id="r", reason="测试"
    )
    first, second = create_graph(data), create_graph(data)
    assert first.status == "draft"
    assert [item.label for item in first.nodes] == labels
    assert not {item.id for item in first.nodes} & {item.id for item in second.nodes}
    assert all(edge.status == "pending" for edge in first.edges)


def test_batch_temp_ids_all_node_types_and_edges():
    """同批建立各种引用、连线及布局，原图和全局数据不变。"""
    before = graph_data()
    original = deepcopy(before)
    refs = [{"entity_type": "article", "uuid": "v1"}]
    graph, ids = apply_operations(
        before,
        operations(
            {
                "op": "add_node",
                "client_key": "entity",
                "node": {"kind": "entity", "label": "初版", "entity": refs[0]},
            },
            {
                "op": "add_node",
                "client_key": "group",
                "node": {"kind": "collection", "label": "选择版本", "members": refs},
            },
            {
                "op": "add_node",
                "client_key": "versions",
                "node": {
                    "kind": "versions",
                    "label": "全部版本",
                    "version_source": {
                        "entity_type": "article",
                        "source_id": "post",
                        "platform": "站点",
                    },
                },
            },
            {
                "op": "reference_subchain",
                "client_key": "child",
                "chain_id": "child-id",
                "label": "子链",
            },
            {
                "op": "add_edge",
                "client_key": "edge",
                "edge": {"source": "$group/@article:v1", "target": "$child/inside"},
            },
            {
                "op": "move_nodes",
                "positions": [{"node_id": "$child", "x": 340, "y": 80}],
            },
            {"op": "set_metadata", "metadata": {"tags": ["测试"]}},
        ),
    )
    assert before == original
    assert graph.edges[0].source == f"{ids['group']}/@article:v1"
    assert graph.edges[0].target == f"{ids['child']}/inside"
    assert graph.nodes[2].members == []
    assert graph.nodes[3].chain_id == "child-id"
    assert graph.nodes[3].position.x == 340


def test_failed_batch_never_changes_original():
    """最后一个操作失败时，前面的元数据修改也不生效。"""
    before = graph_data(nodes=[node("a")])
    original = deepcopy(before)
    with pytest.raises(ValueError, match="不存在节点"):
        apply_operations(
            before,
            operations(
                {"op": "set_metadata", "metadata": {"title": "不应保存"}},
                {"op": "remove_node", "node_id": "missing"},
            ),
        )
    assert before == original


@pytest.mark.parametrize(
    "operation",
    [
        {"op": "remove_node", "node_id": "a", "node_ids": ["a"]},
        {
            "op": "add_node",
            "client_key": "a",
            "node": {"id": "forged", "kind": "note", "label": "伪造ID"},
        },
        {"op": "update_node", "node_id": "a", "patch": {"label": None}},
        {"op": "set_metadata", "metadata": {}},
        {
            "op": "move_nodes",
            "positions": [{"node_id": "a", "x": float("inf"), "y": 0}],
        },
    ],
)
def test_strict_operation_contract(operation):
    """拒绝多余字段、空修改、伪造身份和非有限坐标。"""
    with pytest.raises(ValidationError):
        EvidenceOperation.model_validate(operation)


def test_remove_reference_uses_local_node_and_edge_policy():
    """同一子链的多个引用按本链节点区分，移除时明确处理内部连线。"""
    before = graph_data(
        nodes=[
            node("a", "chain", chain_id="child"),
            node("b", "chain", chain_id="child"),
        ],
        edges=[{"id": "e", "source": "a/inside", "target": "b"}],
    )
    with pytest.raises(ValueError, match="仍有"):
        apply_operations(
            before, operations({"op": "remove_subchain_reference", "node_id": "a"})
        )
    after, _ = apply_operations(
        before,
        operations(
            {
                "op": "remove_subchain_reference",
                "node_id": "a",
                "edge_policy": "remove_connected",
            }
        ),
    )
    assert [item.id for item in after.nodes] == ["b"]
    assert after.nodes[0].chain_id == "child" and not after.edges
    with pytest.raises(ValueError, match="remove_subchain_reference"):
        apply_operations(before, operations({"op": "remove_node", "node_id": "a"}))


def test_collection_member_change_protects_existing_edges():
    """移除成员同步检查该成员端点，不允许残留悬空关系。"""
    first, second = (
        {"entity_type": "article", "uuid": "v1"},
        {"entity_type": "article", "uuid": "v2"},
    )
    before = graph_data(
        nodes=[node("a", "collection", members=[first, second]), node("b")],
        edges=[{"id": "e", "source": "a/@article:v1", "target": "b"}],
    )
    operation = {
        "op": "update_collection_members",
        "node_id": "a",
        "members": [first],
        "member_mode": "remove",
    }
    with pytest.raises(ValueError, match="仍有"):
        apply_operations(before, operations(operation))
    after, _ = apply_operations(
        before, operations({**operation, "edge_policy": "remove_connected"})
    )
    assert [item.uuid for item in after.nodes[0].members] == ["v2"]
    assert not after.edges


@pytest.mark.parametrize("layout", ["grid", "tree"])
def test_layout_handles_cycles_scope_and_locked_nodes(layout):
    """环路布局能够终止，保留锁定位置和范围外的节点。"""
    before = graph_data(
        nodes=[node("a"), node("b"), node("c", position={"x": 80, "y": 80})],
        edges=[
            {"id": "ab", "source": "a", "target": "b"},
            {"id": "ba", "source": "b", "target": "a"},
        ],
    )
    after, _ = apply_operations(
        before,
        operations(
            {
                "op": "auto_layout",
                "layout": layout,
                "node_ids": ["a", "b"],
                "locked_node_ids": ["a"],
            }
        ),
    )
    assert after.nodes[0].position.model_dump() == before["nodes"][0]["position"]
    assert after.nodes[2].position.model_dump() == before["nodes"][2]["position"]
    assert after.nodes[1].position != after.nodes[2].position


def test_update_nodes_edges_and_compact_position_diff():
    """修改类型受约束，位置差异只包含位置而不是重复整个节点。"""
    before = graph_data(
        nodes=[node("a"), node("b")], edges=[{"id": "e", "source": "a", "target": "b"}]
    )
    after, _ = apply_operations(
        before,
        operations(
            {
                "op": "update_node",
                "node_id": "a",
                "patch": {"label": "判断", "attributes": {"备注": "待查"}},
            },
            {
                "op": "update_edge",
                "edge_id": "e",
                "edge_patch": {"label": "补充", "status": "disputed"},
            },
            {"op": "move_nodes", "positions": [{"node_id": "b", "x": 999, "y": -20}]},
        ),
    )
    diff = graph_diff(before, after)
    assert diff["nodes"]["updated"][1]["changes"] == {
        "position": {"before": {"x": 0.0, "y": 0.0}, "after": {"x": 999.0, "y": -20.0}}
    }
    assert after.edges[0].status == "disputed"


@pytest.mark.asyncio
async def test_original_quote_and_version_membership(validation_services):
    """新依据摘录不匹配或实体不属于该动态来源时必须拒绝。"""
    ref = {"entity_type": "article", "uuid": "v1"}
    graph = EvidenceGraph(
        title="分析",
        nodes=[
            node(
                "v",
                "versions",
                version_source={
                    "entity_type": "article",
                    "source_id": "wrong",
                    "platform": "站点",
                },
            ),
            node("a"),
        ],
        edges=[
            {
                "id": "e",
                "source": "v/@article:v1",
                "target": "a",
                "anchors": [{"entity": ref, "quote": "不存在的原文"}],
            }
        ],
    )
    result = await access.validate_graph("chain", graph, None, object())
    assert not result["valid"]
    assert {item["code"] for item in result["errors"]} == {
        "invalid_endpoint",
        "invalid_anchor",
    }


@pytest.mark.asyncio
async def test_full_source_quote_not_limited_to_preview(monkeypatch):
    """原文校验使用完整正文，不能误用两千字预览。"""
    monkeypatch.setattr(evidence, "require_content_access", AsyncMock())
    es = SimpleNamespace(
        get=AsyncMock(
            return_value={"_source": {"clean_content": "长" * 3000 + "末尾依据"}}
        )
    )
    monkeypatch.setattr(evidence, "get_es", lambda: es)
    source = await access.read_source(
        EvidenceEntityRef(entity_type="article", uuid="v1"), object(), {}
    )
    assert (
        source["clean_content"].endswith("末尾依据")
        and len(source["clean_content"]) > 3000
    )


@pytest.mark.asyncio
async def test_legacy_missing_source_does_not_block_position_fix(validation_services):
    """既有源数据失效时仍可调整图位置，校验保留明确警告。"""
    validation_services.return_value = {"missing": True}
    before = graph_data(
        nodes=[node("a", "entity", entity={"entity_type": "article", "uuid": "gone"})]
    )
    graph, _ = apply_operations(
        before,
        operations(
            {"op": "move_nodes", "positions": [{"node_id": "a", "x": 1, "y": 2}]}
        ),
    )
    result = await access.validate_graph("chain", graph, before, object())
    assert result["valid"] and result["warnings"][0]["code"] == "missing_entity"


@pytest.mark.asyncio
async def test_create_is_idempotent_and_audited(write_services):
    """不同工具调用 ID 复用请求标识也只创建一次，并保留操作者上下文。"""
    tool = tool_module.EvidenceCreateTool()
    args = {"title": "分析", "template": "trace", "reason": "溯源", "request_id": "r1"}
    first = json.loads(await tool.execute(**args))
    second = json.loads(await tool.execute(**args))
    assert first["ok"] and second["replayed"]
    assert first["chain_id"] == second["chain_id"]
    assert len(first["id_map"]) == 5
    assert write_services.writer.await_count == write_services.approval.await_count == 1
    record = next(iter(write_services.stored.values()))
    assert record["initiator_user_id"] == "user" and record["agent_id"] == "agent"
    assert record["status"] == "succeeded"
    conflict = json.loads(await tool.execute(**{**args, "title": "另一分析"}))
    assert not conflict["ok"] and "不同参数" in conflict["error"]["message"]


@pytest.mark.asyncio
async def test_rejected_approval_never_writes(write_services):
    """拒绝审批后不保存，并使相同请求重试保持拒绝结果。"""
    write_services.approval.return_value = HitlOutcome(
        approved=[],
        rejections=["不需要"],
        resolution="rejected",
        approval_request_id="rejected",
        raw={},
    )
    args = {"title": "分析", "reason": "测试", "request_id": "rejected"}
    result = json.loads(await tool_module.EvidenceCreateTool().execute(**args))
    replay = json.loads(await tool_module.EvidenceCreateTool().execute(**args))
    assert result["error"]["code"] == "approval_rejected" and replay["replayed"]
    write_services.writer.assert_not_awaited()


@pytest.mark.asyncio
async def test_unknown_write_is_not_repeated(write_services):
    """网络中断可能已写入，不能因重试而再次创建。"""
    write_services.writer.side_effect = RuntimeError("模拟提交后断网")
    args = {"title": "分析", "reason": "测试", "request_id": "unknown"}
    await tool_module.EvidenceCreateTool().execute(**args)
    result = json.loads(await tool_module.EvidenceCreateTool().execute(**args))
    assert result["error"]["code"] == "request_in_progress_or_unknown"
    assert write_services.writer.await_count == 1


@pytest.mark.asyncio
async def test_permission_rechecked_after_approval(write_services):
    """审批等待期间撤销权限，批准后仍不能写入。"""
    access.require_evidence_user.side_effect = [
        SimpleNamespace(id="user"),
        ForbiddenException("权限已撤销"),
    ]
    result = json.loads(
        await tool_module.EvidenceCreateTool().execute(
            title="分析", reason="测试", request_id="revoked"
        )
    )
    assert not result["ok"] and "撤销" in result["error"]["message"]
    write_services.writer.assert_not_awaited()


@pytest.mark.asyncio
async def test_save_stale_revision_stops_before_approval(monkeypatch, write_services):
    """乐观锁冲突不触发审批或覆盖最新编辑。"""
    monkeypatch.setattr(
        evidence, "get_chain", AsyncMock(return_value={**graph_data(), "revision": 2})
    )
    result = json.loads(
        await tool_module.EvidenceSaveTool().execute(
            chain_id="chain",
            expected_revision=1,
            operations=[{"op": "set_metadata", "metadata": {"title": "新名称"}}],
            reason="测试",
            request_id="stale",
        )
    )
    assert result["error"]["code"] == 240409
    write_services.approval.assert_not_awaited()
    write_services.writer.assert_not_awaited()


@pytest.mark.asyncio
async def test_validate_is_read_only(monkeypatch, write_services):
    """预演返回变更但不申请审批或写入请求记录。"""
    before = graph_data(nodes=[node("a")])
    monkeypatch.setattr(evidence, "get_chain", AsyncMock(return_value=before))
    result = json.loads(
        await tool_module.EvidenceValidateTool().execute(
            chain_id="chain",
            operations=[
                {"op": "update_node", "node_id": "a", "patch": {"label": "拟修改"}}
            ],
        )
    )
    assert result["valid"] and result["diff"]["nodes"]["updated"]
    assert before["nodes"][0]["label"] == "a"
    write_services.records.insert_one.assert_not_awaited()
    write_services.approval.assert_not_awaited()


@pytest.mark.asyncio
async def test_user_identity_required_and_expiration_enforced(monkeypatch):
    """系统任务也不能无用户身份写图，过期账号不能沿用旧授权。"""
    token = context.current_initiator_user_id.set(None)
    try:
        with pytest.raises(ForbiddenException, match="发起用户"):
            await access.require_evidence_user("read")
        context.current_initiator_user_id.set("user")
        user = SimpleNamespace(
            enabled=True, expired_at=datetime.now(timezone.utc) - timedelta(seconds=1)
        )
        monkeypatch.setattr(access.UserModel, "find_one", AsyncMock(return_value=user))
        with pytest.raises(ForbiddenException, match="到期"):
            await access.require_evidence_user("update")
        user.expired_at = None
        checker = AsyncMock(return_value=False)
        monkeypatch.setattr(access, "has_backend_permissions", checker)
        with pytest.raises(ForbiddenException):
            await access.require_evidence_user("delete")
        assert checker.call_args.args[1] == [
            "operation:evidence:chain:read",
            "operation:evidence:chain:delete",
        ]
    finally:
        context.current_initiator_user_id.reset(token)


@pytest.mark.asyncio
async def test_source_permissions_are_not_bypassed(monkeypatch):
    """读取图中的实体摘录仍需相应实体读取权限。"""
    monkeypatch.setattr(
        evidence, "has_backend_permissions", AsyncMock(return_value=False)
    )
    graph = graph_data(
        nodes=[node("a")],
        edges=[
            {
                "id": "e",
                "source": "a",
                "target": "a",
                "anchors": [
                    {
                        "entity": {"entity_type": "forum", "uuid": "post"},
                        "quote": "私有内容",
                    }
                ],
            }
        ],
    )
    with pytest.raises(ForbiddenException):
        await access.require_graph_content_access(graph, object())


@pytest.mark.asyncio
async def test_resolve_nested_live_child_and_paginated_endpoints(monkeypatch):
    """子链解析带当前修订，返回父链内可用的完整端点路径。"""
    parent = graph_data(nodes=[node("child", "chain", chain_id="child-id")])
    child = {
        **graph_data(nodes=[node("inside"), node("other")]),
        "id": "child-id",
        "revision": 9,
    }
    monkeypatch.setattr(evidence, "get_chain", AsyncMock(return_value=child))
    result = await access.resolve_graph_node(parent, "child", object(), 1, 1)
    assert result["chain"]["revision"] == 9 and result["has_more"]
    assert result["items"][0]["endpoint_id"] == "child/inside"
    nested = await access.resolve_graph_node(parent, "child/inside", object(), 1, 1)
    assert nested["owner_chain_id"] == "child-id" and nested["owner_revision"] == 9


def test_graph_read_pages_nodes_and_edges_independently():
    """图分页不会把第一页误报为完整图。"""
    graph = graph_data(
        nodes=[node("a"), node("b")], edges=[{"id": "e", "source": "a", "target": "b"}]
    )
    first = access.read_graph_page(graph, "graph", 1, 1)
    assert first["nodes_has_more"] and not first["edges_has_more"]
    assert first["node_count"] == 2 and first["edge_count"] == 1
    second = access.read_graph_page(graph, "nodes", 2, 1)
    assert second["nodes"][0]["id"] == "b" and "edges" not in second
