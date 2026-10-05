"""对隔离验收服务进行真实 HTTP、鉴权与 MongoDB 往返测试。"""

import asyncio
import os
from uuid import uuid4

import httpx
import pytest

from app.core.config import settings
from app.schemas.evidence import EvidenceGraph


pytestmark = pytest.mark.skipif(
    os.environ.get("CSI_EVIDENCE_PREVIEW_TEST") != "1",
    reason="需要显式启动本机隔离验收服务",
)


@pytest.fixture
async def client():
    """在验明临时数据库后登录，绝不向部署环境写入测试图。"""
    async with httpx.AsyncClient(
        base_url="http://127.0.0.1:8082", timeout=20, trust_env=False
    ) as http:
        status = (await http.get("/health/evidence-preview")).json()["data"]
        assert status["temporary"] is True and status["database"].startswith(
            "csi_evidence_preview_"
        )
        response = (
            await http.post(
                "/api/v1/auth/login",
                json={
                    "username": settings.INIT_SYSTEM_USERNAME,
                    "password": settings.INIT_SYSTEM_PASSWORD,
                },
            )
        ).json()
        assert response["code"] == 0
        http.headers["Authorization"] = "Bearer " + response["data"]["access_token"]
        yield http
        await http.post("/api/v1/auth/logout", json={})


async def create_graph(client, title, **values):
    """创建本组测试专用图并检查成功响应。"""
    data = EvidenceGraph(title=title, **values).model_dump()
    response = (await client.post("/api/v1/evidence/chains", json=data)).json()
    assert response["code"] == 0, response
    return response["data"]


async def save_graph(client, graph):
    """使用服务器修订号保存图定义。"""
    payload = {key: graph[key] for key in EvidenceGraph.model_fields}
    return (
        await client.put(
            f"/api/v1/evidence/chains/{graph['id']}",
            json={**payload, "expected_revision": graph["revision"]},
        )
    ).json()


@pytest.mark.asyncio
async def test_roundtrip_composition_conflict_and_unlink(client):
    """覆盖创建、保存、子链实时引用、并发冲突、解引用和删除。"""
    suffix = uuid4().hex[:8]
    child = await create_graph(
        client,
        f"接口验收子链-{suffix}",
        nodes=[{"id": "event", "kind": "note", "label": "初始事件"}],
    )
    parent = await create_graph(
        client,
        f"接口验收父链-{suffix}",
        nodes=[
            {
                "id": "child",
                "kind": "chain",
                "label": "发展过程",
                "chain_id": child["id"],
            },
            {"id": "claim", "kind": "note", "label": "待验证判断"},
        ],
        edges=[
            {
                "id": "link",
                "source": "child/event",
                "target": "claim",
                "label": "补充",
                "description": "子链中的事件补充判断背景",
            }
        ],
    )
    try:
        child["nodes"][0]["label"] = "事件发生变化"
        updated = await save_graph(client, child)
        assert updated["code"] == 0 and updated["data"]["revision"] == 2
        assert updated["data"]["updated_at"].endswith(("Z", "+00:00"))
        stale = await save_graph(client, child)
        assert stale["code"] == 240409
        resolved = (
            await client.post(
                "/api/v1/evidence/resolve", json={"node": parent["nodes"][0]}
            )
        ).json()
        assert resolved["data"]["chain"]["nodes"][0]["label"] == "事件发生变化"
        assert resolved["data"]["chain"]["revision"] == 2
        stored = (await client.get(f"/api/v1/evidence/chains/{parent['id']}")).json()[
            "data"
        ]
        assert (
            stored["nodes"][0]["chain_id"] == child["id"]
            and "chain" not in stored["nodes"][0]
        )
        assert stored["edges"][0]["source"] == "child/event"
        blocked = (
            await client.delete(
                f"/api/v1/evidence/chains/{child['id']}",
                params={"expected_revision": 2},
            )
        ).json()
        assert blocked["code"] != 0 and "仍被" in blocked["message"]
        parent["nodes"] = [parent["nodes"][1]]
        parent["edges"] = []
        assert (await save_graph(client, parent))["code"] == 0
        assert (await client.get(f"/api/v1/evidence/chains/{child['id']}")).json()[
            "data"
        ]["revision"] == 2
        listed = (
            await client.get("/api/v1/evidence/chains", params={"q": suffix})
        ).json()["data"]
        assert listed["total"] == 2
    finally:
        for graph in (parent, child):
            current = (
                (await client.get(f"/api/v1/evidence/chains/{graph['id']}"))
                .json()
                .get("data")
            )
            if current:
                await client.delete(
                    f"/api/v1/evidence/chains/{graph['id']}",
                    params={"expected_revision": current["revision"]},
                )


