"""覆盖完成任务后续聊时，重复调用 ID 与缺失工具返回的历史修复。"""

from copy import deepcopy
from unittest.mock import AsyncMock, Mock, patch

import pytest

from app.service.nanobot.agent.hook import AgentHook
from app.service.nanobot.agent.runner import AgentRunner, AgentRunSpec
from app.service.nanobot.agent.tools.registry import ToolRegistry
from app.service.nanobot.providers.base import LLMResponse
from app.service.nanobot.providers.openai_compat_provider import OpenAICompatProvider


_COMPLETION_CALL = {
    "role": "assistant",
    "content": "验收完成",
    "tool_calls": [{
        "id": "call_completed_result",
        "type": "function",
        "function": {"name": "submit_task_result", "arguments": "{}"},
    }],
}
_COMPLETION_RESULT = {
    "role": "tool",
    "tool_call_id": "call_completed_result",
    "name": "submit_task_result",
    "content": "任务机读结果已记录",
}


def _assert_tool_pairs(messages: list[dict]) -> None:
    """验证每批工具调用均在下一条非工具消息前得到唯一返回。"""
    pending = set()
    for message in messages:
        if message["role"] == "tool":
            assert message.get("tool_call_id") in pending
            pending.remove(message["tool_call_id"])
        else:
            assert not pending
            if message["role"] == "assistant":
                pending = {call["id"] for call in message.get("tool_calls", [])}
    assert not pending


@pytest.mark.parametrize("earlier_result,later_result", [
    (True, False), (False, True), (False, False), (True, True),
])
def test_repeated_call_id_is_matched_with_its_own_result(
    earlier_result: bool, later_result: bool,
) -> None:
    """前后批次复用同一 ID 时，不能用另一批次的返回掩盖缺失。"""
    messages = [{"role": "user", "content": "开始验收"}, deepcopy(_COMPLETION_CALL)]
    if earlier_result:
        messages.append(deepcopy(_COMPLETION_RESULT))
    messages.extend([
        {"role": "assistant", "content": "本轮结束"},
        deepcopy(_COMPLETION_CALL),
    ])
    if later_result:
        messages.append(deepcopy(_COMPLETION_RESULT))
    messages.append({"role": "user", "content": "继续核对"})
    original = deepcopy(messages)

    repaired = AgentRunner._backfill_missing_tool_results(
        AgentRunner._drop_orphan_tool_results(messages)
    )

    _assert_tool_pairs(repaired)
    assert len(repaired) == len(messages) + 2 - earlier_result - later_result
    assert messages == original
    assert AgentRunner._backfill_missing_tool_results(repaired) == repaired


def test_late_or_duplicate_results_are_not_attached_to_a_previous_batch() -> None:
    """丢弃已结束批次的迟到或重复返回，保留原本有效的结果。"""
    messages = [
        {"role": "user", "content": "开始"},
        deepcopy(_COMPLETION_CALL),
        deepcopy(_COMPLETION_RESULT),
        deepcopy(_COMPLETION_RESULT),
        {"role": "user", "content": "继续"},
        deepcopy(_COMPLETION_RESULT),
    ]
    original = deepcopy(messages)

    repaired = AgentRunner._drop_orphan_tool_results(messages)

    _assert_tool_pairs(repaired)
    assert len(repaired) == 4
    assert repaired[2] == _COMPLETION_RESULT
    assert messages == original


def test_parallel_batch_keeps_real_results_and_repairs_only_missing_results() -> None:
    """并行调用部分缺失时，保留真实返回并在本批次末尾补齐缺失项。"""
    call = deepcopy(_COMPLETION_CALL)
    call["tool_calls"].append({
        "id": "call_read",
        "type": "function",
        "function": {"name": "evidence_read", "arguments": "{}"},
    })
    messages = [
        {"role": "user", "content": "核对"}, call,
        deepcopy(_COMPLETION_RESULT),
        {"role": "user", "content": "继续"},
    ]

    repaired = AgentRunner._backfill_missing_tool_results(messages)

    _assert_tool_pairs(repaired)
    assert repaired[2] == _COMPLETION_RESULT
    assert repaired[3]["tool_call_id"] == "call_read"
    assert repaired[3]["name"] == "evidence_read"
    assert repaired[-1] == messages[-1]


@pytest.mark.asyncio
@pytest.mark.parametrize("streaming", [False, True])
async def test_continuation_repairs_request_without_reexecuting_or_rewriting_history(
    streaming: bool,
) -> None:
    """完成后恢复出的重复调用可续聊，修复只作用于模型请求且不执行旧工具。"""
    messages = [
        {"role": "user", "content": "开始验收"},
        deepcopy(_COMPLETION_CALL),
        deepcopy(_COMPLETION_RESULT),
        {"role": "assistant", "content": "本轮完成"},
        deepcopy(_COMPLETION_CALL),
        {"role": "user", "content": "继续核对"},
    ]
    original = deepcopy(messages)
    response = LLMResponse(content="续聊成功", finish_reason="stop")
    provider = Mock()
    provider.chat_with_retry = AsyncMock(return_value=response)
    provider.chat_stream_with_retry = AsyncMock(return_value=response)
    hook = AgentHook()
    hook.wants_streaming = Mock(return_value=streaming)
    tools = ToolRegistry()
    tools.execute = AsyncMock()

    result = await AgentRunner(provider).run(AgentRunSpec(
        initial_messages=messages, tools=tools, model="test",
        max_iterations=2, max_tool_result_chars=8000, hook=hook,
    ))

    request = provider.chat_stream_with_retry if streaming else provider.chat_with_retry
    request.assert_awaited_once()
    with patch("app.service.nanobot.providers.openai_compat_provider.AsyncOpenAI"):
        compatible_provider = OpenAICompatProvider()
    _assert_tool_pairs(compatible_provider._sanitize_messages(
        request.await_args.kwargs["messages"]
    ))
    assert result.final_content == "续聊成功"
    assert result.messages[:-1] == original
    assert messages == original
    tools.execute.assert_not_awaited()
