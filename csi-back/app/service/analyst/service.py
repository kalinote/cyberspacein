"""AnalystService：/agent/start / /agent/status(SSE) / /agent/approve 的业务编排中枢。

职责（MIGRATION_PLAN §3.1.3）：
1. 按 `agent_id` 从 Mongo 拉取 `NanobotAgentModel` + 其所属 `NanobotWorkspaceModel`
   + 绑定的 `AgentModelConfigModel` / `AgentPromptTemplateModel`，组装一个
   per-request 的 `Nanobot` 实例（`build_bot`）。
2. 在后台 `asyncio.Task` 中执行 `bot.run(user_prompt, session_id=...)`（`run_analysis`）；
   通过 `ContextVar(current_agent_id / current_session_id)` 让业务工具和 hooks（TODO #20）
   能访问上下文。
3. 统一管理 SSE 订阅（`subscribe` / `unsubscribe` / `broadcast_sse`）和 HITL 审批队列
   （`submit_approval` / `await_approval`）。
4. 在 run 开始 / 结束 / 异常时把业务状态写回 `NanobotAgentModel`（`status / current_session_id
   / steps / todos / pending_approval / result`）。

故意留到后续 TODO 的扩展点：
- 业务 Hooks（StatusHook / TodosHook / ApprovalHook / ResultHook）→ TODO #20
- 业务工具（get_entity / modify_entity / notify_user / write_todos）→ TODO #20
- `ResultPayloadSchema` + `response_format=json_schema` → TODO #21

这些点都通过显式注释 `TODO(#20)` / `TODO(#21)` 标注在对应位置。
"""
from __future__ import annotations

import asyncio
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Any

from loguru import logger

from app.models.agent.configs import AgentModelConfigModel, AgentPromptTemplateModel
from app.models.agent.nanobot import NanobotAgentModel, NanobotWorkspaceModel
from app.schemas.agent.nanobot_agent import AgentServiceError
from app.schemas.agent.result import (
    RESULT_FORMAT_INSTRUCTION,
    build_response_format_schema,
    parse_run_result,
)
from app.schemas.constants import NanobotAgentStatusEnum
from app.service.analyst.context import current_agent_id, current_session_id
from app.service.analyst.hooks import default_analyst_hooks
from app.service.analyst.tools import build_business_tools
from app.service.nanobot import Nanobot
from app.service.nanobot.config.schema import DreamConfig
from app.service.nanobot.providers.openai_compat_provider import OpenAICompatProvider
from app.service.nanobot.storage import MongoMemoryBackend, MongoSessionStore
from app.utils.id_lib import generate_id
import app.utils.status_codes as status_codes

logger = logger.bind(name=__name__)


_SANDBOX_ROOT: Path = Path(tempfile.gettempdir()) / "csi_nanobot"


def _agent_sandbox_dir(workspace_id: str, agent_id: str) -> Path:
    """per-agent 文件系统沙箱目录。

    由于 workspace / fs 工具默认全关（MIGRATION_PLAN §3.2），该目录当前仅作为
    `Nanobot.from_components` 的占位参数；未来 sandbox 上线后再切换到真实路径。
    """
    path = _SANDBOX_ROOT / workspace_id / agent_id
    path.mkdir(parents=True, exist_ok=True)
    return path


