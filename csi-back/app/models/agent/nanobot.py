from datetime import datetime
from typing import Any

from beanie import Document
from pydantic import Field
from pymongo import ASCENDING, DESCENDING, IndexModel

from app.schemas.constants import (
    NanobotMemoryDocTypeEnum,
    NanobotMessageRoleEnum,
    NanobotLLMProviderEnum,
    NanobotSessionStatusEnum,
    ReasoningEffortEnum,
)


class NanobotWorkspaceModel(Document):
    """工作区：最基本的业务域，绑定候选资源池与白名单

    同一 workspace 下的所有 Agent 共享 MEMORY / history / cursor（按 workspace_id 隔离）。
    """
    id: str = Field(alias="_id", description="工作区ID")
    name: str = Field(description="工作区名称")
    description: str | None = Field(default=None, description="工作区描述")

    prompt_template_ids: list[str] = Field(default_factory=list, description="可选系统提示词模板ID列表，Agent 只能从中选择一个")
    model_config_ids: list[str] = Field(default_factory=list, description="可选模型提供商配置ID列表，Agent 只能从中选择一个")
    enabled_tools: list[str] = Field(default_factory=list, description="工具白名单，Agent 可用工具必须是该列表的子集")
    enabled_skills: list[str] = Field(default_factory=list, description="技能白名单，Agent 可用技能必须是该列表的子集")
    enabled_mcp_servers: dict[str, dict] = Field(default_factory=dict, description="MCP 服务白名单，key=server_name，value=MCPServerConfig dump")

    created_at: datetime = Field(default_factory=datetime.now, description="创建时间")
    updated_at: datetime = Field(default_factory=datetime.now, description="更新时间")

    class Settings:
        name = "nanobot_workspaces"
        indexes = [
            "name",
            "created_at",
            "updated_at",
        ]


class NanobotAgentModel(Document):
    """Agent：归属于 Workspace；仅持久化配置，运行时状态在 nanobot_sessions。"""
    id: str = Field(alias="_id", description="AgentID")
    workspace_id: str = Field(description="所属工作区ID")

    name: str = Field(description="Agent名称")
    description: str | None = Field(default=None, description="Agent描述")

    # 选定资源（必须是 workspace 对应字段的子集，服务端在 create/update 时强校验）
    prompt_template_id: str = Field(description="选定的提示词模板ID，必须 ∈ workspace.prompt_template_ids")
    model_config_id: str = Field(description="选定的模型提供商配置ID，必须 ∈ workspace.model_config_ids")
    tools: list[str] = Field(default_factory=list, description="启用的工具列表，⊆ workspace.enabled_tools")
    skills: list[str] = Field(default_factory=list, description="启用的技能列表，⊆ workspace.enabled_skills")
    mcp_servers: list[str] = Field(default_factory=list, description="启用的MCP服务名列表，元素 ∈ workspace.enabled_mcp_servers.keys()")
    llm_config: dict[str, Any] = Field(default_factory=dict, description="LLM 生成参数（temperature / max_tokens / reasoning_effort 等）")
    reasoning_effort: ReasoningEffortEnum | None = Field(
        default=None,
        description="推理强度（low/medium/high/xhigh/max；null 表示关闭推理/思考模式）",
    )
    llm_provider: NanobotLLMProviderEnum = Field(default=NanobotLLMProviderEnum.OPENAI_COMPAT, description="LLM 兼容提供商")
    agent_builtin_prompt_ids: list[str] = Field(
        default_factory=list,
        description="绑定的 AGENT 内置提示词文档 ID 列表，按顺序拼入 system prompt；可为空",
    )

    created_at: datetime = Field(default_factory=datetime.now, description="创建时间")
    updated_at: datetime = Field(default_factory=datetime.now, description="更新时间")

    class Settings:
        name = "nanobot_agents"
        indexes = [
            "workspace_id",
            IndexModel([("workspace_id", ASCENDING), ("name", ASCENDING)], unique=True),
            "created_at",
            "updated_at",
        ]


