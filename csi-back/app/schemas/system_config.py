from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class ConfigChangesRequest(BaseModel):
    expected_version: int = Field(ge=0)
    changes: dict[str, Any] = Field(default_factory=dict)


class ConfigVersionActionRequest(BaseModel):
    expected_version: int = Field(ge=0)
    confirmed: bool = True
