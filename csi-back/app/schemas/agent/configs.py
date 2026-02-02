from typing import Any
from pydantic import BaseModel, Field

class AgentToolsParameterSchema(BaseModel):
    name: str = Field(description="参数名称")
    description: str = Field(description="参数描述")
    type: str = Field(description="参数类型")
    required: bool = Field(description="是否必填")
    default: Any = Field(description="默认值")

class AgentToolsResponseSchema(BaseModel):
    name: str = Field(description="工具名称")
    description: str = Field(description="工具描述")
    parameters: list[AgentToolsParameterSchema] = Field(description="工具参数")