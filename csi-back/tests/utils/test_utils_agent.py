"""app.utils.agent 纯函数与模板注入测试（不访问数据库）。"""

import pytest

from app.utils.agent import (
    get_step_detail,
    inject_template_fields,
    modify_entity_approval_description,
    normalize_todo,
    parse_approval_decision,
)


def test_modify_entity_approval_description_dict():
    # tool_call 为 dict 时读取 args.field
    s = modify_entity_approval_description({"args": {"field": "title"}}, None, None)
    assert "title" in s


def test_modify_entity_approval_description_object():
    # tool_call 为对象属性时兼容
    class TC:
        args = {"field": "body"}

    s = modify_entity_approval_description(TC(), None, None)
    assert "body" in s


def test_normalize_todo_dict_and_object():
    assert normalize_todo({"content": "a", "status": "done"})["status"] == "done"
    class T:
        content = "c"
        status = "pending"
    assert normalize_todo(T())["content"] == "c"


@pytest.mark.parametrize(
    "decisions,expected",
    [
        ([], "unknown"),
        ([{"type": "approve"}], "approve"),
        ([{"type": "reject"}], "reject"),
        ([{"type": "edit"}], "edit"),
        ([{"type": "other"}], "unknown"),
    ],
)
def test_parse_approval_decision(decisions, expected):
    assert parse_approval_decision(decisions) == expected


def test_get_step_detail_empty_state():
    assert get_step_detail({}) == {}
    assert get_step_detail({"messages": []}) == {}


def test_get_step_detail_tool_calls():
    su = {"messages": [{"tool_calls": [{"name": "t1", "args": {"x": 1}}]}]}
    d = get_step_detail(su)
    assert d["tool_calls"][0]["name"] == "t1"


def test_get_step_detail_content_preview():
    su = {"messages": [{"content": "hello world"}]}
    d = get_step_detail(su)
    assert d["result_summary"]["content_length"] == 11


def test_inject_template_fields():
    # Jinja2 模板注入字段
    out = inject_template_fields("Hello {{ name }}", {"name": "CSI"})
    assert out == "Hello CSI"


def test_inject_template_fields_missing_uses_placeholder():
    # 未定义变量使用自定义 Undefined 渲染占位
    out = inject_template_fields("{{ missing }}", {})
    assert "缺失" in out or "!" in out
