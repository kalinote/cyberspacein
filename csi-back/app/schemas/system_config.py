from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class ConfigChangesRequest(BaseModel):
    expected_version: int = Field(ge=0)
    changes: dict[str, Any] = Field(default_factory=dict)


class ConfigVersionActionRequest(BaseModel):
    expected_version: int = Field(ge=0)
    confirmed: bool = True


class ConfigCoordinationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    coordination_token: str = Field(min_length=64, max_length=64)
    resolutions: dict[str, Literal["file", "database"]] = Field(default_factory=dict)
    confirmed: bool = True
