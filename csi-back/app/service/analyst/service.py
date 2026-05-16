"""AnalystService：/agent/start / /agent/status(SSE) / /agent/approve 的业务编排中枢。

职责（MIGRATION_PLAN §3.1.3）：
1. 按 `agent_id` 从 Mongo 拉取 `NanobotAgentModel` + 其所属 `NanobotWorkspaceModel`
   + 绑定的 `AgentModelConfigModel` / `AgentPromptTemplateModel`，组装一个
   per-request 的 `Nanobot` 实例（`build_bot`）。
2. 在后台 `asyncio.Task` 中执行 `bot.run(user_prompt, session_id=...)`（`run_analysis`）；
   通过 `ContextVar(current_agent_id / current_session_id)` 让业务工具和 hooks（TODO #20）
   能访问上下文。
3. 统一管理 SSE 订阅（`subscribe` / `unsubscribe` / `broadcast_sse`）；HITL 见 `hitl.py`
   （`submit_approval` 为 API 薄委托）。
4. 在 run 开始 / 结束 / 异常时把业务状态写回 `NanobotSessionModel`（`status / steps / todos /
   pending_approval / result` 等）。

故意留到后续 TODO 的扩展点：
- 业务 Hooks（StatusHook / TodosHook / ApprovalHook / ResultHook）→ TODO #20
- 业务工具（get_entity / modify_entity / notify_user / write_todos）→ TODO #20
- 终局机读结果由工具 `submit_task_result` 写入 ContextVar，`run_analysis` 组装 SSE/DB。

这些点都通过显式注释 `TODO(#20)` 等标注在对应位置。
"""
from __future__ import annotations

import asyncio
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Any

from loguru import logger
from pymongo import ReturnDocument