class NanobotSessionModel(Document):
    """会话：每次 /agent/start 一条；承载本轮运行时状态与元数据。"""
    id: str = Field(alias="_id", description="会话ID")
    agent_id: str = Field(description="所属 AgentID")
    workspace_id: str = Field(description="冗余的工作区ID，便于按 workspace 聚合查询")

    metadata: dict = Field(default_factory=dict, description="会话元数据（runtime_checkpoint / pending_user_turn / _last_summary 等）")
    last_consolidated_seq: int = Field(default=0, description="已合并到 history 的消息 seq 上限")

    status: NanobotSessionStatusEnum = Field(
        default=NanobotSessionStatusEnum.IDLE,
        description="本会话运行状态",
    )
    steps: list[dict] = Field(default_factory=list, description="当前运行的步骤流水")
    todos: list[dict] = Field(default_factory=list, description="write_todos 工具产生的待办列表")
    pending_approval: dict | None = Field(default=None, description="待审批载荷（HITL）")
    result: dict | None = Field(default=None, description="最近一次 run_analysis 回合快照")
    task_submissions: list[dict] = Field(
        default_factory=list,
        description="submit_task_result 历史记录（按调用顺序 append）",
    )

    user_prompt: str | None = Field(default=None, description="本轮用户提示词（渲染后）")
    error_message: str | None = Field(default=None, description="失败或取消时的错误说明")
    started_at: datetime | None = Field(default=None, description="进入运行态的时间")
    finished_at: datetime | None = Field(default=None, description="结束时间")

    created_at: datetime = Field(default_factory=datetime.now, description="创建时间")
    updated_at: datetime = Field(default_factory=datetime.now, description="更新时间")

    class Settings:
        name = "nanobot_sessions"
        indexes = [
            IndexModel([("agent_id", ASCENDING), ("created_at", DESCENDING)]),
            IndexModel(
                [("agent_id", ASCENDING), ("status", ASCENDING), ("updated_at", DESCENDING)],
            ),
            "workspace_id",
            "updated_at",
        ]


class NanobotSessionMessagesModel(Document):
    """消息事件流，每个会话多条消息文档 对应原 session/*.jsonl 具体文件"""
    session_id: str = Field(description="会话ID")
    seq: int = Field(description="消息序号，递增")
    role: NanobotMessageRoleEnum = Field(description="消息角色")
    content: Any = Field(description="消息内容，str 或 list[dict]（多模态）")
    created_at: datetime = Field(default_factory=datetime.now, description="创建时间")

    # subagent 后续需要考虑是否优化 sender_id，目前应该不需要多用户支持
    sender_id: str | None = Field(default=None, description="发送者ID，用于区分普通用户和Subagent")
    injected_event: str | None = Field(default=None, description="注入事件")
    subagent_task_id: str | None = Field(default=None, description="子代理任务ID")

    # assistant only
    tool_calls: list[dict] = Field(default_factory=list, description="工具调用列表，当消息role为assistant时，为assistant需要调用的工具列表")
    reasoning_content: str | None = Field(default=None, description="推理内容，一般不需要放到上下文中")

    # anthropic only
    thinking_blocks: list[dict] = Field(default_factory=list, description="思考块列表，当消息role为assistant时，为assistant的思考块列表")

    # tool only
    tool_call_id: str | None = Field(default=None, description="工具调用消息ID，当消息role为tool时，为工具调用实例ID")
    tool_call_name: str | None = Field(default=None, description="工具名称，当消息role为tool时，为工具名称")

    class Settings:
        name = "nanobot_session_messages"
        indexes = [
            IndexModel([("session_id", ASCENDING), ("seq", ASCENDING)], unique=True),
            "created_at",
        ]


class NanobotMemoryDocsModel(Document):
    """长期记忆和内置系统提示词文档 对应原 memory/MEMORY.md / SOUL.md / USER.md 等文件"""
    workspace_id: str = Field(description="工作区ID")
    type: NanobotMemoryDocTypeEnum = Field(description="记忆类型")
    name: str = Field(description="记忆名称")
    description: str | None = Field(default=None, description="记忆描述")
    content: str = Field(description="记忆内容")
    created_at: datetime = Field(default_factory=datetime.now, description="创建时间")
    updated_at: datetime = Field(default_factory=datetime.now, description="更新时间")

    class Settings:
        name = "nanobot_memory_docs"
        indexes = [
            IndexModel([("workspace_id", ASCENDING), ("type", ASCENDING)]),
            IndexModel(
                [("workspace_id", ASCENDING), ("type", ASCENDING), ("name", ASCENDING)],
                unique=True,
            ),
            "created_at",
            "updated_at",
        ]


class NanobotHistoryModel(Document):
    """历史条目 对应原 memory/history.jsonl 文件，append-only"""
    workspace_id: str = Field(description="工作区ID")
    cursor: int = Field(description="游标，单调递增")
    content: str = Field(description="历史条目内容")
    created_at: datetime = Field(default_factory=datetime.now, description="创建时间")

    class Settings:
        name = "nanobot_history"
        indexes = [
            IndexModel([("workspace_id", ASCENDING), ("cursor", ASCENDING)], unique=True),
            "created_at",
        ]


class NanobotHistoryStateModel(Document):
    """历史游标状态 对应原 .cursor / .dream_cursor 文件"""
    id: str = Field(alias="_id", description="工作区ID")
    last_cursor: int = Field(default=0, description="已分配的最大 cursor")
    last_dream_cursor: int = Field(default=0, description="Dream 已处理到的 cursor")
    updated_at: datetime = Field(default_factory=datetime.now, description="更新时间")

    class Settings:
        name = "nanobot_history_state"
        indexes = [
            "updated_at",
        ]
