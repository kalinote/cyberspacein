from datetime import datetime
from pydantic import BaseModel, Field


class AgentModelConfigCreateRequestSchema(BaseModel):
    name: str = Field(description="模型名称", min_length=1)
    description: str | None = Field(default=None, description="模型描述")
    base_url: str = Field(description="模型基础URL", min_length=1)
    api_key: str = Field(description="模型API密钥")
    model: str = Field(description="模型ID", min_length=1)


class AgentModelConfigSchema(BaseModel):
    id: str = Field(description="配置ID")
    name: str = Field(description="模型名称")
    description: str | None = Field(default=None, description="模型描述")
    base_url: str = Field(description="模型基础URL")
    api_key: str = Field(description="模型API密钥")
    model: str = Field(description="模型ID")
    created_at: datetime = Field(description="创建时间")
    updated_at: datetime = Field(description="更新时间")
