from pydantic import BaseModel, Field


class HighlightRequestSchema(BaseModel):
    """
    重点目标标记请求
    """
    is_highlighted: bool = Field(description="是否标记为重点目标")
    highlight_reason: str | None = Field(default=None, description="标记理由")
