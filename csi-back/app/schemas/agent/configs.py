from typing import Any
from pydantic import BaseModel, Field


class ModelConfigListItemSchema(BaseModel):
    id: str = Field(description="模型配置ID")
    name: str = Field(description="模型配置名称")


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
    
class AgentConfigsStatisticsResponse(BaseModel):
    agent_count: int = Field(default=0, description="分析引擎数量")
    model_count: int = Field(default=0, description="模型资源数量")
    prompt_template_count: int = Field(default=0, description="提示词模板数量")
    tools_count: int = Field(default=0, description="工具数量")