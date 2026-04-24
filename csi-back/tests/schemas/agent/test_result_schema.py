"""MIGRATION_PLAN §12.16：结构化最终结果 schema 与解析器。"""

from __future__ import annotations

from datetime import datetime

import pytest
from pydantic import ValidationError

from app.schemas.agent.result import (
    RESULT_FORMAT_INSTRUCTION,
    ResultPayloadSchema,
    build_response_format_schema,
    parse_run_result,
)


def test_result_schema_roundtrip() -> None:
    s = ResultPayloadSchema(summary="x", success=True, details={"a": 1}, todos_snapshot=[{"id": "1"}])
    dumped = s.model_dump()
    got = ResultPayloadSchema.model_validate(dumped)
    assert got.summary == "x"
    assert got.success is True
    assert got.details["a"] == 1


def test_result_schema_required_fields() -> None:
    with pytest.raises(ValidationError):
        ResultPayloadSchema.model_validate({"success": True})
    with pytest.raises(ValidationError):
        ResultPayloadSchema.model_validate({"summary": "x"})


def test_response_format_payload_shape() -> None:
    payload = build_response_format_schema()
    assert payload["type"] == "json_schema"
    js = payload["json_schema"]
    assert js["name"] == "result"
    assert "schema" in js and isinstance(js["schema"], dict)
    assert js["strict"] is False


def test_parse_strict_json() -> None:
    schema, ok = parse_run_result('{"summary":"x","success":true,"details":{}}')
    assert ok is True
    assert schema.summary == "x"
    assert schema.success is True


def test_parse_fenced_json() -> None:
    schema, ok = parse_run_result(
        "```json\n"
        '{ "summary": "x", "success": true, "failure_reason": null, "details": {}, "todos_snapshot": [] }\n'
        "```"
    )
    assert ok is True
    assert schema.summary == "x"


def test_parse_extra_text_around_json() -> None:
    schema, ok = parse_run_result(
        "前缀\n"
        '{ "summary": "x", "success": true, "failure_reason": null, "details": {}, "todos_snapshot": [] }\n'
        "后缀"
    )
    assert ok is True
    assert schema.success is True


def test_parse_invalid_json_fallback() -> None:
    raw = "这不是 JSON"
    schema, ok = parse_run_result(raw)
    assert ok is False
    assert schema.success is False
    assert "无法解析" in (schema.failure_reason or "")
    assert schema.summary == raw


def test_parse_empty_or_none() -> None:
    schema, ok = parse_run_result(None)
    assert ok is False
    assert schema.success is False
    assert "未返回" in (schema.failure_reason or "")

    schema2, ok2 = parse_run_result("   ")
    assert ok2 is False
    assert schema2.success is False


def test_parse_missing_required_fallback() -> None:
    schema, ok = parse_run_result('{"success": true}')
    assert ok is False
    assert schema.success is False


def test_parse_long_content_truncates_to_2000() -> None:
    raw = "x" * 5000
    schema, ok = parse_run_result(raw)
    assert ok is False
    assert len(schema.summary) == 2000


def test_result_format_instruction_contains_keys() -> None:
    text = RESULT_FORMAT_INSTRUCTION
    for key in ["summary", "success", "failure_reason", "details", "todos_snapshot", "输出格式"]:
        assert key in text
    # 提示词里应包含 json 围栏示例
    assert "```json" in text

