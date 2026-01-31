from datetime import datetime
from beanie import Document
from pydantic import Field

class AgentModelConfigModel(Document):
    id: str = Field(alias="_id")
    name: str = Field(description="模型名称")
    description: str | None = Field(default=None, description="模型描述")
    base_url: str = Field(description="模型基础URL")
    api_key: str = Field(description="模型API密钥")
    model: str = Field(description="模型ID")
    created_at: datetime = Field(default_factory=datetime.now, description="创建时间")
    updated_at: datetime = Field(default_factory=datetime.now, description="更新时间")

    class Settings:
        name = "agent_models"
        indexes = ["name"]
        
class AgentPromptTemplateModel(Document):
    id: str = Field(alias="_id")
    name: str = Field(description="提示词模板名称")
    description: str = Field(description="提示词模板描述")
    system_prompt: str = Field(description="系统提示词")
    user_prompt: str = Field(description="第一段用户提示词模板")
    created_at: datetime = Field(default_factory=datetime.now, description="创建时间")
    updated_at: datetime = Field(default_factory=datetime.now, description="更新时间")

    class Settings:
        name = "agent_prompt_templates"
        indexes = ["name"]