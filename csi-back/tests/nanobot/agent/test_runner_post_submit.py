"""完成工具调用后，默认仍可向模型暴露 tools；opt-in completion_tool_names 可禁用。"""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock

import pytest

import app.service.analyst.context as actx
import app.service.analyst.service as analyst_service
from app.schemas.agent.result import SUBMIT_TASK_RESULT_TOOL_NAME
from app.service.nanobot.agent.runner import AgentRunner, AgentRunSpec
from app.service.nanobot.agent.tools.registry import ToolRegistry
from app.service.analyst.tools import SubmitTaskResultTool
from app.service.nanobot.providers.base import LLMProvider, LLMResponse, ToolCallRequest


class _SeqProvider(LLMProvider):
    def __init__(self) -> None:
        super().__init__()
        self.chat_calls: list[dict[str, Any]] = []
        self._step = 0

    def get_default_model(self) -> str:
        return "gpt-4o"

    async def chat(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
        model: str | None = None,
        max_tokens: int = 4096,
        temperature: float = 0.7,
        reasoning_effort: str | None = None,
        tool_choice: str | dict[str, Any] | None = None,
    ) -> LLMResponse:
        self.chat_calls.append({"tools": tools, "tools_len": 0 if tools is None else len(tools)})
        self._step += 1
        if self._step == 1:
            return LLMResponse(
                content="",
                tool_calls=[
                    ToolCallRequest(
                        id="t1",
                        name=SUBMIT_TASK_RESULT_TOOL_NAME,
                        arguments={
                            "success": True,
                            "failure_reason": None,
                            "short_summary": "短",
                            "payload": {},
                        },
                    )
                ],
                finish_reason="tool_calls",
            )
        return LLMResponse(content="## 总结\n完成。", finish_reason="stop")


@pytest.mark.asyncio
async def test_runner_keeps_tools_after_submit_by_default(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(analyst_service.AnalystService, "broadcast_sse", AsyncMock())
    reg = ToolRegistry()
    reg.register(SubmitTaskResultTool())
    tok = actx.current_agent_id.set("agent1")
    try:
        prov = _SeqProvider()
        runner = AgentRunner(prov)
        spec = AgentRunSpec(
            initial_messages=[{"role": "user", "content": "hi"}],
            tools=reg,
            model="gpt-4o",
            max_iterations=8,
            max_tool_result_chars=8000,
            concurrent_tools=False,
        )
        res = await runner.run(spec)
        assert res.final_content == "## 总结\n完成。"
        assert len(prov.chat_calls) >= 2
        assert prov.chat_calls[0]["tools_len"] > 0
        assert prov.chat_calls[1]["tools_len"] > 0
    finally:
        actx.current_agent_id.reset(tok)


@pytest.mark.asyncio
async def test_runner_omits_tools_after_submit_when_opt_in(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(analyst_service.AnalystService, "broadcast_sse", AsyncMock())
    reg = ToolRegistry()
    reg.register(SubmitTaskResultTool())
    tok = actx.current_agent_id.set("agent1")
    try:
        prov = _SeqProvider()
        runner = AgentRunner(prov)
        spec = AgentRunSpec(
            initial_messages=[{"role": "user", "content": "hi"}],
            tools=reg,
            model="gpt-4o",
            max_iterations=8,
            max_tool_result_chars=8000,
            concurrent_tools=False,
            completion_tool_names=frozenset({SUBMIT_TASK_RESULT_TOOL_NAME}),
        )
        res = await runner.run(spec)
        assert res.final_content == "## 总结\n完成。"
        assert len(prov.chat_calls) >= 2
        assert prov.chat_calls[0]["tools_len"] > 0
        assert prov.chat_calls[1]["tools"] is None
    finally:
        actx.current_agent_id.reset(tok)