from app.core.config import settings
from app.models.agent.configs import AgentModelConfigModel, AgentPromptTemplateModel
from app.models.agent.nanobot import (
    NanobotAgentModel,
    NanobotSessionModel,
    NanobotWorkspaceModel,
)
from app.models.agent.sse_event import (
    NanobotAgentSseEventModel,
    NanobotAgentSseEventStateModel,
)
from app.schemas.agent.nanobot_agent import AgentServiceError
from app.schemas.agent.result import TASK_COMPLETION_INSTRUCTION
from app.schemas.constants import NanobotSessionStatusEnum
from app.utils import status_codes
from app.service.analyst.context import (
    current_agent_id,
    current_session_id,
    current_task_completion,
    get_current_task_completion,
)
from app.service.analyst.hooks import default_analyst_hooks
from app.service.analyst.tools import SubmitTaskResultTool, build_business_tools
from app.service.nanobot import Nanobot
from app.service.nanobot.config.schema import DreamConfig
from app.service.nanobot.providers.openai_compat_provider import OpenAICompatProvider
from app.service.nanobot.storage import MongoMemoryBackend, MongoSessionStore
from app.utils.id_lib import generate_id

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

    # 运行期的 Nanobot 实例缓存：key=session_id。仅在 `run_analysis` 期间存活，结束后 pop。
    _bots: dict[str, Nanobot] = {}
    _bots_lock: asyncio.Lock = asyncio.Lock()

    # SSE 订阅者队列，key=(agent_id, session_id)；前端订阅时新建 Queue，取消时移除。
    _sse_subscribers: dict[tuple[str, str], list[asyncio.Queue]] = {}
    _sse_lock: asyncio.Lock = asyncio.Lock()

    # SSE 历史持久化：stream 合并缓冲（用于回放，避免逐字 delta 落库）
    # key=(agent_id, session_id) -> {"delta": str, "last_flush_at": datetime, "created_at": datetime}
    _sse_stream_buffers: dict[tuple[str, str], dict[str, Any]] = {}
    _sse_persist_lock: asyncio.Lock = asyncio.Lock()

    # 后台 run_analysis 任务，key=session_id；用于 cancel / 状态查询。
    _running_tasks: dict[str, asyncio.Task] = {}
    _task_lock: asyncio.Lock = asyncio.Lock()

    # 取消/暂停原因标注，key=session_id；业务工具可以据此决定落 paused / failed。
    _cancel_reasons: dict[str, str] = {}

    # 进程级单例：Mongo backend 本身无状态（in-process cache 在 MongoSessionStore
    # 内部），共享后可以跨多个 AnalystService 调用复用 session 缓存。
    _memory_backend: MongoMemoryBackend | None = None
    _session_store: MongoSessionStore | None = None

    # stream 合并阈值（用于回放落库；实时 SSE 仍按原样逐条广播）
    _SSE_STREAM_FLUSH_MAX_CHARS: int = 2048
    _SSE_STREAM_FLUSH_MAX_MS: int = 200

    # ------------------------------------------------------------------
    # 基础组件获取（懒加载 + 进程级单例）
    # ------------------------------------------------------------------

    @classmethod
    def _build_sse_state_id(cls, agent_id: str, session_id: str) -> str:
        return f"{agent_id}:{session_id}"

    @classmethod
    async def _alloc_sse_seq(cls, agent_id: str, session_id: str) -> int:
        """为 (agent_id, session_id) 原子分配递增 seq。"""
        now = datetime.now()
        collection = NanobotAgentSseEventStateModel.get_pymongo_collection()
        updated = await collection.find_one_and_update(
            {"_id": cls._build_sse_state_id(agent_id, session_id)},
            {
                "$inc": {"last_seq": 1},
                "$set": {"updated_at": now},
            },
            upsert=True,
            return_document=ReturnDocument.AFTER,
        )
        return int(updated["last_seq"])

    @classmethod
    async def _persist_sse_event(
        cls,
        *,
        agent_id: str,
        session_id: str,
        event: str,
        data: Any,
        is_debug: bool = False,
        compressed: bool = False,
    ) -> None:
        """将 SSE 事件写入事件日志（用于回放）。写失败不应影响主流程。"""
        try:
            seq = await cls._alloc_sse_seq(agent_id, session_id)
            await NanobotAgentSseEventModel(
                agent_id=agent_id,
                session_id=session_id,
                seq=seq,
                event=event,
                data=data,
                is_debug=bool(is_debug),
                compressed=bool(compressed),
                created_at=datetime.now(),
            ).insert()
        except Exception:
            logger.exception(
                f"持久化 SSE 事件失败（已忽略）: agent_id={agent_id} session_id={session_id} event={event}"
            )

    @classmethod
    async def _maybe_persist_stream_delta(cls, agent_id: str, data: Any) -> None:
        """合并 stream delta 后再持久化，避免逐字落库。"""
        if not isinstance(data, dict):
            return
        session_id = str(data.get("session_id") or "").strip()
        delta = data.get("delta")
        if not session_id or not isinstance(delta, str) or delta == "":
            return

        now = datetime.now()
        key = (agent_id, session_id)
        async with cls._sse_persist_lock:
            buf = cls._sse_stream_buffers.get(key)
            if buf is None:
                buf = {"delta": "", "created_at": now, "last_flush_at": now}
                cls._sse_stream_buffers[key] = buf
            buf["delta"] = str(buf.get("delta") or "") + delta

            elapsed_ms = int((now - buf["last_flush_at"]).total_seconds() * 1000)
            if len(buf["delta"]) < cls._SSE_STREAM_FLUSH_MAX_CHARS and elapsed_ms < cls._SSE_STREAM_FLUSH_MAX_MS:
                return

            merged = str(buf.get("delta") or "")
            buf["delta"] = ""
            buf["last_flush_at"] = now

        if merged:
            await cls._persist_sse_event(
                agent_id=agent_id,
                session_id=session_id,
                event="stream",
                data={**data, "delta": merged},
                is_debug=False,
                compressed=True,
            )

    @classmethod
    async def _flush_stream_buffer(cls, agent_id: str, session_id: str) -> None:
        key = (agent_id, session_id)
        async with cls._sse_persist_lock:
            buf = cls._sse_stream_buffers.get(key)
            if not buf:
                return
            merged = str(buf.get("delta") or "")
            buf["delta"] = ""
            buf["last_flush_at"] = datetime.now()
        if merged:
            await cls._persist_sse_event(
                agent_id=agent_id,
                session_id=session_id,
                event="stream",
                data={"agent_id": agent_id, "session_id": session_id, "delta": merged},
                is_debug=False,
                compressed=True,
            )

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
    async def subscribe(
        cls, agent_id: str, session_id: str, *, debug: bool = False
    ) -> asyncio.Queue:
        """前端订阅某次会话的事件流；返回一个 per-subscriber 的 Queue。

        debug=True 时，该订阅者会额外收到更详细的调试事件（仍通过同一 SSE 连接输出）。
        """
        session_id = str(session_id or "").strip()
        if not session_id:
            raise AgentServiceError(
                status_codes.INVALID_ARGUMENT, "订阅 SSE 必须提供 session_id"
            )
        queue: asyncio.Queue = asyncio.Queue()
        setattr(queue, "_csi_debug", bool(debug))
        try:
            await cls._flush_stream_buffer(agent_id, session_id)
            events = (
                await NanobotAgentSseEventModel.find(
                    {"agent_id": agent_id, "session_id": session_id}
                )
                .sort("+seq")
                .to_list()
            )
            for ev in events:
                if ev.is_debug and not bool(debug):
                    continue
                queue.put_nowait({"event": ev.event, "data": ev.data, "id": ev.seq})
        except Exception:
            logger.exception(
                f"回放 SSE 历史失败（已忽略）: agent_id={agent_id} session_id={session_id}"
            )
        async with cls._sse_lock:
            cls._sse_subscribers.setdefault((agent_id, session_id), []).append(queue)
        return queue

    @classmethod
    async def unsubscribe(
        cls, agent_id: str, session_id: str, queue: asyncio.Queue
    ) -> None:
        session_id = str(session_id or "").strip()
        key = (agent_id, session_id)
        async with cls._sse_lock:
            subs = cls._sse_subscribers.get(key)
            if not subs:
                return
            try:
                subs.remove(queue)
            except ValueError:
                pass
            if not subs:
                cls._sse_subscribers.pop(key, None)

    @classmethod
    async def broadcast_sse(
        cls, agent_id: str, event: str, data: Any, *, persist: bool = True
    ) -> None:
        """把一条事件广播给订阅了该 (agent_id, session_id) 的 SSE 队列。

        persist=False 时仅推送给当前在线订阅者，不写 `nanobot_agent_sse_events`（用于审批
        已决等对「首条已持久化事件」的就地补丁后的实时刷新）。
        """
        payload = {"event": event, "data": data}
        session_key: str | None = None
        if isinstance(data, dict):
            sid = str(data.get("session_id") or "").strip()
            if sid:
                session_key = sid
        if persist:
            if event == "stream":
                await cls._maybe_persist_stream_delta(agent_id, data)
            else:
                if isinstance(data, dict) and data.get("session_id"):
                    await cls._persist_sse_event(
                        agent_id=agent_id,
                        session_id=str(data.get("session_id")),
                        event=event,
                        data=data,
                        is_debug=False,
                        compressed=False,
                    )
        if not session_key:
            logger.warning(
                f"SSE 广播缺少 session_id，已跳过实时推送: agent={agent_id} event={event}"
            )
            return
        async with cls._sse_lock:
            subs = list(cls._sse_subscribers.get((agent_id, session_key), []))
        for queue in subs:
            try:
                queue.put_nowait(payload)
            except asyncio.QueueFull:
                logger.warning(
                    f"SSE 队列已满丢弃事件: agent={agent_id} session={session_key} event={event}"
                )

    @classmethod
    async def broadcast_debug_sse(cls, agent_id: str, event: str, data: Any) -> None:
        """只给 debug 订阅者广播调试事件。"""
        payload = {"event": event, "data": data}
        session_key: str | None = None
        if isinstance(data, dict):
            sid = str(data.get("session_id") or "").strip()
            if sid:
                session_key = sid
        if isinstance(data, dict) and data.get("session_id"):
            await cls._persist_sse_event(
                agent_id=agent_id,
                session_id=str(data.get("session_id")),
                event=event,
                data=data,
                is_debug=True,
                compressed=False,
            )
        if not session_key:
            logger.warning(
                f"SSE debug 广播缺少 session_id，已跳过: agent={agent_id} event={event}"
            )
            return
        async with cls._sse_lock:
            subs = list(cls._sse_subscribers.get((agent_id, session_key), []))
        for queue in subs:
            if not bool(getattr(queue, "_csi_debug", False)):
                continue
            try:
                queue.put_nowait(payload)
            except asyncio.QueueFull:
                logger.warning(
                    f"SSE debug 队列已满丢弃事件: agent={agent_id} session={session_key} event={event}"
                )

    @classmethod
    async def submit_approval(
        cls, agent_id: str, session_id: str, decisions: list[dict]
    ) -> None:
        """路由层 `/agent/approve` 调用，委托 `HitlService.submit_decisions`。"""
        from app.service.analyst.hitl import HitlService

        await HitlService.submit_decisions(agent_id, session_id, decisions)

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
        3) 生成新 session_id，写入 `NanobotSessionModel` 初始运行态；
        4) `Nanobot.from_components(...)` 装配出 bot。

        注意：
        - 本方法不写入会话 `status=RUNNING`，留给 `start_agent` 把 task 正式拉起后统一写。
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
        )

        # 按 agent.mcp_servers 从 workspace.enabled_mcp_servers 里挑子集作为本次可用的 MCP
        mcp_subset: dict[str, dict] = {}
        for server_name in agent.mcp_servers:
            if server_name in (workspace.enabled_mcp_servers or {}):
                mcp_subset[server_name] = workspace.enabled_mcp_servers[server_name]

        session_id = generate_id(f"session:{agent.id}:{datetime.now().isoformat()}")
        now = datetime.now()
        await NanobotSessionModel(
            id=session_id,
            agent_id=agent.id,
            workspace_id=agent.workspace_id,
            metadata={},
            last_consolidated_seq=0,
            status=NanobotSessionStatusEnum.IDLE,
            steps=[],
            todos=[],
            pending_approval=None,
            result=None,
            user_prompt=None,
            error_message=None,
            started_at=None,
            finished_at=None,
            created_at=now,
            updated_at=now,
        ).insert()

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
        )

        # 业务工具按 agent.tools 白名单注册（未启用任何业务工具时跳过，保留 AgentLoop 的内置工具）
        for tool in build_business_tools(agent.tools):
            bot.loop.tools.register(tool)
        bot.loop.tools.register(SubmitTaskResultTool())

        system_suffix_parts: list[str] = []
        if prompt_tpl.system_prompt and prompt_tpl.system_prompt.strip():
            system_suffix_parts.append(prompt_tpl.system_prompt.strip())
        system_suffix_parts.append(TASK_COMPLETION_INSTRUCTION)
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

        max_parallel = settings.NANOBOT_AGENT_MAX_PARALLEL_SESSIONS
        if max_parallel > 0:
            running_n = await NanobotSessionModel.find(
                {
                    "agent_id": agent_id,
                    "status": NanobotSessionStatusEnum.RUNNING.value,
                }
            ).count()
            if running_n >= max_parallel:
                logger.info(
                    "拒绝启动: agent_id={} 已达并行上限 running={} max={}",
                    agent_id,
                    running_n,
                    max_parallel,
                )
                raise AgentServiceError(
                    status_codes.CONFLICT_STATE,
                    f"该 Agent 已有 {running_n} 个运行中的会话，达到并行上限 {max_parallel}，请稍后再试",
                )

        bot, session_id = await cls.build_bot(agent, workspace)

        sess = await NanobotSessionModel.find_one({"_id": session_id})
        if sess is not None:
            now = datetime.now()
            sess.status = NanobotSessionStatusEnum.RUNNING
            sess.user_prompt = user_prompt
            sess.started_at = now
            sess.updated_at = now
            await sess.save()

        from app.service.analyst.hitl import HitlService

        await HitlService.clear_session(session_id)
        cls._cancel_reasons.pop(session_id, None)

        async with cls._bots_lock:
            cls._bots[session_id] = bot

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
            cls._running_tasks[session_id] = task

        await cls.broadcast_sse(
            agent_id,
            "status",
            {
                "agent_id": agent_id,
                "session_id": session_id,
                "status": NanobotSessionStatusEnum.RUNNING.value,
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
        """后台任务：设 ContextVar → bot.run → 解析结果 → 写回会话 → 广播 SSE。"""
        token_completion = current_task_completion.set(None)
        token_agent = current_agent_id.set(agent_id)
        token_session = current_session_id.set(session_id)
        final_session_status = NanobotSessionStatusEnum.COMPLETED
        result_payload: dict | None = None
        error_message: str | None = None
        try:
            # debug：把本轮 prompt 相关信息提前广播（仅 debug 订阅者可见）
            try:
                await bot.loop.context.refresh_memory_snapshot()
                system_prompt = bot.loop.context.build_system_prompt(channel="cli")
                await cls.broadcast_debug_sse(
                    agent_id,
                    "debug_prompt",
                    {
                        "agent_id": agent_id,
                        "session_id": session_id,
                        "model": getattr(bot.loop, "model", None),
                        "system_prompt": system_prompt,
                        "extra_system_suffix": getattr(
                            bot.loop.context, "extra_system_suffix", ""
                        ),
                        "user_prompt": user_prompt,
                        "memory_snapshot": {
                            "memory": bot.loop.context.snapshot.memory,
                            "soul": bot.loop.context.snapshot.soul,
                            "user": bot.loop.context.snapshot.user,
                            "recent_history_count": len(
                                bot.loop.context.snapshot.recent_history or []
                            ),
                        },
                    },
                )
            except Exception:
                logger.exception(
                    f"构造 debug_prompt 失败（已忽略）: agent_id={agent_id} session_id={session_id}"
                )

            # SSE 优化：优先走 loop.process_direct（可开启流式回调）；不支持时回退到 bot.run
            content: str = ""
            tools_used: list[str] = []

            loop = getattr(bot, "loop", None)
            process_direct = getattr(loop, "process_direct", None) if loop is not None else None

            if asyncio.iscoroutinefunction(process_direct):
                async def _on_stream(delta: str) -> None:
                    await cls.broadcast_sse(
                        agent_id,
                        "stream",
                        {"agent_id": agent_id, "session_id": session_id, "delta": delta},
                    )

                async def _on_stream_end(*, resuming: bool = False, **_kw: Any) -> None:
                    # stream_end 到来时把当前缓冲的 stream 合并块先落库（用于回放）
                    await cls._flush_stream_buffer(agent_id, session_id)
                    await cls.broadcast_sse(
                        agent_id,
                        "stream_end",
                        {
                            "agent_id": agent_id,
                            "session_id": session_id,
                            "resuming": bool(resuming),
                        },
                    )

                async def _on_progress(content_: str, *, tool_hint: bool = False) -> None:
                    await cls.broadcast_sse(
                        agent_id,
                        "progress",
                        {
                            "agent_id": agent_id,
                            "session_id": session_id,
                            "content": content_,
                            "tool_hint": bool(tool_hint),
                        },
                    )

                response = await process_direct(
                    user_prompt,
                    session_id=session_id,
                    channel="cli",
                    chat_id="direct",
                    on_progress=_on_progress,
                    on_stream=_on_stream,
                    on_stream_end=_on_stream_end,
                )
                content = (getattr(response, "content", None) if response else None) or ""
                meta = getattr(response, "metadata", None) or {}
                if isinstance(meta, dict):
                    tools_used = list(meta.get("_tools_used") or [])
                    stop_reason_meta = meta.get("_stop_reason")
                else:
                    tools_used = []
                    stop_reason_meta = None
            else:
                run_result = await bot.run(user_prompt, session_id=session_id)
                content = (getattr(run_result, "content", None) if run_result else None) or ""
                tools_used = list(getattr(run_result, "tools_used", []) or [])
                stop_reason_meta = getattr(run_result, "stop_reason", None)

            completion = get_current_task_completion()
            completion_received = completion is not None
            if not completion_received:
                final_session_status = NanobotSessionStatusEnum.FAILED
                error_message = error_message or "未调用 submit_task_result 结束任务"
                result_payload = {
                    "success": False,
                    "failure_reason": error_message,
                    "short_summary": "",
                    "payload": {},
                    "user_markdown": content,
                    "tools_used": tools_used,
                    "stop_reason": stop_reason_meta,
                    "completion_received": False,
                }
            elif completion.get("success"):
                result_payload = {
                    "success": True,
                    "failure_reason": completion.get("failure_reason"),
                    "short_summary": completion.get("short_summary") or "",
                    "payload": completion.get("payload") if isinstance(completion.get("payload"), dict) else {},
                    "user_markdown": content,
                    "tools_used": tools_used,
                    "stop_reason": stop_reason_meta,
                    "completion_received": True,
                }
            else:
                final_session_status = NanobotSessionStatusEnum.FAILED
                error_message = (
                    str(completion.get("failure_reason") or "").strip() or "任务未成功完成"
                )
                result_payload = {
                    "success": False,
                    "failure_reason": error_message,
                    "short_summary": completion.get("short_summary") or "",
                    "payload": completion.get("payload") if isinstance(completion.get("payload"), dict) else {},
                    "user_markdown": content,
                    "tools_used": tools_used,
                    "stop_reason": stop_reason_meta,
                    "completion_received": True,
                }
        except asyncio.CancelledError:
            final_session_status = NanobotSessionStatusEnum.CANCELLED
            error_message = cls._cancel_reasons.get(session_id) or "任务被取消"
            if cls._cancel_reasons.get(session_id) == "pause":
                final_session_status = NanobotSessionStatusEnum.PAUSED
            logger.info(
                f"agent 任务取消: agent_id={agent_id} session_id={session_id} "
                f"reason={error_message}"
            )
            raise
        except Exception as exc:  # noqa: BLE001 - 顶层兜底
            final_session_status = NanobotSessionStatusEnum.FAILED
            error_message = str(exc)
            result_payload = None
            logger.exception(
                f"agent 任务执行异常: agent_id={agent_id} session_id={session_id}"
            )
        finally:
            try:
                sess = await NanobotSessionModel.find_one({"_id": session_id})
                if sess is not None:
                    sess.status = final_session_status
                    sess.result = result_payload or {"error": error_message}
                    sess.pending_approval = None
                    sess.error_message = error_message
                    sess.finished_at = datetime.now()
                    sess.updated_at = datetime.now()
                    await sess.save()
                # run 结束前冲刷一次 stream 缓冲，保证回放不缺尾巴
                await cls._flush_stream_buffer(agent_id, session_id)
                await cls.broadcast_sse(
                    agent_id,
                    "result",
                    {
                        "agent_id": agent_id,
                        "session_id": session_id,
                        "status": final_session_status.value,
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
                    cls._bots.pop(session_id, None)
                async with cls._task_lock:
                    cls._running_tasks.pop(session_id, None)
                from app.service.analyst.hitl import HitlService

                await HitlService.clear_session(session_id)
                cls._cancel_reasons.pop(session_id, None)

                current_session_id.reset(token_session)
                current_agent_id.reset(token_agent)
                current_task_completion.reset(token_completion)

    # ------------------------------------------------------------------
    # 取消 / 暂停
    # ------------------------------------------------------------------

    @classmethod
    async def cancel_agent(
        cls, agent_id: str, session_id: str, *, reason: str = "cancel"
    ) -> bool:
        """请求取消指定会话的后台任务；真正的状态落地由 `run_analysis.finally` 完成。"""
        session_id = str(session_id or "").strip()
        if not session_id:
            return False
        sess = await NanobotSessionModel.find_one({"_id": session_id})
        if sess is None or sess.agent_id != agent_id:
            return False
        async with cls._task_lock:
            task = cls._running_tasks.get(session_id)
        if task is None or task.done():
            return False
        async with cls._bots_lock:
            bot = cls._bots.get(session_id)
        if bot is not None:
            try:
                await bot.loop.subagents.cancel_by_session(session_id)
            except Exception as exc:
                logger.warning(
                    "取消会话时清理子代理失败: session_id={} err={}",
                    session_id,
                    exc,
                )
        cls._cancel_reasons[session_id] = reason
        task.cancel()
        return True

    @staticmethod
    def _parse_run_task_agent_id(task: asyncio.Task, session_id: str) -> str | None:
        name = task.get_name() if hasattr(task, "get_name") else ""
        prefix = "analyst-run:"
        suffix = f":{session_id}"
        if not name.startswith(prefix) or not name.endswith(suffix):
            return None
        agent_id = name[len(prefix) : -len(suffix)]
        return agent_id or None

    @classmethod
    async def _cancel_orphan_run_task(cls, session_id: str) -> None:
        async with cls._task_lock:
            task = cls._running_tasks.get(session_id)
        if task is None or task.done():
            return
        cls._cancel_reasons[session_id] = "shutdown"
        task.cancel()

    @classmethod
    async def shutdown_running_agents(cls, *, timeout: float | None = None) -> None:
        """进程退出时取消所有后台 run_analysis，并在有界时间内等待收尾。"""
        from app.service.analyst.hitl import HitlService

        raw_timeout = (
            settings.NANOBOT_SHUTDOWN_TIMEOUT_S if timeout is None else timeout
        )
        wait_timeout = max(1.0, float(raw_timeout)) if raw_timeout else 1.0

        async with cls._task_lock:
            snapshot = list(cls._running_tasks.items())

        for session_id, task in snapshot:
            if task.done():
                continue
            agent_id: str | None = None
            async with cls._bots_lock:
                bot = cls._bots.get(session_id)
            if bot is not None:
                agent_id = bot.agent_id

            if not agent_id:
                agent_id = cls._parse_run_task_agent_id(task, session_id)

            cancelled = False
            if agent_id:
                cancelled = await cls.cancel_agent(
                    agent_id, session_id, reason="shutdown"
                )
            if not cancelled:
                await cls._cancel_orphan_run_task(session_id)

        async with cls._task_lock:
            pending = [t for t in cls._running_tasks.values() if not t.done()]

        if pending:
            try:
                await asyncio.wait_for(
                    asyncio.gather(*pending, return_exceptions=True),
                    timeout=wait_timeout,
                )
            except asyncio.TimeoutError:
                still_running = sum(1 for t in pending if not t.done())
                logger.warning(
                    "关闭分析引擎超时: 仍有 {} 个任务未完成 (timeout={}s)",
                    still_running,
                    wait_timeout,
                )

        await HitlService.clear_all_sessions()
