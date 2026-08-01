from __future__ import annotations

import json
from copy import deepcopy
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock

import pytest

import app.service.entity_content_analysis as service_module
from app.schemas.constants import NanobotLLMProviderEnum
from app.service.entity_content_analysis import (
    EntityContentAnalysisError,
    EntityContentAnalysisService,
)
from app.service.nanobot.providers.base import LLMResponse, ToolCallRequest


def _valid_arguments(**overrides: Any) -> dict[str, Any]:
    """构造合法的模型结构化返回参数。"""
    result = {
        "translation_applied": True,
        "translate_content": "这是一段译文。",
        "keywords": ["OpenAI", "人工智能"],
        "entities": {
            "person": [],
            "location": [],
            "organization": [],
            "company": ["OpenAI"],
            "region": [],
            "network_user": [],
        },
        "nsfw": False,
    }
    result.update(overrides)
    return result


def _tool_response(
    arguments: dict[str, Any],
    *,
    name: str = "submit_entity_content_analysis",
    call_id: str = "call-1",
) -> LLMResponse:
    """构造包含一个函数调用的模型响应。"""
    return LLMResponse(
        content=None,
        tool_calls=[
            ToolCallRequest(
                id=call_id,
                name=name,
                arguments=arguments,
            )
        ],
        finish_reason="tool_calls",
    )


class _StubProvider:
    """记录请求并按顺序返回预设响应。"""

    def __init__(self, *responses: LLMResponse | Exception) -> None:
        self.responses = list(responses)
        self.calls: list[dict[str, Any]] = []

    async def chat_with_retry(self, **kwargs: Any) -> LLMResponse:
        """返回下一条预设响应。"""
        self.calls.append(kwargs)
        response = self.responses.pop(0)
        if isinstance(response, Exception):
            raise response
        return response


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("provider_type", "expected_constructor"),
    [
        (NanobotLLMProviderEnum.OPENAI_COMPAT, "openai"),
        ("anthropic", "anthropic"),
    ],
)
async def test_from_model_config_builds_selected_provider(
    monkeypatch: pytest.MonkeyPatch,
    provider_type: NanobotLLMProviderEnum | str,
    expected_constructor: str,
) -> None:
    model_config = SimpleNamespace(
        api_key="api-key",
        base_url="https://llm.example/v1",
        model="model-1",
    )
    find_one = AsyncMock(return_value=model_config)
    monkeypatch.setattr(service_module.AgentModelConfigModel, "find_one", find_one)

    providers = {"openai": object(), "anthropic": object()}
    constructor_calls: dict[str, dict[str, Any]] = {}

    def build_openai(**kwargs: Any) -> object:
        constructor_calls["openai"] = kwargs
        return providers["openai"]

    def build_anthropic(**kwargs: Any) -> object:
        constructor_calls["anthropic"] = kwargs
        return providers["anthropic"]

    monkeypatch.setattr(service_module, "OpenAICompatProvider", build_openai)
    monkeypatch.setattr(service_module, "AnthropicProvider", build_anthropic)

    service = await EntityContentAnalysisService.from_model_config(
        " model-config-1 ",
        provider_type,
    )

    find_one.assert_awaited_once_with({"_id": "model-config-1"})
    assert service._provider is providers[expected_constructor]
    assert constructor_calls == {
        expected_constructor: {
            "api_key": "api-key",
            "api_base": "https://llm.example/v1",
            "default_model": "model-1",
        }
    }


