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
    agent_id: str = Field(description="分析引擎ID")
    user_prompt: str | None = Field(
        default=None,
        description="用户本轮输入的 prompt",
    )
    entity_uuid: str | None = Field(default=None, description="实体UUID（可选业务上下文）")
    entity_type: EntityType | None = Field(default=None, description="实体类型（可选业务上下文）")
    extra_context: dict[str, Any] = Field(
        default_factory=dict, description="其它业务上下文，透传给 AnalystService"
    )


class StartAgentResponseSchema(BaseModel):
    agent_id: str = Field(description="分析引擎ID")
    session_id: str = Field(description="本次启动分配的会话ID")


class ApproveRequestSchema(BaseModel):
    agent_id: str = Field(description="分析引擎ID")
    decisions: list[dict] = Field(description="审批决策列表")


class CancelAgentRequestSchema(BaseModel):
    agent_id: str = Field(description="分析引擎ID")
    reason: str = Field(default="user cancel", description="取消原因，用于审计与 SSE 日志")


class CancelAgentResponseSchema(BaseModel):
    agent_id: str = Field(description="分析引擎ID")
    cancelled: bool = Field(description="是否真的向后台任务发出了取消请求（任务不在则为 False）")


class ToolDescriptorSchema(BaseModel):
    name: str = Field(description="工具名")
    description: str = Field(description="工具描述")
    read_only: bool = Field(description="是否只读")
    exclusive: bool = Field(description="是否需要独占执行（如涉及审批）")
