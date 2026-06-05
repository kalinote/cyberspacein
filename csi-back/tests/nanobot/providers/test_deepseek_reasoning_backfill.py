"""DeepSeek 思考模式：assistant+tool_calls 缺失 reasoning_content 时的 sanitize 兜底。"""

from unittest.mock import patch

from app.service.nanobot.providers.openai_compat_provider import OpenAICompatProvider


def test_sanitize_backfills_missing_reasoning_content_for_tool_calls() -> None:
    with patch("app.service.nanobot.providers.openai_compat_provider.AsyncOpenAI"):
        provider = OpenAICompatProvider()

    messages = [
        {"role": "user", "content": "查天气"},
        {
            "role": "assistant",
            "content": None,
            "tool_calls": [{
                "id": "call_abc123456",
                "type": "function",
                "function": {"name": "get_weather", "arguments": "{}"},
            }],
        },
        {"role": "tool", "content": "晴", "tool_call_id": "call_abc123456", "name": "get_weather"},
    ]

    sanitized = provider._sanitize_messages(messages)

    assistant = next(m for m in sanitized if m.get("role") == "assistant" and m.get("tool_calls"))
    assert assistant["reasoning_content"] == ""


def test_sanitize_preserves_existing_reasoning_content() -> None:
    with patch("app.service.nanobot.providers.openai_compat_provider.AsyncOpenAI"):
        provider = OpenAICompatProvider()

    messages = [
        {"role": "user", "content": "hi"},
        {
            "role": "assistant",
            "content": None,
            "reasoning_content": "需要先调用工具",
            "tool_calls": [{
                "id": "call_abc123456",
                "type": "function",
                "function": {"name": "fn", "arguments": "{}"},
            }],
        },
        {"role": "tool", "content": "ok", "tool_call_id": "call_abc123456", "name": "fn"},
    ]

    sanitized = provider._sanitize_messages(messages)

    assistant = next(m for m in sanitized if m.get("role") == "assistant" and m.get("tool_calls"))
    assert assistant["reasoning_content"] == "需要先调用工具"