@pytest.mark.asyncio
async def test_from_model_config_reports_invalid_configuration(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    find_one = AsyncMock(return_value=None)
    monkeypatch.setattr(service_module.AgentModelConfigModel, "find_one", find_one)

    with pytest.raises(EntityContentAnalysisError, match="不支持的 LLM 提供商"):
        await EntityContentAnalysisService.from_model_config("model-1", "unknown")
    find_one.assert_not_awaited()

    with pytest.raises(EntityContentAnalysisError, match="模型配置不存在"):
        await EntityContentAnalysisService.from_model_config("model-1")


@pytest.mark.asyncio
async def test_analyze_sends_required_context_and_returns_full_copy() -> None:
    provider = _StubProvider(_tool_response(_valid_arguments()))
    service = EntityContentAnalysisService(provider)  # type: ignore[arg-type]
    source = {
        "uuid": "entity-1",
        "title": "模型发布",
        "entity_type": "article",
        "clean_content": "OpenAI released a new model.",
        "translate_content": "旧译文",
        "keywords": ["旧关键词"],
        "entities": {"old": ["旧实体"]},
        "nsfw": True,
        "private_field": "不得默认发送给模型",
        "metadata": {"source": "feed"},
    }
    original = deepcopy(source)

    result = await service.analyze(source, min_analysis_length=0)

    assert source == original
    assert result is not source
    assert result["metadata"] == source["metadata"]
    assert result["metadata"] is not source["metadata"]
    assert result == {
        **original,
        "translate_content": "这是一段译文。",
        "keywords": ["OpenAI", "人工智能"],
        "entities": {
            "person": [],
            "location": [],
            "organization": [],
            "company": ["OpenAI"],
            "region": [],
            "network_user": [],
        },
        "nsfw": False,
    }

    assert len(provider.calls) == 1
    request = provider.calls[0]
    assert request["temperature"] == 0.1
    assert request["max_tokens"] == 4096
    assert request["retry_mode"] == "standard"
    assert request["tool_choice"] == "required"
    assert {
        tool["function"]["name"]
        for tool in request["tools"]
    } == {
        "read_current_record_fields",
        "submit_entity_content_analysis",
    }

    user_message = request["messages"][1]["content"]
    assert "OpenAI released a new model." in user_message
    assert "模型发布" in user_message
    assert "entity-1" in user_message
    assert '"private_field"' in user_message
    assert "不得默认发送给模型" not in user_message
    assert "旧译文" not in user_message


@pytest.mark.asyncio
async def test_analyze_with_outcome_exposes_short_content_skip() -> None:
    provider = _StubProvider()
    service = EntityContentAnalysisService(provider)  # type: ignore[arg-type]
    source = {
        "uuid": "entity-1",
        "clean_content": "短内容",
        "metadata": {"nested": True},
    }

    outcome = await service.analyze_with_outcome(
        source,
        min_analysis_length=3,
    )

    assert outcome.skipped is True
    assert outcome.skip_reason == "分析字段长度未超过最小限制: 3 <= 3"
    assert outcome.chunk_count == 0
    assert outcome.analysis_length == 3
    assert outcome.data == source
    assert outcome.data is not source
    assert outcome.data["metadata"] is not source["metadata"]
    assert provider.calls == []


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("source", "analysis_field", "message"),
    [
        ({"clean_content": "文本"}, "nested.content", "安全的顶层字段名"),
        ({"clean_content": "文本"}, "body", "分析字段不存在: body"),
        ({"body": ["不是字符串"]}, "body", "分析字段必须是字符串: body"),
    ],
)
async def test_analyze_rejects_invalid_analysis_field(
    source: dict[str, Any],
    analysis_field: str,
    message: str,
) -> None:
    provider = _StubProvider()
    service = EntityContentAnalysisService(provider)  # type: ignore[arg-type]

    with pytest.raises(EntityContentAnalysisError, match=message):
        await service.analyze(source, analysis_field=analysis_field)

    assert provider.calls == []


