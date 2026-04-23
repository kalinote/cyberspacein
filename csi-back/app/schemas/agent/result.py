"""Agent 最终运行结果的结构化 Schema（MIGRATION_PLAN §3.5）

- `ResultPayloadSchema`：所有 Agent 本轮 `/start → bot.run` 最终产出的结构化载荷。
- `RESULT_FORMAT_INSTRUCTION`：需要追加到 system prompt 末尾，告诉 LLM 按此结构返回。
- `parse_run_result(...)`：把 `RunResult.content` 尽力解析成 `ResultPayloadSchema`，解析失败时
  返回一个 `success=False` 的兜底实例，保证上层总能拿到结构化结果。

解析策略优先级：
1. 若 `response_format: json_schema` 严格模式可用（取决于 provider），`content` 本身应该已是合法 JSON。
2. 不严格模式或输出偶有 markdown/前后缀时，用 `json_repair.loads` 做宽松修复。
3. 完全无法解析时，`summary=raw, success=False, failure_reason="格式异常"`。
"""
from __future__ import annotations

from typing import Any

import json_repair
from pydantic import BaseModel, Field


class ResultPayloadSchema(BaseModel):
    """Agent 最终结果载荷。

    设计目标：
    - 字段尽量少、必填项明确，便于 `response_format=json_schema strict=True` 使用。
    - `details` 作为弱结构容器，允许不同业务场景按需扩展，不破坏核心 schema。
    - `todos_snapshot` 记录最终 todos 状态；前端可不依赖，仅用于调试 / 回溯。
    """

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
    "# 输出格式（强制）\n\n"
    "你在本次对话结束时，必须以**纯 JSON 对象**形式输出最终结论，结构如下：\n\n"
    "```json\n"
    "{\n"
    '  "summary": "<一段中文结论摘要>",\n'
    '  "success": true,\n'
    '  "failure_reason": null,\n'
    '  "details": {},\n'
    '  "todos_snapshot": []\n'
    "}\n"
    "```\n\n"
    "规则：\n"
    "- `summary` 必填，简洁描述本次执行的关键结论。\n"
    "- `success=false` 时必须在 `failure_reason` 中说明原因。\n"
    "- `details` 与 `todos_snapshot` 可留空；需要时按业务场景补充。\n"
    "- 禁止在 JSON 外输出任何其它文本（不要 Markdown 代码块围栏、不要解释）。"
)


def build_response_format_schema() -> dict[str, Any]:
    """返回 OpenAI 兼容的 `response_format=json_schema` 载荷。"""
    return {
        "type": "json_schema",
        "json_schema": {
            "name": "result",
            "schema": ResultPayloadSchema.model_json_schema(),
            "strict": False,
        },
    }


def parse_run_result(raw: str | None) -> tuple[ResultPayloadSchema, bool]:
    """解析 RunResult.content 为 ResultPayloadSchema。

    返回 `(schema, parsed_ok)`：
    - parsed_ok=True：严格/宽松 JSON 解析成功并通过 Pydantic 校验。
    - parsed_ok=False：解析失败，返回一个 summary=raw / success=False 的兜底实例。
    """
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
    "ResultPayloadSchema",
    "RESULT_FORMAT_INSTRUCTION",
    "build_response_format_schema",
    "parse_run_result",
]
