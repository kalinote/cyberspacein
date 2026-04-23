"""MIGRATION_PLAN §12.1：nanobot Beanie 模型与枚举单测。"""

from __future__ import annotations

import asyncio
import os
import uuid
from typing import Any

import pytest
import pytest_asyncio
from beanie import init_beanie
from motor.motor_asyncio import AsyncIOMotorClient
from pymongo.errors import DuplicateKeyError

try:
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:
    pass

from app.models import get_all_models
from app.models.agent.nanobot import (
    NanobotAgentModel,
    NanobotHistoryModel,
    NanobotHistoryStateModel,
    NanobotMemoryDocsModel,
    NanobotSessionMessagesModel,
    NanobotSessionModel,
    NanobotWorkspaceModel,
)
from app.schemas.constants import (
    NanobotAgentStatusEnum,
    NanobotMemoryDocTypeEnum,
    NanobotMessageRoleEnum,
)

NANOBOT_DOCUMENTS: list[type] = [
    NanobotWorkspaceModel,
    NanobotAgentModel,
    NanobotSessionModel,
    NanobotSessionMessagesModel,
    NanobotMemoryDocsModel,
    NanobotHistoryModel,
    NanobotHistoryStateModel,
]


def test_nanobot_models_are_registered_in_get_all_models() -> None:
    models = get_all_models()
    for cls in NANOBOT_DOCUMENTS:
        assert cls in models, f"{cls.__name__} 未在 get_all_models() 中注册"


@pytest_asyncio.fixture
async def nanobot_db() -> Any:
    """每个用例独立库：避免 pytest-asyncio module scope 与默认 loop scope 冲突。"""
    url = os.environ.get("MONGODB_URL", "mongodb://127.0.0.1:27017")
    username = os.environ.get("MONGODB_USERNAME") or None
    password = os.environ.get("MONGODB_PASSWORD") or None
    db_name = f"pytest_nanobot_{uuid.uuid4().hex[:16]}"

    conn_kw: dict[str, Any] = {"serverSelectionTimeoutMS": 5000}
    if username and password:
        conn_kw["username"] = username
        conn_kw["password"] = password

    client = AsyncIOMotorClient(url, **conn_kw)
    try:
        await asyncio.wait_for(client.admin.command("ping"), timeout=5.0)
    except Exception as exc:
        client.close()
        pytest.skip(f"MongoDB 不可用，跳过 nanobot 模型集成测试: {exc}")

    db = client[db_name]
    await init_beanie(database=db, document_models=list(NANOBOT_DOCUMENTS))
    try:
        yield
    finally:
        await client.drop_database(db_name)
        client.close()


async def _seed_minimal_workspace_agent_session() -> tuple[str, str, str]:
    ws_id = f"ws_{uuid.uuid4().hex[:8]}"
    ag_id = f"ag_{uuid.uuid4().hex[:8]}"
    ss_id = f"ss_{uuid.uuid4().hex[:8]}"
    ws = NanobotWorkspaceModel(id=ws_id, name="测试工作区")
    await ws.insert()
    ag = NanobotAgentModel(
        id=ag_id,
        workspace_id=ws_id,
        name="测试Agent",
        prompt_template_id="pt1",
        model_config_id="mc1",
    )
    await ag.insert()
    sess = NanobotSessionModel(id=ss_id, agent_id=ag_id, workspace_id=ws_id)
    await sess.insert()
    return ws_id, ag_id, ss_id


@pytest.mark.asyncio
async def test_models_registered_collections_exist_after_insert(nanobot_db: Any) -> None:
    _ = nanobot_db
    ws_id, ag_id, ss_id = await _seed_minimal_workspace_agent_session()

    msg = NanobotSessionMessagesModel(
        session_id=ss_id,
        seq=1,
        role=NanobotMessageRoleEnum.USER,
        content="你好",
    )
    await msg.insert()

    mem = NanobotMemoryDocsModel(
        workspace_id=ws_id,
        type=NanobotMemoryDocTypeEnum.MEMORY,
        content="记忆",
    )
    await mem.insert()

    hist = NanobotHistoryModel(workspace_id=ws_id, cursor=1, content="历史")
    await hist.insert()

    st = NanobotHistoryStateModel(id=ws_id, last_cursor=1, last_dream_cursor=0)
    await st.insert()

    db = NanobotWorkspaceModel.get_pymongo_collection().database
    names = set(await db.list_collection_names())
    expected = {cls.Settings.name for cls in NANOBOT_DOCUMENTS}
    assert expected <= names, f"缺少集合: {expected - names}"

    for cls in NANOBOT_DOCUMENTS:
        assert await cls.get_pymongo_collection().count_documents({}) >= 1