@pytest.mark.asyncio
async def test_concurrent_cross_reference_cannot_form_cycle(client):
    """两个请求同时互相引用时，最多一个保存成功。"""
    first = await create_graph(client, "并发验收 A")
    second = await create_graph(client, "并发验收 B")
    first["nodes"] = [
        {"id": "b", "kind": "chain", "label": "B", "chain_id": second["id"]}
    ]
    second["nodes"] = [
        {"id": "a", "kind": "chain", "label": "A", "chain_id": first["id"]}
    ]
    try:
        results = await asyncio.gather(
            save_graph(client, first), save_graph(client, second)
        )
        assert sum(result["code"] == 0 for result in results) == 1
        assert any(
            "引用自身" in result["message"] for result in results if result["code"] != 0
        )
    finally:
        cleared_graphs = []
        for graph in (first, second):
            current = (
                await client.get(f"/api/v1/evidence/chains/{graph['id']}")
            ).json()["data"]
            current["nodes"] = []
            cleared = (await save_graph(client, current))["data"]
            cleared_graphs.append(cleared)
        for graph in cleared_graphs:
            removed = (
                await client.delete(
                    f"/api/v1/evidence/chains/{graph['id']}",
                    params={"expected_revision": graph["revision"]},
                )
            ).json()
            assert removed["code"] == 0


@pytest.mark.asyncio
async def test_entity_version_query_and_fixed_group_real_data(client):
    """对已有实体执行只读解析，动态组与固定组均能返回原始版本。"""
    reference = {
        "id": "entity",
        "kind": "entity",
        "label": "来源文章",
        "entity": {
            "entity_type": "article",
            "uuid": "20499157e43fd71f89c5174e03d97c19",
        },
    }
    result = (
        await client.post("/api/v1/evidence/resolve", json={"node": reference})
    ).json()
    assert result["code"] == 0
    entity = result["data"]["items"][0]
    assert not entity.get("missing")
    versions = {
        "id": "versions",
        "kind": "versions",
        "label": "全部版本",
        "version_source": {
            "entity_type": "article",
            "source_id": entity["source_id"],
            "platform": entity["platform"],
        },
    }
    result = (
        await client.post("/api/v1/evidence/resolve", json={"node": versions})
    ).json()
    assert result["code"] == 0 and result["data"]["total"] >= 1
    assert all(
        item["source_id"] == entity["source_id"]
        and item["platform"] == entity["platform"]
        for item in result["data"]["items"]
    )
    fixed = {
        "id": "fixed",
        "kind": "collection",
        "label": "指定版本",
        "members": [reference["entity"]],
    }
    result = (
        await client.post("/api/v1/evidence/resolve", json={"node": fixed})
    ).json()
    assert (
        result["data"]["total"] == 1
        and result["data"]["items"][0]["uuid"] == reference["entity"]["uuid"]
    )


@pytest.mark.asyncio
async def test_anonymous_cannot_read_or_write(client):
    """真实路由矩阵保护读写接口。"""
    async with httpx.AsyncClient(
        base_url="http://127.0.0.1:8082", timeout=10, trust_env=False
    ) as anonymous:
        for response in [
            await anonymous.get("/api/v1/evidence/chains"),
            await anonymous.post("/api/v1/evidence/chains", json={"title": "不应创建"}),
        ]:
            assert response.json()["code"] != 0
