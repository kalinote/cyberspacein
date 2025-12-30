from typing import Any
from pydantic import BaseModel, Field


class SDKResultRequest(BaseModel):
    status: str = Field(description="运行结果")
    error: str | None = Field(default=None, description="错误信息")
    outputs: dict[str, Any] = Field(default={}, description="输出结果")
