"""build_assistant_message 单元测试。"""

from app.service.nanobot.utils.helpers import build_assistant_message

_TOOL_CALLS = [{
    "id": "call_1",
    "type": "function",
    "function": {"name": "get_weather", "arguments": "{}"},
}]


def test_tool_calls_without_reasoning_sets_empty_reasoning_content() -> None:
    msg = build_assistant_message("", tool_calls=_TOOL_CALLS, reasoning_content=None)

    assert msg["role"] == "assistant"
    assert msg["tool_calls"] == _TOOL_CALLS
    assert msg["reasoning_content"] == ""


def test_tool_calls_with_reasoning_preserves_text() -> None:
    msg = build_assistant_message(
        "",
        tool_calls=_TOOL_CALLS,
        reasoning_content="先查天气",
    )

    assert msg["reasoning_content"] == "先查天气"


def test_no_tool_calls_without_reasoning_omits_field() -> None:
    msg = build_assistant_message("hello")

    assert "reasoning_content" not in msg


def test_no_tool_calls_with_reasoning_includes_field() -> None:
    msg = build_assistant_message("hello", reasoning_content="思考过程")

    assert msg["reasoning_content"] == "思考过程"
