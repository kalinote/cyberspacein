"""HITL（Human-in-the-Loop）审批：统一信封与来源约定。"""
from __future__ import annotations

import re
from typing import Any

from pydantic import BaseModel, Field

_SOURCE_PATTERN = re.compile(r"^[a-z][a-z0-9_]*:[a-z][a-z0-9_]*$")


class HitlSource:
    """`source` 字段取值：`{行为}:{名称}`。"""

    TOOL_MODIFY_ENTITY = "tool:modify_entity"


def build_source(behavior: str, name: str) -> str:
    return f"{behavior}:{name}"


def validate_source(source: str) -> str:
    s = str(source or "").strip()
    if not _SOURCE_PATTERN.match(s):
        raise ValueError(f"无效的 HITL source: {source!r}，期望格式 behavior:name")
    return s


class PendingApprovalRecord(BaseModel):
    approval_request_id: str = Field(description="本次审批请求 ID")
    source: str = Field(description="HITL 来源，如 tool:modify_entity")
    requested_at: str = Field(description="发起时间 ISO8601")
    payload: dict[str, Any] = Field(default_factory=dict, description="来源私有展示/执行数据")


class ApprovalRequiredEventData(BaseModel):
    agent_id: str
    session_id: str
    approval_request_id: str
    source: str
    resolution: str | None = None
    reject_reasons: list[str] | None = None
    payload: dict[str, Any] = Field(default_factory=dict)


class ModifyEntityHitlPayload(BaseModel):
    entity_type: str
    entity_uuid: str
    modifications: list[dict[str, Any]]
    reason: str