@pytest.mark.asyncio
async def test_custom_analysis_field_and_user_prompt_are_scoped() -> None:
    provider = _StubProvider(_tool_response(_valid_arguments()))
    service = EntityContentAnalysisService(provider)  # type: ignore[arg-type]

    await service.analyze(
        {
            "uuid": "entity-2",
            "title": "自定义正文",
            "body": "Body text to analyze.",
            "clean_content": "不得作为分析正文发送",
        },
        analysis_field="body",
        min_analysis_length=0,
        user_prompt_override="重点关注产品名称。",
    )

    request = provider.calls[0]
    system_message = request["messages"][0]["content"]
    user_message = request["messages"][1]["content"]
    assert "重点关注产品名称。" not in system_message
    assert "重点关注产品名称。" in user_message
    assert "请分析当前记录上下文" not in user_message
    assert "Body text to analyze." in user_message
    assert "不得作为分析正文发送" not in user_message
    assert '"clean_content"' in user_message


@pytest.mark.asyncio
async def test_model_can_read_only_current_record_top_level_fields() -> None:
    provider = _StubProvider(
        _tool_response(
            {
                "names": [
                    "author",
                    "metadata",
                    "clean_content",
                    "missing",
                    "metadata.name",
                ]
            },
            name="read_current_record_fields",
            call_id="read-1",
        ),
        _tool_response(_valid_arguments()),
    )
    service = EntityContentAnalysisService(provider)  # type: ignore[arg-type]

    await service.analyze(
        {
            "uuid": "entity-1",
            "clean_content": "Source text",
            "author": "Alice",
            "metadata": {"name": "Feed"},
        },
        min_analysis_length=0,
    )

    assert len(provider.calls) == 2
    second_messages = provider.calls[1]["messages"]
    assert second_messages[-2]["role"] == "assistant"
    assert second_messages[-1]["role"] == "tool"
    tool_result = json.loads(second_messages[-1]["content"])
    assert tool_result == {
        "ok": False,
        "values": {
            "author": "Alice",
            "metadata": {"name": "Feed"},
        },
        "errors": {
            "clean_content": "分析字段已按当前分块提供，禁止读取完整原文",
            "missing": "当前记录不存在该字段",
            "metadata.name": "不支持点路径或嵌套路径",
        },
    }


@pytest.mark.asyncio
async def test_analyze_rejects_unauthorized_tool_call() -> None:
    provider = _StubProvider(
        _tool_response({}, name="database_query"),
    )
    service = EntityContentAnalysisService(provider)  # type: ignore[arg-type]

    with pytest.raises(EntityContentAnalysisError, match="未授权工具"):
        await service.analyze(
            {"clean_content": "Source text"},
            min_analysis_length=0,
        )


@pytest.mark.asyncio
async def test_analyze_preserves_translation_and_normalizes_lists() -> None:
    provider = _StubProvider(
        _tool_response(
            _valid_arguments(
                translation_applied=False,
                translate_content=None,
                keywords=[" Alpha ", "Alpha", "NSFW", "NSFW", ""],
                entities={
                    "person": [" Alice ", "Alice", ""],
                    "location": [],
                    "organization": [],
                    "company": ["OpenAI", "OpenAI"],
                    "region": [],
                    "network_user": [],
                },
                nsfw=True,
            )
        )
    )
    service = EntityContentAnalysisService(provider)  # type: ignore[arg-type]

    result = await service.analyze(
        {
            "uuid": "entity-1",
            "clean_content": "这是一段中文内容。",
            "translate_content": "保留的旧译文",
        },
        min_analysis_length=0,
    )

    assert result["translate_content"] == "保留的旧译文"
    assert result["keywords"] == ["NSFW", "Alpha"]
    assert result["entities"]["person"] == ["Alice"]
    assert result["entities"]["company"] == ["OpenAI"]
    assert result["nsfw"] is True


