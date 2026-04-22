from pydantic import BaseModel, Field


class ModelConfigListItemSchema(BaseModel):
    id: str = Field(description="模型配置ID")
    name: str = Field(description="模型配置名称")
