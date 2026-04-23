from datetime import datetime
from typing import TYPE_CHECKING, Any, Literal

from pydantic import BaseModel, Field

if TYPE_CHECKING:
    from app.models.agent.nanobot import NanobotWorkspaceModel


class MCPServerConfigSchema(BaseModel):
    """MCP 服务连接配置（对应 nanobot.config.schema.MCPServerConfig，仅用于接口传参/响应）。"""

    type: Literal["stdio", "sse", "streamableHttp"] | None = Field(
        default=None,
        description="连接类型，留空时由 nanobot 根据其它字段自动判断",
    )
    command: str = Field(default="", description="stdio 模式下执行的命令")
    args: list[str] = Field(default_factory=list, description="stdio 模式命令行参数")
    env: dict[str, str] = Field(default_factory=dict, description="stdio 模式额外环境变量")
    url: str = Field(default="", description="sse / streamableHttp 模式下的服务地址")
    headers: dict[str, str] = Field(default_factory=dict, description="http/sse 模式下的自定义请求头")
    tool_timeout: int = Field(default=30, ge=1, description="单个工具调用超时秒数")
    enabled_tools: list[str] = Field(
        default_factory=lambda: ["*"],
        description="该 MCP 服务下允许注册的工具列表，['*'] 表示全部",
    )


class NanobotWorkspaceCreateRequestSchema(BaseModel):
    """创建 Workspace 请求体。"""

    name: str = Field(description="工作区名称", min_length=1, max_length=64)
    description: str | None = Field(default=None, description="工作区描述")
    prompt_template_ids: list[str] = Field(
        default_factory=list,
        description="可选的系统提示词模板ID列表（来自 /agent/configs/prompt-templates），Agent 只能从中选择一个",
    )
    model_config_ids: list[str] = Field(
        default_factory=list,
        description="可选的模型配置ID列表（来自 /agent/configs/models），Agent 只能从中选择一个",
    )
    enabled_tools: list[str] = Field(default_factory=list, description="工具白名单，Agent 可用工具必须是该列表子集")
    enabled_skills: list[str] = Field(default_factory=list, description="技能白名单，Agent 可用技能必须是该列表子集")
    enabled_mcp_servers: dict[str, MCPServerConfigSchema] = Field(
        default_factory=dict,
        description="MCP 服务白名单，key=server_name，value=MCPServerConfig；Agent 只能引用这里声明过的 server_name",
    )


class NanobotWorkspaceUpdateRequestSchema(BaseModel):
    """更新 Workspace 请求体（全字段覆盖式更新，保持与创建语义一致）。"""

    name: str = Field(description="工作区名称", min_length=1, max_length=64)
    description: str | None = Field(default=None, description="工作区描述")
    prompt_template_ids: list[str] = Field(default_factory=list, description="可选的系统提示词模板ID列表")
    model_config_ids: list[str] = Field(default_factory=list, description="可选的模型配置ID列表")
    enabled_tools: list[str] = Field(default_factory=list, description="工具白名单")
    enabled_skills: list[str] = Field(default_factory=list, description="技能白名单")
    enabled_mcp_servers: dict[str, MCPServerConfigSchema] = Field(
        default_factory=dict, description="MCP 服务白名单"
    )


class NanobotWorkspaceSchema(BaseModel):
    """Workspace 响应体。"""

    id: str = Field(description="工作区ID")
    name: str = Field(description="工作区名称")
    description: str | None = Field(default=None, description="工作区描述")
    prompt_template_ids: list[str] = Field(default_factory=list, description="可选的系统提示词模板ID列表")
    model_config_ids: list[str] = Field(default_factory=list, description="可选的模型配置ID列表")
    enabled_tools: list[str] = Field(default_factory=list, description="工具白名单")
    enabled_skills: list[str] = Field(default_factory=list, description="技能白名单")
    enabled_mcp_servers: dict[str, MCPServerConfigSchema] = Field(
        default_factory=dict, description="MCP 服务白名单"
    )
    created_at: datetime = Field(description="创建时间")
    updated_at: datetime = Field(description="更新时间")

    @classmethod
    def from_doc(cls, doc: "NanobotWorkspaceModel") -> "NanobotWorkspaceSchema":
        return cls(
            id=doc.id,
            name=doc.name,
            description=doc.description,
            prompt_template_ids=list(doc.prompt_template_ids),
            model_config_ids=list(doc.model_config_ids),
            enabled_tools=list(doc.enabled_tools),
            enabled_skills=list(doc.enabled_skills),
            enabled_mcp_servers={
                name: MCPServerConfigSchema.model_validate(payload)
                for name, payload in (doc.enabled_mcp_servers or {}).items()
            },
            created_at=doc.created_at,
            updated_at=doc.updated_at,
        )


class NanobotWorkspaceListItemSchema(BaseModel):
    """工作区名称列表项（给下拉选择使用）。"""

    id: str = Field(description="工作区ID")
    name: str = Field(description="工作区名称")


class WorkspaceServiceError(Exception):
    """WorkspaceService 统一业务异常，携带 HTTP 状态码与消息。"""

    def __init__(self, code: int, message: str, data: Any | None = None) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.data = data