@pytest.mark.asyncio
async def test_analyze_reports_model_error_and_missing_function_call() -> None:
    error_provider = _StubProvider(
        LLMResponse(content="配额不足", finish_reason="error")
    )
    error_service = EntityContentAnalysisService(  # type: ignore[arg-type]
        error_provider
    )
    with pytest.raises(EntityContentAnalysisError, match="模型请求失败: 配额不足"):
        await error_service.analyze(
            {"clean_content": "待分析文本"},
            min_analysis_length=0,
        )

    missing_provider = _StubProvider(
        LLMResponse(content='{"keywords":[]}', finish_reason="stop")
    )
    missing_service = EntityContentAnalysisService(  # type: ignore[arg-type]
        missing_provider
    )
    with pytest.raises(EntityContentAnalysisError, match="模型未返回要求的函数调用"):
        await missing_service.analyze(
            {"clean_content": "待分析文本"},
            min_analysis_length=0,
        )
    assert len(missing_provider.calls) == 1


@pytest.mark.asyncio
async def test_analyze_retries_validation_failure_once() -> None:
    invalid = _valid_arguments()
    invalid["entities"] = {
        **invalid["entities"],
        "unexpected": ["不允许的分类"],
    }
    provider = _StubProvider(
        _tool_response(invalid),
        _tool_response(_valid_arguments()),
    )
    service = EntityContentAnalysisService(provider)  # type: ignore[arg-type]

    result = await service.analyze(
        {"clean_content": "Source text"},
        min_analysis_length=0,
    )

    assert result["translate_content"] == "这是一段译文。"
    assert len(provider.calls) == 2
    assert provider.calls[1]["tool_choice"]["function"]["name"] == (
        "submit_entity_content_analysis"
    )
    assert "函数参数未通过严格格式校验" in (
        provider.calls[1]["messages"][-1]["content"]
    )


@pytest.mark.asyncio
async def test_analyze_fails_after_second_validation_failure() -> None:
    invalid = _valid_arguments(translation_applied="yes")
    provider = _StubProvider(
        _tool_response(invalid),
        _tool_response(invalid),
    )
    service = EntityContentAnalysisService(provider)  # type: ignore[arg-type]

    with pytest.raises(
        EntityContentAnalysisError,
        match="模型结构化分析结果格式校验失败",
    ):
        await service.analyze(
            {"clean_content": "Source text"},
            min_analysis_length=0,
        )

    assert len(provider.calls) == 2


@pytest.mark.asyncio
async def test_analyze_chunks_and_aggregates_results() -> None:
    provider = _StubProvider(
        _tool_response(
            _valid_arguments(
                translate_content="译文一",
                keywords=["Alpha", "Beta"],
                entities={
                    "person": ["Alice"],
                    "location": [],
                    "organization": [],
                    "company": ["OpenAI"],
                    "region": [],
                    "network_user": [],
                },
            )
        ),
        _tool_response(
            _valid_arguments(
                translation_applied=False,
                translate_content=None,
                keywords=["Beta", "Gamma", "NSFW"],
                entities={
                    "person": ["Alice", "Bob"],
                    "location": [],
                    "organization": [],
                    "company": [],
                    "region": ["US"],
                    "network_user": [],
                },
                nsfw=True,
            )
        ),
    )
    service = EntityContentAnalysisService(provider)  # type: ignore[arg-type]

    outcome = await service.analyze_with_outcome(
        {
            "uuid": "entity-1",
            "clean_content": "abcdefgh",
            "translate_content": "旧译文",
        },
        min_analysis_length=0,
        chunk_size=4,
    )

    assert outcome.skipped is False
    assert outcome.chunk_count == 2
    assert outcome.analysis_length == 8
    assert outcome.data["translate_content"] == "译文一\n\nefgh"
    assert outcome.data["keywords"] == ["NSFW", "Beta", "Alpha", "Gamma"]
    assert outcome.data["entities"]["person"] == ["Alice", "Bob"]
    assert outcome.data["entities"]["company"] == ["OpenAI"]
    assert outcome.data["entities"]["region"] == ["US"]
    assert outcome.data["nsfw"] is True
    assert len(provider.calls) == 2
    assert '"index":1' in provider.calls[0]["messages"][1]["content"]
    assert '"index":2' in provider.calls[1]["messages"][1]["content"]
