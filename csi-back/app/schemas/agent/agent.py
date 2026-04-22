from datetime import datetime
from typing import TYPE_CHECKING, Any

from pydantic import BaseModel, Field

from app.schemas.constants import EntityType

if TYPE_CHECKING:
    from app.models.agent.configs import AgentModelConfigModel, AgentPromptTemplateModel


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

    @classmethod
    def from_doc(cls, doc: "AgentModelConfigModel") -> "AgentModelConfigSchema":
        return cls(
            id=doc.id,
            name=doc.name,
            description=doc.description,
            base_url=doc.base_url,
            api_key=doc.api_key,
            model=doc.model,
            created_at=doc.created_at,
            updated_at=doc.updated_at,
        )


class AgentPromptTemplateCreateRequestSchema(BaseModel):
    name: str = Field(description="提示词模板名称", min_length=1)
    description: str = Field(description="提示词模板描述")
    system_prompt: str = Field(description="系统提示词")
    user_prompt: str = Field(description="第一段用户提示词模板")


class AgentPromptTemplateSchema(BaseModel):
    id: str = Field(description="模板ID")
    name: str = Field(description="提示词模板名称")
    description: str = Field(description="提示词模板描述")
    system_prompt: str = Field(description="系统提示词")
    user_prompt: str = Field(description="第一段用户提示词模板")
    created_at: datetime = Field(description="创建时间")
    updated_at: datetime = Field(description="更新时间")

    @classmethod
    def from_doc(cls, doc: "AgentPromptTemplateModel") -> "AgentPromptTemplateSchema":
        return cls(
            id=doc.id,
            name=doc.name,
            description=doc.description,
            system_prompt=doc.system_prompt,
            user_prompt=doc.user_prompt,
            created_at=doc.created_at,
            updated_at=doc.updated_at,
        )


class AgentCreateRequestSchema(BaseModel):
    name: str = Field(description="Agent名称", min_length=1)
    description: str = Field(description="Agent描述")
    prompt_template_id: str = Field(description="提示词模板id")
    model_id: str = Field(description="模型配置id")
    llm_config: dict[str, Any] = Field(description="LLM配置，包括模型、温度等")
    tools: list[str] = Field(default_factory=list, description="工具列表")


class StartAgentRequestSchema(BaseModel):
    entity_uuid: str = Field(description="实体UUID")
    entity_type: EntityType = Field(description="实体类型")
    agent_id: str = Field(description="分析引擎ID")


class ApproveRequestSchema(BaseModel):
    thread_id: str = Field(description="会话ID")
    decisions: list[dict] = Field(description="审批决策列表")