@pytest.mark.asyncio
async def test_indexes_created(nanobot_db: Any) -> None:
    _ = nanobot_db
    await _seed_minimal_workspace_agent_session()

    async def keys_and_uniques(model: type) -> list[tuple[dict[str, int], bool]]:
        coll = model.get_pymongo_collection()
        specs = await coll.list_indexes().to_list(length=None)
        out: list[tuple[dict[str, int], bool]] = []
        for spec in specs:
            if spec["name"] == "_id_":
                continue
            out.append((dict(spec["key"]), bool(spec.get("unique"))))
        return out

    def _match(keys: dict[str, int], want: dict[str, int]) -> bool:
        return frozenset(keys.items()) == frozenset(want.items())

    agent_specs = await keys_and_uniques(NanobotAgentModel)
    assert any(
        _match(k, {"workspace_id": 1, "name": 1}) and u for k, u in agent_specs
    ), "缺少 (workspace_id, name) 唯一复合索引"

    msg_specs = await keys_and_uniques(NanobotSessionMessagesModel)
    assert any(
        _match(k, {"session_id": 1, "seq": 1}) and u for k, u in msg_specs
    ), "缺少 (session_id, seq) 唯一复合索引"

    mem_specs = await keys_and_uniques(NanobotMemoryDocsModel)
    assert any(
        _match(k, {"workspace_id": 1, "type": 1}) and u for k, u in mem_specs
    ), "缺少 (workspace_id, type) 唯一复合索引"

    hist_specs = await keys_and_uniques(NanobotHistoryModel)
    assert any(
        _match(k, {"workspace_id": 1, "cursor": 1}) and u for k, u in hist_specs
    ), "缺少 (workspace_id, cursor) 唯一复合索引"


@pytest.mark.asyncio
async def test_id_alias_roundtrip(nanobot_db: Any) -> None:
    _ = nanobot_db
    ws_id = f"ws_alias_{uuid.uuid4().hex[:8]}"
    ws = NanobotWorkspaceModel(id=ws_id, name="别名测试")
    await ws.insert()

    raw = await NanobotWorkspaceModel.get_pymongo_collection().find_one({"_id": ws_id})
    assert raw is not None
    assert raw["_id"] == ws_id

    loaded = await NanobotWorkspaceModel.get(ws_id)
    assert loaded is not None
    assert loaded.id == ws_id

    ag_id = f"ag_alias_{uuid.uuid4().hex[:8]}"
    ag = NanobotAgentModel(
        id=ag_id,
        workspace_id=ws_id,
        name="A",
        prompt_template_id="p",
        model_config_id="m",
    )
    await ag.insert()
    ag2 = await NanobotAgentModel.get(ag_id)
    assert ag2 is not None and ag2.id == ag_id

    ss_id = f"ss_alias_{uuid.uuid4().hex[:8]}"
    sess = NanobotSessionModel(id=ss_id, agent_id=ag_id, workspace_id=ws_id)
    await sess.insert()
    sess2 = await NanobotSessionModel.get(ss_id)
    assert sess2 is not None and sess2.id == ss_id

    st = NanobotHistoryStateModel(id=ws_id, last_cursor=0, last_dream_cursor=0)
    await st.insert()
    st2 = await NanobotHistoryStateModel.get(ws_id)
    assert st2 is not None and st2.id == ws_id


@pytest.mark.asyncio
async def test_enum_roundtrip_stored_as_string(nanobot_db: Any) -> None:
    _ = nanobot_db
    ws_id, _, ss_id = await _seed_minimal_workspace_agent_session()

    msg = NanobotSessionMessagesModel(
        session_id=ss_id,
        seq=1,
        role=NanobotMessageRoleEnum.ASSISTANT,
        content="回复",
    )
    await msg.insert()

    raw_msg = await NanobotSessionMessagesModel.get_pymongo_collection().find_one(
        {"session_id": ss_id, "seq": 1}
    )
    assert raw_msg is not None
    assert raw_msg["role"] == NanobotMessageRoleEnum.ASSISTANT.value
    assert isinstance(raw_msg["role"], str)

    reloaded = await NanobotSessionMessagesModel.find_one(
        {"session_id": ss_id, "seq": 1}
    )
    assert reloaded is not None
    assert reloaded.role is NanobotMessageRoleEnum.ASSISTANT

    ag = await NanobotAgentModel.find_one()
    assert ag is not None
    ag.status = NanobotAgentStatusEnum.RUNNING
    await ag.save()

    raw_ag = await NanobotAgentModel.get_pymongo_collection().find_one({"_id": ag.id})
    assert raw_ag is not None
    assert raw_ag["status"] == NanobotAgentStatusEnum.RUNNING.value

    ag2 = await NanobotAgentModel.get(ag.id)
    assert ag2 is not None and ag2.status is NanobotAgentStatusEnum.RUNNING

    mem = NanobotMemoryDocsModel(
        workspace_id=ws_id,
        type=NanobotMemoryDocTypeEnum.SOUL,
        content="soul",
    )
    await mem.insert()
    raw_mem = await NanobotMemoryDocsModel.get_pymongo_collection().find_one(
        {"workspace_id": ws_id}
    )
    assert raw_mem is not None
    assert raw_mem["type"] == NanobotMemoryDocTypeEnum.SOUL.value
    mem2 = await NanobotMemoryDocsModel.find_one()
    assert mem2 is not None and mem2.type is NanobotMemoryDocTypeEnum.SOUL


