"""MIGRATION_PLAN §12.5：Session 领域对象单测（纯内存）。"""

from __future__ import annotations

import pytest

from app.service.nanobot.session.manager import Session


def _msg(role: str, content: str, **kwargs):
    return {"role": role, "content": content, **kwargs}


def test_session_init_required_fields() -> None:
    # 必须提供 id / agent_id / workspace_id
    with pytest.raises(TypeError):
        Session()  # type: ignore
    with pytest.raises(TypeError):
        Session(id="s", agent_id="a")  # type: ignore
    with pytest.raises(TypeError):
        Session(id="s", workspace_id="w")  # type: ignore

    s = Session(id="s1", agent_id="a1", workspace_id="w1")
    assert s.id == "s1"
    assert s.agent_id == "a1"
    assert s.workspace_id == "w1"


def test_session_add_message_fields() -> None:
    s = Session(id="s1", agent_id="a1", workspace_id="w1")
    s.add_message("user", "hi", tool_call_id="x")
    last = s.messages[-1]
    assert last["role"] == "user"
    assert last["content"] == "hi"
    assert "timestamp" in last
    assert last["tool_call_id"] == "x"
    assert "seq" not in last  # seq 由 SessionStore 分配


def test_session_clear() -> None:
    s = Session(id="s1", agent_id="a1", workspace_id="w1")
    s.add_message("user", "hi")
    s.last_consolidated = 3
    s.clear()
    assert s.messages == []
    assert s.last_consolidated == 0


def test_retain_recent_zero_clears() -> None:
    s = Session(id="s1", agent_id="a1", workspace_id="w1")
    s.add_message("user", "hi")
    s.retain_recent_legal_suffix(0)
    assert s.messages == []
    assert s.last_consolidated == 0


def test_get_history_skip_consolidated() -> None:
    s = Session(id="s1", agent_id="a1", workspace_id="w1")
    s.messages = [
        _msg("user", "u1"),
        _msg("assistant", "a1"),
        _msg("user", "u2"),
        _msg("assistant", "a2"),
    ]
    s.last_consolidated = 2
    history = s.get_history()
    assert [m["content"] for m in history] == ["u2", "a2"]


def test_retain_recent_legal_suffix_boundary() -> None:
    s = Session(id="s1", agent_id="a1", workspace_id="w1")
    # 构造一段非法前缀：tool 结果没有对应 assistant tool_calls 声明（orphan）
    s.messages = [
        _msg("tool", "orphan", tool_call_id="t_orphan"),
        _msg("user", "u1"),
        _msg(
            "assistant",
            "a1",
            tool_calls=[{"id": "t1", "name": "x", "arguments": {}}],
        ),
        _msg("tool", "ok", tool_call_id="t1"),
        _msg("assistant", "a2"),
        _msg("user", "u2"),
        _msg("assistant", "a3"),
    ]
    # 设置 last_consolidated 以便观察裁剪后的调整
    s.last_consolidated = 2

    # max_messages=4：从尾部裁剪，再回退到 user 边界，并剥离 orphan tool
    s.retain_recent_legal_suffix(4)

    assert s.messages[0]["role"] == "user"  # 首条必须是 user
    assert all(m.get("tool_call_id") != "t_orphan" for m in s.messages)
    # last_consolidated 应随 dropped 调整，不应为负
    assert s.last_consolidated >= 0


def test_get_history_aligns_legal_tool_boundary() -> None:
    s = Session(id="s1", agent_id="a1", workspace_id="w1")
    # sliced 中包含一个 orphan tool（无声明），get_history 应从其后开始
    s.messages = [
        _msg("user", "u0"),
        _msg("assistant", "a0"),
        _msg("tool", "orphan", tool_call_id="x"),
        _msg("user", "u1"),
        _msg("assistant", "a1"),
    ]
    hist = s.get_history(max_messages=5)
    assert [m["content"] for m in hist] == ["u1", "a1"]

