from __future__ import annotations

import asyncio
import os
import uuid
from typing import Any

import pytest
import pytest_asyncio
from beanie import init_beanie
from motor.motor_asyncio import AsyncIOMotorClient

from app.models.agent.nanobot import (
    NanobotAgentModel,
    NanobotSessionModel,
    NanobotWorkspaceModel,
)
from app.models.agent.sse_event import NanobotAgentSseEventModel, NanobotAgentSseEventStateModel
from app.service.analyst.service import AnalystService


@pytest_asyncio.fixture
async def sse_replay_db() -> Any:
    """初始化最小 Beanie 模型集，用于 SSE 回放集成测试。"""
    url = os.environ.get("MONGODB_URL", "mongodb://127.0.0.1:27017")
    username = os.environ.get("MONGODB_USERNAME") or None
    password = os.environ.get("MONGODB_PASSWORD") or None
    db_name = f"pytest_sse_replay_{uuid.uuid4().hex[:16]}"

    conn_kw: dict[str, Any] = {"serverSelectionTimeoutMS": 5000}
    if username and password:
        conn_kw["username"] = username
        conn_kw["password"] = password

    client = AsyncIOMotorClient(url, **conn_kw)
    try:
        await asyncio.wait_for(client.admin.command("ping"), timeout=5.0)
    except Exception as exc:
        client.close()
        pytest.skip(f"MongoDB 不可用，跳过 SSE 回放集成测试: {exc}")

    db = client[db_name]
    await init_beanie(
        database=db,
        document_models=[
            NanobotWorkspaceModel,
            NanobotAgentModel,
            NanobotSessionModel,
            NanobotAgentSseEventModel,
            NanobotAgentSseEventStateModel,
        ],
    )
    try:
        yield
    finally:
        await client.drop_database(db_name)
        client.close()


async def _seed_agent_with_session() -> tuple[str, str]:
    ws_id = f"ws_{uuid.uuid4().hex[:8]}"
    ag_id = f"ag_{uuid.uuid4().hex[:8]}"
    ss_id = f"ss_{uuid.uuid4().hex[:8]}"
    await NanobotWorkspaceModel(id=ws_id, name="测试工作区").insert()
    await NanobotAgentModel(
        id=ag_id,
        workspace_id=ws_id,
        name="测试Agent",
        prompt_template_id="pt1",
        model_config_id="mc1",
    ).insert()
    await NanobotSessionModel(id=ss_id, agent_id=ag_id, workspace_id=ws_id).insert()
    return ag_id, ss_id


@pytest.mark.asyncio
async def test_subscribe_replays_history_and_filters_debug(sse_replay_db: Any) -> None:
    _ = sse_replay_db
    agent_id, session_id = await _seed_agent_with_session()

    await AnalystService.broadcast_sse(
        agent_id,
        "status",
        {"agent_id": agent_id, "session_id": session_id, "status": "running"},
    )

    # stream：使用大块 delta 触发合并落库（避免逐字事件）
    await AnalystService.broadcast_sse(
        agent_id,
        "stream",
        {"agent_id": agent_id, "session_id": session_id, "delta": "a" * 3000},
    )

    await AnalystService.broadcast_debug_sse(
        agent_id,
        "debug_prompt",
        {"agent_id": agent_id, "session_id": session_id, "user_prompt": "hi"},
    )

    q_normal = await AnalystService.subscribe(agent_id, session_id, debug=False)
    q_debug = await AnalystService.subscribe(agent_id, session_id, debug=True)
    try:
        p1 = await q_normal.get()
        assert p1["event"] == "status"
        assert p1.get("id") is not None

        p2 = await q_normal.get()
        assert p2["event"] == "stream"
        assert isinstance((p2.get("data") or {}).get("delta"), str)

        # 普通订阅者不应回放 debug 事件
        assert q_normal.empty()

        d1 = await q_debug.get()
        assert d1["event"] == "status"
        d2 = await q_debug.get()
        assert d2["event"] == "stream"
        d3 = await q_debug.get()
        assert d3["event"] == "debug_prompt"
    finally:
        await AnalystService.unsubscribe(agent_id, session_id, q_normal)
        await AnalystService.unsubscribe(agent_id, session_id, q_debug)


@pytest.mark.asyncio
async def test_approval_required_patch_updates_single_persisted_row(sse_replay_db: Any) -> None:
    _ = sse_replay_db
    agent_id, session_id = await _seed_agent_with_session()
    req_id = "test-approval-req-1"

    await AnalystService.broadcast_sse(
        agent_id,
        "approval_required",
        {
            "agent_id": agent_id,
            "session_id": session_id,
            "approval_request_id": req_id,
            "resolution": None,
            "payload": {"approval_request_id": req_id, "reason": "x"},
        },
    )
    n1 = await NanobotAgentSseEventModel.find(
        {"agent_id": agent_id, "session_id": session_id, "event": "approval_required"}
    ).count()
    assert n1 == 1

    await AnalystService.patch_persisted_approval_required(
        agent_id,
        session_id,
        req_id,
        resolution="approved",
        reject_reasons=None,
    )
    n2 = await NanobotAgentSseEventModel.find(
        {"agent_id": agent_id, "session_id": session_id, "event": "approval_required"}
    ).count()
    assert n2 == 1

    row = await NanobotAgentSseEventModel.find_one(
        {"agent_id": agent_id, "session_id": session_id, "event": "approval_required"}
    )
    assert row is not None
    assert isinstance(row.data, dict)
    assert row.data.get("resolution") == "approved"

    q = await AnalystService.subscribe(agent_id, session_id, debug=False)
    try:
        msg = await q.get()
        assert msg["event"] == "approval_required"
        assert (msg.get("data") or {}).get("resolution") == "approved"
    finally:
        await AnalystService.unsubscribe(agent_id, session_id, q)

