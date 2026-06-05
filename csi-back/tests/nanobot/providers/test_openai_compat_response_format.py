"""MIGRATION_PLAN §12.16：OpenAICompatProvider response_format 透传。"""

from __future__ import annotations

from typing import Any

from app.service.nanobot.providers.openai_compat_provider import OpenAICompatProvider


def test_provider_kwargs_includes_response_format() -> None:
    rf = {"type": "json_schema", "json_schema": {"name": "result", "schema": {}, "strict": False}}
    p = OpenAICompatProvider(api_key="k", api_base="http://x", default_model="gpt", response_format=rf)
    kwargs = p._build_kwargs(
        messages=[{"role": "user", "content": "hi"}],
        tools=None,
        model=None,
        max_tokens=10,
        temperature=0.1,
        reasoning_effort=None,
        tool_choice=None,
    )
    assert kwargs["response_format"] is rf


def test_provider_kwargs_without_response_format() -> None:
    p = OpenAICompatProvider(api_key="k", api_base="http://x", default_model="gpt", response_format=None)
    kwargs = p._build_kwargs(
        messages=[{"role": "user", "content": "hi"}],
        tools=None,
        model=None,
        max_tokens=10,
        temperature=0.1,
        reasoning_effort=None,
        tool_choice=None,
    )
    assert "response_format" not in kwargs


def test_provider_response_format_coexists_tools() -> None:
    rf: dict[str, Any] = {"type": "json_schema", "json_schema": {"name": "result", "schema": {}, "strict": False}}
    p = OpenAICompatProvider(api_key="k", api_base="http://x", default_model="gpt", response_format=rf)
    kwargs = p._build_kwargs(
        messages=[{"role": "user", "content": "hi"}],
        tools=[{"type": "function", "function": {"name": "t", "description": "", "parameters": {"type": "object"}}}],
        model=None,
        max_tokens=10,
        temperature=0.1,
        reasoning_effort=None,
        tool_choice=None,
    )
    assert "tools" in kwargs
    assert kwargs["response_format"] is rf

