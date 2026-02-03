from datetime import datetime
from typing import Any
from pydantic import BaseModel, Field

from app.schemas.constants import EntityType


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


class AgentCreateRequestSchema(BaseModel):
    name: str = Field(description="Agent名称", min_length=1)
    description: str = Field(description="Agent描述")
    prompt_template_id: str = Field(description="提示词模板id")
    model_id: str = Field(description="模型配置id")
    llm_config: dict[str, Any] = Field(description="LLM配置，包括模型、温度等")
    tools: list[str] = Field(default_factory=list, description="工具列表")


class AgentListItemSchema(BaseModel):
    id: str = Field(description="分析引擎ID")
    name: str = Field(description="分析引擎名称")


class AgentSchema(BaseModel):
    id: str = Field(description="分析引擎ID")
    name: str = Field(description="Agent名称")
    description: str = Field(description="Agent描述")
    prompt_template_id: str = Field(description="提示词模板id")
    model_id: str = Field(description="模型配置id")
    llm_config: dict[str, Any] = Field(description="LLM配置，包括模型、温度等")
    tools: list[str] = Field(description="工具列表")
    created_at: datetime = Field(description="创建时间")
    updated_at: datetime = Field(description="更新时间")

class StartAgentRequestSchema(BaseModel):
    entity_uuid: str = Field(description="实体UUID")
    entity_type: EntityType = Field(description="实体类型")
    agent_id: str = Field(description="分析引擎ID")


class StartAgentResponseSchema(BaseModel):
    thread_id: str = Field(description="会话ID")


class AgentStatusPayloadSchema(BaseModel):
    thread_id: str = Field(description="会话ID")
    status: str = Field(description="会话状态")
    fields: dict[str, Any] = Field(default_factory=dict, description="启动时字段")
    steps: list[dict] = Field(default_factory=list, description="执行步骤")
    todos: list[dict] = Field(default_factory=list, description="Todo 项")
    updated_at: datetime = Field(description="更新时间")
    is_running: bool = Field(description="是否正在运行")


class ApprovalRequiredPayloadSchema(BaseModel):
    payload: dict[str, Any] = Field(default_factory=dict, description="审批上下文")
    thread_id: str = Field(description="会话ID")


class SSEEventSchema(BaseModel):
    type: str = Field(description="事件类型")
    data: dict[str, Any] = Field(default_factory=dict, description="事件数据")


class ApproveRequestSchema(BaseModel):
    thread_id: str = Field(description="会话ID")
    decisions: list[dict] = Field(description="审批决策列表")


class ApproveResponseSchema(BaseModel):
    thread_id: str = Field(description="会话ID")
    status: str = Field(description="操作状态")