class AnalystService:
    """分析引擎业务编排入口（类级别共享状态，不实例化）。"""

    # 运行期的 Nanobot 实例缓存：key=agent_id。仅在 `run_analysis` 期间存活，结束后 pop。
    _bots: dict[str, Nanobot] = {}
    _bots_lock: asyncio.Lock = asyncio.Lock()

    # SSE 订阅者队列，key=agent_id；前端订阅时新建 Queue，取消时移除。
    _sse_subscribers: dict[str, list[asyncio.Queue]] = {}
    _sse_lock: asyncio.Lock = asyncio.Lock()

    # 后台 run_analysis 任务，key=agent_id；用于 cancel / 状态查询。
    _running_tasks: dict[str, asyncio.Task] = {}
    _task_lock: asyncio.Lock = asyncio.Lock()

    # 取消/暂停原因标注，key=agent_id；业务工具可以据此决定落 paused / failed。
    _cancel_reasons: dict[str, str] = {}

    # HITL 决策通道，key=agent_id。modify_entity 工具（TODO #20）在 AWAITING_APPROVAL 时
    # await 该队列，路由层 `/agent/approve` 往该队列 put 决策。
    _pending_resumes: dict[str, asyncio.Queue] = {}
    _resume_lock: asyncio.Lock = asyncio.Lock()

    # 进程级单例：Mongo backend 本身无状态（in-process cache 在 MongoSessionStore
    # 内部），共享后可以跨多个 AnalystService 调用复用 session 缓存。
    _memory_backend: MongoMemoryBackend | None = None
    _session_store: MongoSessionStore | None = None

    # ------------------------------------------------------------------
    # 基础组件获取（懒加载 + 进程级单例）
    # ------------------------------------------------------------------

    @classmethod
    def _get_memory_backend(cls) -> MongoMemoryBackend:
        if cls._memory_backend is None:
            cls._memory_backend = MongoMemoryBackend()
        return cls._memory_backend

    @classmethod
    def _get_session_store(cls) -> MongoSessionStore:
        if cls._session_store is None:
            cls._session_store = MongoSessionStore()
        return cls._session_store

    # ------------------------------------------------------------------
    # SSE：订阅 / 取消 / 广播
    # ------------------------------------------------------------------

    @classmethod
    async def subscribe(cls, agent_id: str) -> asyncio.Queue:
        """前端订阅 agent 的事件流；返回一个 per-subscriber 的 Queue。"""
        queue: asyncio.Queue = asyncio.Queue()
        async with cls._sse_lock:
            cls._sse_subscribers.setdefault(agent_id, []).append(queue)
        return queue

    @classmethod
    async def unsubscribe(cls, agent_id: str, queue: asyncio.Queue) -> None:
        async with cls._sse_lock:
            subs = cls._sse_subscribers.get(agent_id)
            if not subs:
                return
            try:
                subs.remove(queue)
            except ValueError:
                pass
            if not subs:
                cls._sse_subscribers.pop(agent_id, None)

    @classmethod
    async def broadcast_sse(cls, agent_id: str, event: str, data: Any) -> None:
        """把一条事件广播给所有订阅了该 agent 的 SSE 队列。"""
        payload = {"event": event, "data": data}
        async with cls._sse_lock:
            subs = list(cls._sse_subscribers.get(agent_id, []))
        for queue in subs:
            try:
                queue.put_nowait(payload)
            except asyncio.QueueFull:
                logger.warning(
                    f"SSE 队列已满丢弃事件: agent={agent_id} event={event}"
                )

    # ------------------------------------------------------------------
    # HITL 审批：决策队列
    # ------------------------------------------------------------------

    @classmethod
    async def _get_or_create_resume_queue(cls, agent_id: str) -> asyncio.Queue:
        async with cls._resume_lock:
            queue = cls._pending_resumes.get(agent_id)
            if queue is None:
                queue = asyncio.Queue()
                cls._pending_resumes[agent_id] = queue
            return queue

    @classmethod
    async def submit_approval(cls, agent_id: str, decisions: list[dict]) -> None:
        """路由层 `/agent/approve` 调用：把 decisions 放进 agent 的决策队列。

        如果 agent 当前不在 AWAITING_APPROVAL 状态，依然接受写入（幂等），但会 log 告警，
        避免因为 agent 已经推进到下一步而丢失决策。业务工具消费 queue 时会自行校验。
        """
        doc = await NanobotAgentModel.find_one({"_id": agent_id})
        if doc is None:
            raise AgentServiceError(
                status_codes.NOT_FOUND_AGENT, f"Agent 不存在: {agent_id}"
            )
        if doc.status != NanobotAgentStatusEnum.AWAITING_APPROVAL:
            logger.warning(
                f"/approve 写入时 agent 非 AWAITING_APPROVAL 状态: "
                f"agent_id={agent_id} status={doc.status}"
            )
        queue = await cls._get_or_create_resume_queue(agent_id)
        await queue.put({"decisions": decisions, "submitted_at": datetime.now()})

    @classmethod
    async def await_approval(cls, agent_id: str) -> dict:
        """业务工具（TODO #20 的 modify_entity）调用：阻塞等待决策到达。"""
        queue = await cls._get_or_create_resume_queue(agent_id)
        return await queue.get()

    # ------------------------------------------------------------------
    # build_bot：拉配置 + 构造 provider + Nanobot
    # ------------------------------------------------------------------

    @classmethod
    async def build_bot(
        cls,
        agent: NanobotAgentModel,
        workspace: NanobotWorkspaceModel,
    ) -> tuple[Nanobot, str]:
        """构造本次 /start 的 Nanobot，并分配新的 session_id。

        步骤：
        1) 按 `agent.model_config_id` / `agent.prompt_template_id` 拉模型配置与提示词模板；
        2) 构造 provider（`OpenAICompatProvider`，后续支持 anthropic 时再按 spec 派发）；
        3) 生成新 session_id，重置 agent 运行时状态到「准备运行」快照；
        4) `Nanobot.from_components(...)` 装配出 bot。

        注意：
        - 本方法不写入 `status=RUNNING`，留给 `start_agent` 把 task 正式拉起后统一写。
        - Hooks / 业务工具在 TODO #20 中通过 `bot.loop.tools.register(...)` / `bot.loop._extra_hooks`
          注入；本方法只预留 `bot` 给调用方。
        """
        model_cfg = await AgentModelConfigModel.find_one({"_id": agent.model_config_id})
        if model_cfg is None:
            raise AgentServiceError(
                status_codes.NOT_FOUND_MODEL_CONFIG,
                f"Agent 绑定的模型配置不存在: {agent.model_config_id}",
            )

        prompt_tpl = await AgentPromptTemplateModel.find_one(
            {"_id": agent.prompt_template_id}
        )
        if prompt_tpl is None:
            raise AgentServiceError(
                status_codes.NOT_FOUND_TEMPLATE,
                f"Agent 绑定的提示词模板不存在: {agent.prompt_template_id}",
            )

        provider = OpenAICompatProvider(
            api_key=model_cfg.api_key,
            api_base=model_cfg.base_url,
            default_model=model_cfg.model,
            response_format=build_response_format_schema(),
        )

        # 按 agent.mcp_servers 从 workspace.enabled_mcp_servers 里挑子集作为本次可用的 MCP
        mcp_subset: dict[str, dict] = {}
        for server_name in agent.mcp_servers:
            if server_name in (workspace.enabled_mcp_servers or {}):
                mcp_subset[server_name] = workspace.enabled_mcp_servers[server_name]

        session_id = generate_id(f"session:{agent.id}:{datetime.now().isoformat()}")

        # 重置 agent 运行时状态：/start 是一次全新回合，清掉旧 steps/todos/pending/result。
        agent.current_session_id = session_id
        agent.steps = []
        agent.todos = []
        agent.pending_approval = None
        agent.result = None
        agent.updated_at = datetime.now()
        await agent.save()

        bot = Nanobot.from_components(
            agent_id=agent.id,
            workspace_id=agent.workspace_id,
            provider=provider,
            memory_backend=cls._get_memory_backend(),
            session_store=cls._get_session_store(),
            workspace=_agent_sandbox_dir(agent.workspace_id, agent.id),
            model=model_cfg.model,
            dream_config=DreamConfig(),
            mcp_servers=mcp_subset or None,
            hooks=default_analyst_hooks(),
            # TODO(#21): response_format: json_schema 需要在这里通过 provider 扩展传入
        )

        # 业务工具按 agent.tools 白名单注册（未启用任何业务工具时跳过，保留 AgentLoop 的内置工具）
        for tool in build_business_tools(agent.tools):
            bot.loop.tools.register(tool)

        # system prompt 末尾 = AgentPromptTemplateModel.system_prompt + 结构化结果格式要求
        # （即便 provider 支持 response_format: json_schema，也保留 prompt 层约束作为双保险，
        # 以兼容不支持严格 JSON schema 的兼容 provider。）
        system_suffix_parts: list[str] = []
        if prompt_tpl.system_prompt and prompt_tpl.system_prompt.strip():
            system_suffix_parts.append(prompt_tpl.system_prompt.strip())
        system_suffix_parts.append(RESULT_FORMAT_INSTRUCTION)
        bot.loop.context.extra_system_suffix = "\n\n".join(system_suffix_parts)

        return bot, session_id

    # ------------------------------------------------------------------
    # /agent/start：启动分析任务
    # ------------------------------------------------------------------

    @classmethod
    async def start_agent(
        cls,
        agent_id: str,
        user_prompt: str,
        context: dict[str, Any] | None = None,
    ) -> str:
        """启动 agent 并立即返回 session_id；真正执行在后台 task。"""
        agent = await NanobotAgentModel.find_one({"_id": agent_id})
        if agent is None:
            raise AgentServiceError(
                status_codes.NOT_FOUND_AGENT, f"Agent 不存在: {agent_id}"
            )
        workspace = await NanobotWorkspaceModel.find_one({"_id": agent.workspace_id})
        if workspace is None:
            raise AgentServiceError(
                status_codes.NOT_FOUND_WORKSPACE,
                f"Agent 所属工作区不存在: {agent.workspace_id}",
            )

        # 并发控制：一个 agent 同时只能跑一个 session
        if agent.status in {
            NanobotAgentStatusEnum.RUNNING,
            NanobotAgentStatusEnum.AWAITING_APPROVAL,
        }:
            raise AgentServiceError(
                status_codes.CONFLICT_STATE,
                f"Agent 当前处于 {agent.status.value} 状态，请先等待当前任务结束",
            )
        async with cls._task_lock:
            if agent_id in cls._running_tasks and not cls._running_tasks[agent_id].done():
                raise AgentServiceError(
                    status_codes.CONFLICT_STATE,
                    f"Agent 已有运行中的后台任务，无法重复启动: {agent_id}",
                )

        bot, session_id = await cls.build_bot(agent, workspace)

        # 写入 RUNNING 状态（build_bot 已重置 steps/todos/pending/result）
        agent.status = NanobotAgentStatusEnum.RUNNING
        agent.updated_at = datetime.now()
        await agent.save()

        # 清理 agent 维度的残留审批队列（避免上一轮未消费的决策污染）
        async with cls._resume_lock:
            cls._pending_resumes.pop(agent_id, None)
        cls._cancel_reasons.pop(agent_id, None)

        async with cls._bots_lock:
            cls._bots[agent_id] = bot

        task = asyncio.create_task(
            cls.run_analysis(
                agent_id=agent_id,
                session_id=session_id,
                bot=bot,
                user_prompt=user_prompt,
                context=context or {},
            ),
            name=f"analyst-run:{agent_id}:{session_id}",
        )
        async with cls._task_lock:
            cls._running_tasks[agent_id] = task

        await cls.broadcast_sse(
            agent_id,
            "status",
            {
                "agent_id": agent_id,
                "session_id": session_id,
                "status": NanobotAgentStatusEnum.RUNNING.value,
            },
        )

        logger.info(
            f"启动 agent 成功: agent_id={agent_id} session_id={session_id}"
        )
        return session_id

    # ------------------------------------------------------------------
    # run_analysis：后台执行
    # ------------------------------------------------------------------

    @classmethod
    async def run_analysis(
        cls,
        agent_id: str,
        session_id: str,
        bot: Nanobot,
        user_prompt: str,
        context: dict[str, Any],
    ) -> None:
        """后台任务：设 ContextVar → bot.run → 解析结果 → 写回 agent → 广播 SSE。"""
        token_agent = current_agent_id.set(agent_id)
        token_session = current_session_id.set(session_id)
        final_status = NanobotAgentStatusEnum.COMPLETED
        result_payload: dict | None = None
        error_message: str | None = None
        try:
            run_result = await bot.run(user_prompt, session_id=session_id)
            parsed_result, parsed_ok = parse_run_result(run_result.content)
            result_payload = {
                **parsed_result.model_dump(),
                "parsed": parsed_ok,
                "raw_content": run_result.content,
                "tools_used": list(run_result.tools_used),
            }
            if not parsed_ok:
                logger.warning(
                    f"结果无法解析为 ResultPayloadSchema，已使用兜底摘要: "
                    f"agent_id={agent_id} session_id={session_id}"
                )
        except asyncio.CancelledError:
            final_status = NanobotAgentStatusEnum.FAILED
            error_message = cls._cancel_reasons.get(agent_id) or "任务被取消"
            if cls._cancel_reasons.get(agent_id) == "pause":
                final_status = NanobotAgentStatusEnum.PAUSED
            logger.info(
                f"agent 任务取消: agent_id={agent_id} session_id={session_id} "
                f"reason={error_message}"
            )
            raise
        except Exception as exc:  # noqa: BLE001 - 顶层兜底
            final_status = NanobotAgentStatusEnum.FAILED
            error_message = str(exc)
            logger.exception(
                f"agent 任务执行异常: agent_id={agent_id} session_id={session_id}"
            )
        finally:
            try:
                doc = await NanobotAgentModel.find_one({"_id": agent_id})
                if doc is not None:
                    doc.status = final_status
                    doc.result = result_payload or {"error": error_message}
                    doc.pending_approval = None
                    doc.updated_at = datetime.now()
                    await doc.save()
                await cls.broadcast_sse(
                    agent_id,
                    "result",
                    {
                        "agent_id": agent_id,
                        "session_id": session_id,
                        "status": final_status.value,
                        "result": result_payload,
                        "error": error_message,
                    },
                )
            finally:
                try:
                    await bot.close()
                except Exception:
                    logger.exception(f"关闭 bot 资源异常: agent_id={agent_id}")

                async with cls._bots_lock:
                    cls._bots.pop(agent_id, None)
                async with cls._task_lock:
                    cls._running_tasks.pop(agent_id, None)
                async with cls._resume_lock:
                    cls._pending_resumes.pop(agent_id, None)
                cls._cancel_reasons.pop(agent_id, None)

                current_session_id.reset(token_session)
                current_agent_id.reset(token_agent)

    # ------------------------------------------------------------------
    # 取消 / 暂停
    # ------------------------------------------------------------------

    @classmethod
    async def cancel_agent(cls, agent_id: str, *, reason: str = "cancel") -> bool:
        """请求取消后台任务；真正的状态落地由 `run_analysis.finally` 完成。"""
        async with cls._task_lock:
            task = cls._running_tasks.get(agent_id)
        if task is None or task.done():
            return False
        cls._cancel_reasons[agent_id] = reason
        task.cancel()
        return True
