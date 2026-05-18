"""AgentStopReasonEnum 与 RunAnalysisResultPayloadSchema 约束测试。"""

import pytest
from pydantic import ValidationError

from app.schemas.agent.result import RunAnalysisResultPayloadSchema
from app.schemas.constants import AgentStopReasonEnum


def test_coerce_from_string() -> None:
    assert AgentStopReasonEnum.coerce("completed") is AgentStopReasonEnum.COMPLETED
    assert AgentStopReasonEnum.coerce(AgentStopReasonEnum.ERROR) is AgentStopReasonEnum.ERROR
    assert AgentStopReasonEnum.coerce(None) is None
    assert AgentStopReasonEnum.coerce("not_a_reason") is None


def test_all_runner_values_are_enum_members() -> None:
    expected = {
        "completed",
        "tool_error",
        "error",
        "empty_final_response",
        "max_iterations",
        "awaiting_approval",
    }
    assert {m.value for m in AgentStopReasonEnum} == expected


def test_run_analysis_result_payload_serializes_stop_reason() -> None:
    payload = RunAnalysisResultPayloadSchema(
        success=True,
        short_summary="ok",
        stop_reason=AgentStopReasonEnum.MAX_ITERATIONS,
        completion_received=True,
    ).model_dump()
    assert payload["stop_reason"] == "max_iterations"


def test_run_analysis_result_payload_rejects_invalid_stop_reason() -> None:
    with pytest.raises(ValidationError):
        RunAnalysisResultPayloadSchema(
            success=True,
            stop_reason="legacy_unknown",
            completion_received=True,
        )
