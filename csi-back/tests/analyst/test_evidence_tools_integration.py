"""使用随机临时 MongoDB 库验证工具闭环，不连接模型或改写业务库。"""

import asyncio
import json
import os
from uuid import uuid4

import pytest
from beanie import init_beanie
from motor.motor_asyncio import AsyncIOMotorClient

from app.core.config import settings
from app.models.auth.user import UserModel
from app.models.evidence import EvidenceChainModel
from app.service import evidence
from app.service.analyst import context
from app.service.analyst.tools import evidence as tool_module
from app.service.analyst.tools.registry import build_business_tools


pytestmark = pytest.mark.skipif(
    os.environ.get("CSI_EVIDENCE_TOOL_INTEGRATION") != "1",
    reason="仅在显式启用随机临时库验收时连接 MongoDB",
)


@pytest.fixture
async def isolated_tools(monkeypatch):
    """仅初始化随机测试库的模型，并保证退出时只清理本次测试库。"""
    options = {"serverSelectionTimeoutMS": 5000}
    if settings.MONGODB_USERNAME and settings.MONGODB_PASSWORD:
        options.update(
            username=settings.MONGODB_USERNAME, password=settings.MONGODB_PASSWORD
        )
    client = AsyncIOMotorClient(settings.MONGODB_URL, **options)
    name = "csi_evidence_tools_test_" + uuid4().hex
    database = client[name]
    tokens = []
    try:
        await client.admin.command("ping")
        await init_beanie(
            database=database, document_models=[EvidenceChainModel, UserModel]
        )
        user = UserModel(
            _id="tool-test-user",
            username="tool-test-user",
            display_name="工具验收用户",
            password_hash="仅测试，不能登录",
            is_system=True,
        )
        await user.insert()
        monkeypatch.setattr(evidence, "get_mongodb", lambda: database)
        monkeypatch.setattr(tool_module, "get_mongodb", lambda: database)
        for variable, value in [
            (context.current_agent_id, "test-agent"),
            (context.current_session_id, "test-session"),
            (context.current_initiator_user_id, user.id),
            (context.current_auto_approve_hitl, True),
        ]:
            tokens.append((variable, variable.set(value)))
        names = [
            f"evidence_{name}"
            for name in (
                "list",
                "read",
                "resolve",
                "create",
                "save",
                "validate",
                "delete",
            )
        ]
        yield {tool.name: tool for tool in build_business_tools(names)}, database
    finally:
        for variable, token in reversed(tokens):
            variable.reset(token)
        if database.name == name and name.startswith("csi_evidence_tools_test_"):
            await client.drop_database(name)
        client.close()


async def invoke(tools, name, **arguments):
    """调用真实工具并检查成功响应，错误用例直接读取原始结果。"""
    result = json.loads(await tools[f"evidence_{name}"].execute(**arguments))
    assert result["ok"], result
    return result


