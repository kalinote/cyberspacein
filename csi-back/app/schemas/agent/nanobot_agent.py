from datetime import datetime
from typing import TYPE_CHECKING, Any

from pydantic import BaseModel, Field

if TYPE_CHECKING:
    from app.models.agent.nanobot import NanobotAgentModel


class NanobotAgentCreateRequestSchema(BaseModel):
    """创建 Agent 请求体。所选资源必须是所属 Workspace 白名单的子集，由服务端强校验。"""

    workspace_id: str = Field(description="所属工作区ID", min_length=1)
    name: str = Field(description="Agent 名称", min_length=1, max_length=64)
    description: str | None = Field(default=None, description="Agent 描述")
    prompt_template_id: str = Field(
        description="选定的系统提示词模板ID，必须 ∈ workspace.prompt_template_ids",
        min_length=1,
    )
    model_config_id: str = Field(
        description="选定的模型配置ID，必须 ∈ workspace.model_config_ids",
        min_length=1,
    )
    tools: list[str] = Field(default_factory=list, description="启用的工具列表，⊆ workspace.enabled_tools")
    skills: list[str] = Field(default_factory=list, description="启用的技能列表，⊆ workspace.enabled_skills")
    mcp_servers: list[str] = Field(
        default_factory=list,
        description="启用的 MCP 服务名列表，元素 ∈ workspace.enabled_mcp_servers.keys()",
    )
    llm_config: dict[str, Any] = Field(
        default_factory=dict,
        description="LLM 生成参数（temperature / max_tokens / reasoning_effort 等），透传给 provider",
    )
    agent_builtin_prompt_ids: list[str] = Field(
        default_factory=list,
        description="AGENT 内置提示词文档 ID 列表，按顺序拼入 system prompt",
    )


class NanobotAgentUpdateRequestSchema(BaseModel):
    """更新 Agent 请求体（全字段覆盖式更新）。不允许修改 `workspace_id`，归属由重新创建实现。"""

    name: str = Field(description="Agent 名称", min_length=1, max_length=64)
    description: str | None = Field(default=None, description="Agent 描述")
    prompt_template_id: str = Field(description="选定的系统提示词模板ID", min_length=1)
    model_config_id: str = Field(description="选定的模型配置ID", min_length=1)
    tools: list[str] = Field(default_factory=list, description="启用的工具列表")
    skills: list[str] = Field(default_factory=list, description="启用的技能列表")
    mcp_servers: list[str] = Field(default_factory=list, description="启用的 MCP 服务名列表")
    llm_config: dict[str, Any] = Field(default_factory=dict, description="LLM 生成参数")
    agent_builtin_prompt_ids: list[str] = Field(
        default_factory=list,
        description="AGENT 内置提示词文档 ID 列表",
    )


class NanobotAgentSchema(BaseModel):
    """Agent 响应体（仅配置维度；运行时状态见 nanobot_sessions）。"""

    id: str = Field(description="Agent ID")
    workspace_id: str = Field(description="所属工作区ID")
    name: str = Field(description="Agent 名称")
    description: str | None = Field(default=None, description="Agent 描述")
    prompt_template_id: str = Field(description="选定的系统提示词模板ID")
    model_config_id: str = Field(description="选定的模型配置ID")
    tools: list[str] = Field(default_factory=list, description="启用的工具列表")
    skills: list[str] = Field(default_factory=list, description="启用的技能列表")
    mcp_servers: list[str] = Field(default_factory=list, description="启用的 MCP 服务名列表")
    llm_config: dict[str, Any] = Field(default_factory=dict, description="LLM 生成参数")
    agent_builtin_prompt_ids: list[str] = Field(
        default_factory=list,
        description="AGENT 内置提示词文档 ID 列表",
    )
    created_at: datetime = Field(description="创建时间")
    updated_at: datetime = Field(description="更新时间")

    @classmethod
    def from_doc(cls, doc: "NanobotAgentModel") -> "NanobotAgentSchema":
        return cls(
            id=doc.id,
            workspace_id=doc.workspace_id,
            name=doc.name,
            description=doc.description,
            prompt_template_id=doc.prompt_template_id,
            model_config_id=doc.model_config_id,
            tools=list(doc.tools),
            skills=list(doc.skills),
            mcp_servers=list(doc.mcp_servers),
            llm_config=dict(doc.llm_config or {}),
            agent_builtin_prompt_ids=list(doc.agent_builtin_prompt_ids or []),
            created_at=doc.created_at,
            updated_at=doc.updated_at,
        )


class NanobotAgentListItemSchema(BaseModel):
    """Agent 名称列表项（供下拉选择使用）。"""

    id: str = Field(description="Agent ID")
    name: str = Field(description="Agent 名称")
    workspace_id: str = Field(description="所属工作区ID")


class AgentServiceError(Exception):
    """AgentService 统一业务异常，携带 HTTP 状态码与消息。"""

    def __init__(self, code: int, message: str, data: Any | None = None) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.data = data
