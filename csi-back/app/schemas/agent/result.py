"""Agent 运行结果相关 Schema。

- `SubmitTaskResultParams`：`submit_task_result` 工具参数（机读权威结果）。
- `TASK_COMPLETION_INSTRUCTION`：追加到 system prompt，约束「工具收口 + 最后一轮 Markdown」流程。
- `ResultPayloadSchema` / `parse_run_result`：历史兼容与测试保留（不再作为 `/start` 终局解析路径）。
"""
from __future__ import annotations

from typing import Any

import json_repair
from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.schemas.constants import AgentStopReasonEnum

SUBMIT_TASK_RESULT_TOOL_NAME = "submit_task_result"


class SubmitTaskResultParams(BaseModel):
    """通过 `submit_task_result` 提交的机读结果（权威业务态）。"""

    success: bool = Field(description="是否达成任务目标")
    failure_reason: str | None = Field(
        default=None,
        description="未达成时必填原因；success=True 时留空",
    )
    short_summary: str = Field(description="简短摘要，供日志与 SSE 提示")
    payload: dict[str, Any] = Field(
        default_factory=dict,
        description="完整结构化业务结果",
    )

    @model_validator(mode="after")
    def _failure_requires_reason(self) -> SubmitTaskResultParams:
        if not self.success:
            if self.failure_reason is None or not str(self.failure_reason).strip():
                raise ValueError("success 为 false 时必须提供非空 failure_reason")
        return self


TASK_COMPLETION_INSTRUCTION: str = (
    "# 任务结束流程（强制）\n\n"
    "1. 在正常工作阶段可自由调用可用工具完成分析与修改。\n"
    "2. 当你认为机读结果已齐备时，**必须调用工具** `"
    + SUBMIT_TASK_RESULT_TOOL_NAME
    + "`，并在参数中传入：\n"
    "   - `success`：是否达成目标；\n"
    "   - `failure_reason`：失败时必填，成功时为 null；\n"
    "   - `short_summary`：一句话摘要；\n"
    "   - `payload`：完整结构化业务结果（对象）。\n"
    "3. 在收到该工具返回的提示后，**下一轮回复**必须仅为面向用户的 **Markdown 纯文本**总结，"
    "不要再调用任何工具，也不要输出 JSON。\n"
    "4. **仅允许调用当前请求里已列出的工具**；禁止编造或调用未列出的工具名，若未出现在工具列表中则一律不得调用。\n"
    "5. **禁止滥用 spawn**：仅在需要进行任务分解或任务可以并行执行时使用 spawn，如果任务只能串行执行或只需要单步骤完成，则不要使用 spawn."
    "等方式轮询其他子任务；子任务完成时结果会通过系统消息注入会话，请直接基于上下文与"
    "已返回的工具结果继续推理，避免链式 spawn。\n"
)


class RunAnalysisResultPayloadSchema(BaseModel):
    """`run_analysis` 写入会话与 SSE `result` 事件内 `result` 字段的载荷。"""

    model_config = ConfigDict(use_enum_values=True)

    success: bool = Field(description="业务是否达成目标（以 submit_task_result 为准）")
    failure_reason: str | None = Field(default=None, description="失败原因")
    short_summary: str = Field(default="", description="简短摘要")
    payload: dict[str, Any] = Field(default_factory=dict, description="结构化业务结果")
    user_markdown: str = Field(default="", description="面向用户的 Markdown 正文")
    tools_used: list[str] = Field(default_factory=list, description="本轮调用的工具名列表")
    stop_reason: AgentStopReasonEnum | None = Field(
        default=None,
        description="Agent 推理循环结束原因",
    )
    completion_received: bool = Field(
        default=False,
        description="是否收到 submit_task_result",
    )


class ResultPayloadSchema(BaseModel):
    """历史：曾用于助手终局 JSON；现由工具 `submit_task_result` 承担机读结果。"""

    summary: str = Field(description="本次运行的核心结论/摘要，必填")
    success: bool = Field(description="是否达成预期目标（False 时 failure_reason 必填）")
    failure_reason: str | None = Field(
        default=None,
        description="未达成目标的原因说明；success=True 时留空",
    )
    details: dict[str, Any] = Field(
        default_factory=dict, description="额外结构化细节，按业务场景自由扩展"
    )
    todos_snapshot: list[dict[str, Any]] = Field(
        default_factory=list, description="本次运行结束时的待办列表快照"
    )


RESULT_FORMAT_INSTRUCTION: str = (
    "已弃用：请改用 `TASK_COMPLETION_INSTRUCTION` 与工具 `"
    + SUBMIT_TASK_RESULT_TOOL_NAME
    + "`。"
)


def build_response_format_schema() -> dict[str, Any]:
    """历史兼容：返回 OpenAI 兼容的 `response_format=json_schema` 载荷（业务层已不再使用）。"""
    return {
        "type": "json_schema",
        "json_schema": {
            "name": "result",
            "schema": ResultPayloadSchema.model_json_schema(),
            "strict": False,
        },
    }


def parse_run_result(raw: str | None) -> tuple[ResultPayloadSchema, bool]:
    """解析字符串为 ResultPayloadSchema（兼容旧测试/脚本；`run_analysis` 不再依赖此路径）。"""
    if raw is None or not raw.strip():
        return (
            ResultPayloadSchema(
                summary="",
                success=False,
                failure_reason="LLM 未返回任何内容",
            ),
            False,
        )

    text = raw.strip()
    try:
        parsed = json_repair.loads(text)
    except Exception:
        parsed = None

    if isinstance(parsed, dict):
        try:
            return ResultPayloadSchema.model_validate(parsed), True
        except Exception:
            pass

    fallback = ResultPayloadSchema(
        summary=text[:2000],
        success=False,
        failure_reason="结果格式异常，无法解析为 ResultPayloadSchema",
    )
    return fallback, False


__all__ = [
    "SUBMIT_TASK_RESULT_TOOL_NAME",
    "SubmitTaskResultParams",
    "TASK_COMPLETION_INSTRUCTION",
    "RunAnalysisResultPayloadSchema",
    "ResultPayloadSchema",
    "RESULT_FORMAT_INSTRUCTION",
    "build_response_format_schema",
    "parse_run_result",
]
