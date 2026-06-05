"""Agent 运行结果相关 Schema。

- `SubmitTaskResultParams`：`submit_task_result` 工具参数。
- `TASK_SUBMIT_GUIDANCE`：可选的 system prompt 指导（何时调用 submit）。
- `TaskSubmissionRecordSchema`：持久化到 session.task_submissions 的单条记录。
- `ResultPayloadSchema` / `parse_run_result`：历史兼容与测试保留。
"""
from __future__ import annotations

from datetime import datetime
from typing import Any

import json_repair
from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.schemas.constants import AgentStopReasonEnum

SUBMIT_TASK_RESULT_TOOL_NAME = "submit_task_result"


class SubmitTaskResultParams(BaseModel):
    """通过 `submit_task_result` 提交的机读结果。"""

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


class TaskSubmissionRecordSchema(BaseModel):
    """单次 submit_task_result 的持久化记录。"""

    id: str = Field(description="提交记录 ID")
    success: bool = Field(description="是否达成任务目标")
    failure_reason: str | None = Field(default=None, description="失败原因")
    short_summary: str = Field(default="", description="简短摘要")
    payload: dict[str, Any] = Field(default_factory=dict, description="结构化业务结果")
    submitted_at: str = Field(description="提交时间 ISO8601")

    @classmethod
    def from_submit_params(
        cls,
        submission_id: str,
        params: SubmitTaskResultParams | dict[str, Any],
        *,
        submitted_at: datetime | None = None,
    ) -> TaskSubmissionRecordSchema:
        if isinstance(params, dict):
            params = SubmitTaskResultParams.model_validate(params)
        ts = submitted_at or datetime.now()
        return cls(
            id=submission_id,
            success=params.success,
            failure_reason=params.failure_reason,
            short_summary=params.short_summary or "",
            payload=dict(params.payload or {}),
            submitted_at=ts.isoformat(),
        )


TASK_SUBMIT_GUIDANCE: str = (
    "# 任务结果提交工具（可选）\n\n"
    "工具 `"
    + SUBMIT_TASK_RESULT_TOOL_NAME
    + "` 用于在**一段可交付工作**结束、失败需固化、或需要写入机读业务结果时提交结构化结果。\n"
    "参数：`success`、`failure_reason`（失败时必填）、`short_summary`、`payload`。\n\n"
    "**适合调用**：子任务/分析/修改已完成或明确失败，需要记录机读 payload 时。\n"
    "**不必调用**：寒暄、澄清、任务未完成、仅中间进度、简单问答。\n"
    "同一对话可多次调用，每次对应一个子任务；调用后仍可继续对话或使用其他工具。\n\n"
    "**仅允许调用当前请求里已列出的工具**；禁止编造未列出的工具名。\n"
    "**禁止滥用 spawn**：仅在任务可分解或并行时使用 spawn；串行或单步任务勿用 spawn 轮询子任务。\n"
)

TASK_COMPLETION_INSTRUCTION = TASK_SUBMIT_GUIDANCE


class RunAnalysisResultPayloadSchema(BaseModel):
    """`run_analysis` 写入会话与 SSE `result` 事件内 `result` 字段的载荷（最近一轮）。"""

    model_config = ConfigDict(use_enum_values=True)

    success: bool = Field(description="本轮会话结束是否为 COMPLETED（非仅是否调用 submit）")
    failure_reason: str | None = Field(default=None, description="失败原因")
    short_summary: str = Field(default="", description="兼容字段：最近 submit 的摘要")
    payload: dict[str, Any] = Field(
        default_factory=dict,
        description="兼容字段：最近 submit 的 payload",
    )
    user_markdown: str = Field(default="", description="面向用户的 Markdown 正文")
    tools_used: list[str] = Field(default_factory=list, description="本轮调用的工具名列表")
    stop_reason: AgentStopReasonEnum | None = Field(
        default=None,
        description="Agent 推理循环结束原因",
    )
    completion_received: bool = Field(
        default=False,
        description="本轮是否调用过 submit_task_result",
    )
    last_submission: TaskSubmissionRecordSchema | None = Field(
        default=None,
        description="本轮最后一次 submit_task_result 记录",
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
    "已弃用：请改用 `TASK_SUBMIT_GUIDANCE` 与工具 `"
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
    "TaskSubmissionRecordSchema",
    "TASK_SUBMIT_GUIDANCE",
    "TASK_COMPLETION_INSTRUCTION",
    "RunAnalysisResultPayloadSchema",
    "ResultPayloadSchema",
    "RESULT_FORMAT_INSTRUCTION",
    "build_response_format_schema",
    "parse_run_result",
]
