"""Provider 流式 reasoning_content 回调测试。"""

from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

from app.service.nanobot.providers.openai_compat_provider import OpenAICompatProvider


def _make_reasoning_chunk(reasoning: str | None, content: str | None, finish: str | None):
    delta = SimpleNamespace(content=content, reasoning_content=reasoning, tool_calls=None)
    choice = SimpleNamespace(finish_reason=finish, delta=delta)
    return SimpleNamespace(choices=[choice], usage=None)


@pytest.mark.asyncio
async def test_chat_stream_invokes_on_reasoning_delta() -> None:
    with patch("app.service.nanobot.providers.openai_compat_provider.AsyncOpenAI"):
        provider = OpenAICompatProvider()

    chunks = [
        _make_reasoning_chunk("Think ", None, None),
        _make_reasoning_chunk("more", None, None),
        _make_reasoning_chunk(None, "answer", "stop"),
    ]

    class _FakeStream:
        def __aiter__(self):
            return self

        async def __anext__(self):
            if not chunks:
                raise StopAsyncIteration
            return chunks.pop(0)

    provider._client = SimpleNamespace(
        chat=SimpleNamespace(
            completions=SimpleNamespace(
                create=AsyncMock(return_value=_FakeStream())
            )
        )
    )
    provider._should_use_responses_api = lambda *_a, **_k: False  # type: ignore[method-assign]

    reasoning_deltas: list[str] = []

    async def _on_reasoning(delta: str) -> None:
        reasoning_deltas.append(delta)

    result = await provider.chat_stream(
        messages=[{"role": "user", "content": "hi"}],
        on_reasoning_delta=_on_reasoning,
    )

    assert reasoning_deltas == ["Think ", "more"]
    assert result.reasoning_content == "Think more"
    assert result.content == "answer"


@pytest.mark.asyncio
async def test_chat_stream_no_attribute_error_without_reasoning_content_attr() -> None:
    """DeepSeek 等 API 的 ChoiceDelta 无 reasoning_content 字段时不应抛 AttributeError。"""
    with patch("app.service.nanobot.providers.openai_compat_provider.AsyncOpenAI"):
        provider = OpenAICompatProvider()

    delta = SimpleNamespace(content="hello", tool_calls=None)
    choice = SimpleNamespace(finish_reason="stop", delta=delta)
    chunks = [SimpleNamespace(choices=[choice], usage=None)]

    class _FakeStream:
        def __aiter__(self):
            return self

        async def __anext__(self):
            if not chunks:
                raise StopAsyncIteration
            return chunks.pop(0)

    provider._client = SimpleNamespace(
        chat=SimpleNamespace(
            completions=SimpleNamespace(create=AsyncMock(return_value=_FakeStream()))
        )
    )
    provider._should_use_responses_api = lambda *_a, **_k: False  # type: ignore[method-assign]

    reasoning_deltas: list[str] = []

    async def _on_reasoning(d: str) -> None:
        reasoning_deltas.append(d)

    result = await provider.chat_stream(
        messages=[{"role": "user", "content": "hi"}],
        on_reasoning_delta=_on_reasoning,
    )

    assert reasoning_deltas == []
    assert result.content == "hello"
    assert result.finish_reason == "stop"