@pytest.mark.asyncio
async def test_complete_tool_flow_in_isolated_database(isolated_tools):
    """验证真实落库、实时子链、预演、幂等、CAS 和安全删除的完整链路。"""
    tools, database = isolated_tools
    child = await invoke(
        tools,
        "create",
        title="溯源子链",
        template="trace",
        reason="隔离验收",
        request_id="create-child",
    )
    replay = await invoke(
        tools,
        "create",
        title="溯源子链",
        template="trace",
        reason="隔离验收",
        request_id="create-child",
    )
    assert replay["replayed"] and replay["chain_id"] == child["chain_id"]
    parent = await invoke(
        tools,
        "create",
        title="事件分析",
        tags=["验收"],
        reason="隔离验收",
        request_id="create-parent",
    )
    listing = await invoke(tools, "list", tags=["验收"], page_size=1)
    assert listing["total"] == 1 and listing["items"][0]["id"] == parent["chain_id"]
    edit = {
        "chain_id": parent["chain_id"],
        "expected_revision": 1,
        "request_id": "save-parent",
        "reason": "引用并连接线索",
        "operations": [
            {
                "op": "reference_subchain",
                "client_key": "child1",
                "chain_id": child["chain_id"],
                "label": "溯源",
            },
            {
                "op": "reference_subchain",
                "client_key": "child2",
                "chain_id": child["chain_id"],
                "label": "共享引用",
            },
            {
                "op": "add_node",
                "client_key": "claim",
                "node": {"kind": "note", "label": "待验证判断"},
            },
            {
                "op": "add_edge",
                "client_key": "relation",
                "edge": {
                    "source": f"$child1/{child['id_map']['node_1']}",
                    "target": "$claim",
                    "label": "补充",
                },
            },
            {"op": "auto_layout", "layout": "tree"},
        ],
    }
    saved = await invoke(tools, "save", **edit)
    assert saved["revision"] == 2 and saved["changes"]["nodes"]["added"] == 3
    replay = await invoke(tools, "save", **edit)
    assert replay["replayed"] and replay["revision"] == 2
    resolved = await invoke(
        tools,
        "resolve",
        chain_id=parent["chain_id"],
        node_id=saved["id_map"]["child1"],
        page_size=1,
    )
    assert resolved["has_more"] and resolved["chain"]["revision"] == 1
    assert resolved["items"][0]["endpoint_id"].startswith(
        saved["id_map"]["child1"] + "/"
    )
    await invoke(
        tools,
        "save",
        chain_id=child["chain_id"],
        expected_revision=1,
        reason="验证指针",
        request_id="save-child",
        operations=[
            {
                "op": "update_node",
                "node_id": child["id_map"]["node_1"],
                "patch": {"label": "更新后的事件起点"},
            }
        ],
    )
    resolved = await invoke(
        tools, "resolve", chain_id=parent["chain_id"], node_id=saved["id_map"]["child2"]
    )
    assert (
        resolved["chain"]["revision"] == 2
        and resolved["items"][0]["label"] == "更新后的事件起点"
    )
    preview = await invoke(
        tools,
        "validate",
        chain_id=parent["chain_id"],
        expected_revision=2,
        operations=[
            {
                "op": "move_nodes",
                "positions": [{"node_id": saved["id_map"]["child1"], "x": 99, "y": 88}],
            }
        ],
    )
    assert preview["valid"] and preview["diff"]["nodes"]["updated"]
    unchanged = await invoke(tools, "read", chain_id=parent["chain_id"])
    assert unchanged["revision"] == 2
    invalid = json.loads(
        await tools["evidence_save"].execute(
            chain_id=parent["chain_id"],
            expected_revision=2,
            reason="验证原子失败",
            request_id="bad-batch",
            operations=[
                {"op": "set_metadata", "metadata": {"title": "不应提交"}},
                {"op": "remove_node", "node_id": "missing"},
            ],
        )
    )
    assert not invalid["ok"]
    assert (await invoke(tools, "read", chain_id=parent["chain_id"]))[
        "title"
    ] == "事件分析"
    blocked = json.loads(
        await tools["evidence_delete"].execute(
            chain_id=child["chain_id"],
            expected_revision=2,
            reason="仍被引用",
            request_id="blocked-delete",
        )
    )
    assert (
        not blocked["ok"] and blocked["validation"]["affected_references"]["total"] == 1
    )
    args = {
        "chain_id": parent["chain_id"],
        "expected_revision": 2,
        "reason": "并发修订检查",
        "operations": [{"op": "set_metadata", "metadata": {"description": "并发修改"}}],
    }
    results = [
        json.loads(raw)
        for raw in await asyncio.gather(
            *(
                tools["evidence_save"].execute(**args, request_id=f"concurrent-{index}")
                for index in range(2)
            )
        )
    ]
    assert sum(result["ok"] for result in results) == 1
    assert (
        next(result for result in results if not result["ok"])["error"]["code"]
        == 240409
    )
    removed = await invoke(
        tools,
        "save",
        chain_id=parent["chain_id"],
        expected_revision=3,
        reason="移除一个引用",
        request_id="remove-one",
        operations=[
            {
                "op": "remove_subchain_reference",
                "node_id": saved["id_map"]["child1"],
                "edge_policy": "remove_connected",
            }
        ],
    )
    assert removed["revision"] == 4
    parent_read = await invoke(tools, "read", chain_id=parent["chain_id"])
    assert len(parent_read["nodes"]) == 2 and not parent_read["edges"]
    assert (await invoke(tools, "read", chain_id=child["chain_id"]))["revision"] == 2
    await invoke(
        tools,
        "delete",
        chain_id=parent["chain_id"],
        expected_revision=4,
        reason="清理父链",
        request_id="delete-parent",
    )
    assert (await invoke(tools, "read", chain_id=child["chain_id"]))["node_count"] == 3
    await invoke(
        tools,
        "delete",
        chain_id=child["chain_id"],
        expected_revision=2,
        reason="清理子链",
        request_id="delete-child",
    )
    assert await database.evidence_chains.count_documents({"deleted": True}) == 2
    assert (
        await database.evidence_agent_requests.count_documents({"status": "succeeded"})
        == 8
    )
    assert await database.evidence_graph_locks.count_documents({}) == 0
