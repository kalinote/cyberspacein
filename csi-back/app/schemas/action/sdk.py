from typing import Any, Literal
from pydantic import BaseModel, Field


class SDKResultRequest(BaseModel):
    result_id: str = Field(min_length=1, max_length=128)
    attempt: int = Field(ge=1)
    status: Literal["success", "failed", "cancelled", "timed_out"] = Field(description="运行结果")
    error: str | None = Field(default=None, description="错误信息")
    outputs: dict[str, Any] = Field(default_factory=dict, description="输出结果")
    exit_code: int | None = None


class SDKHeartbeatRequest(BaseModel):
    progress: float = Field(default=0, ge=0, le=100)
    message: str = Field(default="", max_length=1024)


class SDKHeartbeatResponse(BaseModel):
    command: Literal["continue", "cancel"] = "continue"
    lease_expires_at: str
    component_token: str | None = None


class SDKComponentInitResponse(BaseModel):
    action_id: str
    node_instance_id: str
    component_run_id: str
    component_id: str
    attempt: int
    config: dict[str, Any] = Field(default_factory=dict)
    inputs: dict[str, Any] = Field(default_factory=dict)
    outputs: dict[str, Any] = Field(default_factory=dict)
    heartbeat_interval: int
    lease_seconds: int
    timeout_seconds: int