@pytest.mark.asyncio
async def test_defaults_not_shared_mutable_lists(nanobot_db: Any) -> None:
    _ = nanobot_db
    ws_id = f"ws_def_{uuid.uuid4().hex[:8]}"
    ws = NanobotWorkspaceModel(id=ws_id, name="默认隔离")
    await ws.insert()

    a1 = NanobotAgentModel(
        id=f"a1_{uuid.uuid4().hex[:6]}",
        workspace_id=ws_id,
        name="Agent1",
        prompt_template_id="p",
        model_config_id="m",
    )
    a2 = NanobotAgentModel(
        id=f"a2_{uuid.uuid4().hex[:6]}",
        workspace_id=ws_id,
        name="Agent2",
        prompt_template_id="p",
        model_config_id="m",
    )
    await a1.insert()
    await a2.insert()

    a1_loaded = await NanobotAgentModel.get(a1.id)
    a2_loaded = await NanobotAgentModel.get(a2.id)
    assert a1_loaded is not None and a2_loaded is not None

    a1_loaded.tools.append("notify_user")
    await a1_loaded.save()

    a2_refreshed = await NanobotAgentModel.get(a2.id)
    assert a2_refreshed is not None
    assert "notify_user" not in a2_refreshed.tools

    a1_loaded.steps.append({"n": 1})
    await a1_loaded.save()
    a2_refreshed2 = await NanobotAgentModel.get(a2.id)
    assert a2_refreshed2 is not None
    assert a2_refreshed2.steps == []


@pytest.mark.asyncio
async def test_unique_conflict_agent_workspace_name(nanobot_db: Any) -> None:
    _ = nanobot_db
    ws_id = f"ws_uq_{uuid.uuid4().hex[:8]}"
    await NanobotWorkspaceModel(id=ws_id, name="UQ").insert()

    await NanobotAgentModel(
        id=f"x1_{uuid.uuid4().hex[:6]}",
        workspace_id=ws_id,
        name="同名",
        prompt_template_id="p",
        model_config_id="m",
    ).insert()

    with pytest.raises(DuplicateKeyError):
        await NanobotAgentModel(
            id=f"x2_{uuid.uuid4().hex[:6]}",
            workspace_id=ws_id,
            name="同名",
            prompt_template_id="p",
            model_config_id="m",
        ).insert()


@pytest.mark.asyncio
async def test_unique_conflict_session_message_seq(nanobot_db: Any) -> None:
    _ = nanobot_db
    _, _, ss_id = await _seed_minimal_workspace_agent_session()
    await NanobotSessionMessagesModel(
        session_id=ss_id,
        seq=1,
        role=NanobotMessageRoleEnum.USER,
        content="a",
    ).insert()
    with pytest.raises(DuplicateKeyError):
        await NanobotSessionMessagesModel(
            session_id=ss_id,
            seq=1,
            role=NanobotMessageRoleEnum.USER,
            content="b",
        ).insert()


@pytest.mark.asyncio
async def test_unique_conflict_history_workspace_cursor(nanobot_db: Any) -> None:
    _ = nanobot_db
    ws_id, _, _ = await _seed_minimal_workspace_agent_session()
    await NanobotHistoryModel(workspace_id=ws_id, cursor=7, content="c1").insert()
    with pytest.raises(DuplicateKeyError):
        await NanobotHistoryModel(workspace_id=ws_id, cursor=7, content="c2").insert()


@pytest.mark.asyncio
async def test_unique_conflict_memory_workspace_type(nanobot_db: Any) -> None:
    _ = nanobot_db
    ws_id, _, _ = await _seed_minimal_workspace_agent_session()
    await NanobotMemoryDocsModel(
        workspace_id=ws_id,
        type=NanobotMemoryDocTypeEnum.MEMORY,
        content="m1",
    ).insert()
    with pytest.raises(DuplicateKeyError):
        await NanobotMemoryDocsModel(
            workspace_id=ws_id,
            type=NanobotMemoryDocTypeEnum.MEMORY,
            content="m2",
        ).insert()


@pytest.mark.asyncio
async def test_agent_status_default(nanobot_db: Any) -> None:
    _ = nanobot_db
    ws_id = f"ws_idle_{uuid.uuid4().hex[:8]}"
    await NanobotWorkspaceModel(id=ws_id, name="默认状态").insert()

    ag_id = f"ag_idle_{uuid.uuid4().hex[:8]}"
    ag = NanobotAgentModel(
        id=ag_id,
        workspace_id=ws_id,
        name="IdleAgent",
        prompt_template_id="p",
        model_config_id="m",
    )
    await ag.insert()

    loaded = await NanobotAgentModel.get(ag_id)
    assert loaded is not None
    assert loaded.status is NanobotAgentStatusEnum.IDLE
    assert loaded.current_session_id is None
    assert loaded.steps == []
    assert loaded.todos == []
    assert loaded.pending_approval is None
    assert loaded.result is None
