"""Nanobot 面向业务层的装配入口。

与老版本的差异：

- 删除了 `from_config` / `_make_provider`：这两者依赖文件系统下的 `config.json`
  与 `Config` schema，整套老式"Workspace 即目录"的假设在新架构下不再成立。
- 新增 `from_components(...)`：按业务层已经就位的"组件"（LLMProvider、
  MemoryBackend、SessionStore、workspace 沙箱路径等）装配一个 `Nanobot`。
  通常由 `AnalystService.build_bot(agent_id)`（TODO #19）调用，调用方负责：
    * 按 `agent_id` / `workspace_id` 查询 Workspace/Agent 配置；
    * 根据 Agent 绑定的 `AgentModelConfigModel` 构建 `LLMProvider`；
    * 提供 Mongo 实现的 `MemoryBackend` / `SessionStore`；
    * 提供 per-agent 文件沙箱目录（用于文件系统类工具）。
- `Nanobot.run(...)` 的 `session_key` 参数重命名为 `session_id`，None 时
  `AgentLoop.process_direct` 会按稳定规则派生一个默认会话 id。
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any

from app.service.nanobot.agent.hook import AgentHook
from app.service.nanobot.agent.loop import AgentLoop
from app.service.nanobot.agent.memory import MemoryStore
from app.service.nanobot.bus.queue import MessageBus
from app.service.nanobot.session.manager import SessionManager

if TYPE_CHECKING:
    from app.service.nanobot.config.schema import (
        DreamConfig,
        ExecToolConfig,
        ToolsConfig,
        WebToolsConfig,
    )
    from app.service.nanobot.providers.base import LLMProvider
    from app.service.nanobot.storage.base import MemoryBackend, SessionStore


@dataclass(slots=True)
class RunResult:
    """单次 agent 运行结果"""

    content: str
    tools_used: list[str]
    messages: list[dict[str, Any]]


class Nanobot:
    """Nanobot 的业务 façade。

    典型使用（由 AnalystService 内部完成）::

        bot = Nanobot.from_components(
            agent_id=agent.id,
            workspace_id=workspace.id,
            provider=provider,
            memory_backend=mongo_memory_backend,
            session_store=mongo_session_store,
            workspace=agent_sandbox_path,
            model=agent.model_override,
            dream_config=workspace.dream_config,
            ...
        )
        result = await bot.run("请分析最近一周的日志", session_id=session.id)
    """

    def __init__(self, loop: AgentLoop) -> None:
        self._loop = loop

    # ------------------------------------------------------------------
    # 装配入口
    # ------------------------------------------------------------------

    @classmethod
    def from_components(
        cls,
        *,
        agent_id: str,
        workspace_id: str,
        provider: LLMProvider,
        memory_backend: MemoryBackend,
        session_store: SessionStore,
        workspace: Path,
        model: str | None = None,
        dream_config: DreamConfig | None = None,
        tools_config: ToolsConfig | None = None,
        web_config: WebToolsConfig | None = None,
        exec_config: ExecToolConfig | None = None,
        mcp_servers: dict | None = None,
        max_iterations: int | None = None,
        context_window_tokens: int | None = None,
        context_block_limit: int | None = None,
        max_tool_result_chars: int | None = None,
        provider_retry_mode: str = "standard",
        restrict_to_workspace: bool = False,
        timezone: str | None = None,
        disabled_skills: list[str] | None = None,
        send_progress: bool = True,
        send_tool_hints: bool = False,
        hooks: list[AgentHook] | None = None,
    ) -> "Nanobot":
        """按已构建好的组件装配 Nanobot。

        - `agent_id` / `workspace_id`：AgentLoop 的身份绑定。
        - `provider`：外部已构建好的 LLMProvider 实例。
        - `memory_backend`：workspace 级长期记忆后端（通常是 `MongoMemoryBackend`）。
        - `session_store`：会话存储后端（通常是 `MongoSessionStore`）。
        - `workspace`：per-agent 文件系统沙箱目录（`ReadFileTool` / `ExecTool` 等工具的根）。
          与 Mongo 持久化互相独立，删除/重建不影响记忆与会话。
        """
        memory = MemoryStore(backend=memory_backend, workspace_id=workspace_id)
        sessions = SessionManager(store=session_store)
        # MessageBus 暂时保留：AgentLoop._process_message 还需要 bus.publish_outbound
        # 来发 progress / retry_wait / stream 事件。后续若改成直接走 hooks
        # (TODO #20) 可同步移除。
        bus = MessageBus()
        loop = AgentLoop(
            bus=bus,
            provider=provider,
            memory=memory,
            sessions=sessions,
            agent_id=agent_id,
            workspace=workspace,
            model=model,
            max_iterations=max_iterations,
            context_window_tokens=context_window_tokens,
            context_block_limit=context_block_limit,
            max_tool_result_chars=max_tool_result_chars,
            provider_retry_mode=provider_retry_mode,
            web_config=web_config,
            exec_config=exec_config,
            restrict_to_workspace=restrict_to_workspace,
            mcp_servers=mcp_servers,
            send_progress=send_progress,
            send_tool_hints=send_tool_hints,
            timezone=timezone,
            hooks=hooks,
            disabled_skills=disabled_skills,
            tools_config=tools_config,
            dream_config=dream_config,
        )
        return cls(loop)

    # ------------------------------------------------------------------
    # 暴露给业务层的属性
    # ------------------------------------------------------------------

    @property
    def loop(self) -> AgentLoop:
        """暴露底层 AgentLoop，供 AnalystService 做 hook 注入、状态查询等"""
        return self._loop

    @property
    def agent_id(self) -> str:
        return self._loop.agent_id

    @property
    def workspace_id(self) -> str:
        return self._loop.workspace_id

    # ------------------------------------------------------------------
    # 单次调用
    # ------------------------------------------------------------------

    async def run(
        self,
        message: str,
        *,
        session_id: str | None = None,
        hooks: list[AgentHook] | None = None,
    ) -> RunResult:
        """跑一次 agent，返回结果。

        - `session_id`：会话标识；None 时由 AgentLoop 按 channel/chat_id 派生一个稳定 id。
        - `hooks`：可选，本次运行的额外 hooks（原 extra_hooks 会在运行后恢复）。
        """
        prev = self._loop._extra_hooks
        if hooks is not None:
            self._loop._extra_hooks = list(hooks)
        try:
            response = await self._loop.process_direct(
                message, session_id=session_id,
            )
        finally:
            self._loop._extra_hooks = prev

        content = (response.content if response else None) or ""
        return RunResult(content=content, tools_used=[], messages=[])

    async def close(self) -> None:
        """清理底层资源：drain 后台任务 + 关闭 MCP 连接"""
        await self._loop.close_mcp()
