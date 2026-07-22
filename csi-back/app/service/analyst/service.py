"""AnalystService：/agent/start / /agent/status(SSE) / /agent/approve 的业务编排中枢。

职责（MIGRATION_PLAN §3.1.3）：
1. `/start` 与 `/message` 只持久化投递 Run，`AnalystRuntimeWorker` 在任意实例原子领取。
2. Worker 按 Agent/Workspace 配置组装 `Nanobot`，并通过 Run 租约与 fencing token 提交终态。
3. MongoDB 保存会话、Run、审批和事件历史，Redis Streams 分发跨实例实时事件。
4. `ContextVar` 向工具与 hooks 传递 agent/session/run/lease 上下文。
"""
from __future__ import annotations

import asyncio
import tempfile
import uuid
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from loguru import logger
from pymongo import ReturnDocument
from pymongo.errors import DuplicateKeyError

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
from app.schemas.agent.runtime_state import NanobotRunDesiredStateEnum
from app.schemas.agent.result import (
    RunAnalysisResultPayloadSchema,
    TASK_SUBMIT_GUIDANCE,
    TaskSubmissionRecordSchema,
)
from app.schemas.constants import AgentStopReasonEnum, NanobotLLMProviderEnum, NanobotSessionStatusEnum
from app.utils import status_codes
from app.service.analyst.context import (
    current_agent_id,
    current_auto_approve_hitl,
    current_initiator_user_id,
    current_run_id,
    current_run_lease_token,
    current_run_worker_id,
    current_session_id,
    current_task_completion,
    get_current_task_completion,
    get_current_run_id,
    get_current_run_lease_token,
)
from app.service.analyst.hooks import default_analyst_hooks
from app.service.analyst.approval_store import AnalystApprovalStore
from app.service.analyst.event_bus import AnalystEventBus, AnalystEventSubscription
from app.service.analyst.runtime_store import (
    AnalystRuntimeCapacityError,
    AnalystRuntimeStore,
)
from app.service.analyst.tools import SubmitTaskResultTool, build_business_tools
from app.service.nanobot import Nanobot
from app.service.nanobot.config.schema import DreamConfig
from app.service.nanobot.providers.anthropic_provider import AnthropicProvider
from app.service.nanobot.providers.base import GenerationSettings, LLMProvider
from app.service.nanobot.providers.openai_compat_provider import OpenAICompatProvider
from app.service.nanobot.agent.prompt_repository import AgentPromptRepository
from app.service.analyst.skill_service import SkillService
from app.service.nanobot.config.schema import AgentDefaults
from app.service.nanobot.storage import MongoMemoryBackend, MongoSessionStore
from app.utils.id_lib import generate_id

logger = logger.bind(name=__name__)

_SANDBOX_ROOT: Path = Path(tempfile.gettempdir()) / "csi_nanobot"


_RUN_FAILURE_STOP_REASONS = frozenset(
    {
        AgentStopReasonEnum.TOOL_ERROR,
        AgentStopReasonEnum.ERROR,
    }
)


@dataclass(frozen=True)
class AnalystRunOutcome:
    """一次 Nanobot 执行产生的会话终态。"""

    status: NanobotSessionStatusEnum
    result: dict[str, Any] | None
    error_message: str | None


def _resolve_run_outcome(
    *,
    content: str,
    tools_used: list[str],
    stop_reason: AgentStopReasonEnum | None,
    completion: dict[str, Any] | None,
) -> tuple[NanobotSessionStatusEnum, dict[str, Any], str | None]:
    """根据运行结束原因与可选 submit 判定会话状态与 result 载荷。"""
    completion_received = completion is not None
    last_submission: TaskSubmissionRecordSchema | None = None
    if completion_received and isinstance(completion, dict):
        try:
            last_submission = TaskSubmissionRecordSchema.model_validate(completion)
        except Exception:
            last_submission = None

    short_summary = ""
    payload: dict[str, Any] = {}
    failure_reason: str | None = None
    if last_submission is not None:
        short_summary = last_submission.short_summary
        payload = dict(last_submission.payload or {})
        failure_reason = last_submission.failure_reason

    error_message: str | None = None
    final_status = NanobotSessionStatusEnum.COMPLETED

    if stop_reason in _RUN_FAILURE_STOP_REASONS:
        final_status = NanobotSessionStatusEnum.FAILED
        error_message = (content or "").strip() or f"Agent 运行异常: {stop_reason}"
    elif completion_received and completion is not None and not completion.get("success"):
        final_status = NanobotSessionStatusEnum.FAILED
        error_message = (
            str(completion.get("failure_reason") or "").strip() or "任务未成功完成"
        )
        failure_reason = error_message
    
    result_payload = RunAnalysisResultPayloadSchema(
        success=final_status == NanobotSessionStatusEnum.COMPLETED,
        failure_reason=failure_reason if final_status == NanobotSessionStatusEnum.FAILED else None,
        short_summary=short_summary,
        payload=payload,
        user_markdown=content,
        tools_used=tools_used,
        stop_reason=stop_reason,
        completion_received=completion_received,
        last_submission=last_submission,
    ).model_dump()
    return final_status, result_payload, error_message
    

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

    # 当前 Worker 的本地资源句柄，仅用于进程退出清理；不是运行状态权威来源。
    _bots: dict[str, Nanobot] = {}
    _bots_lock: asyncio.Lock = asyncio.Lock()

    # SSE 订阅者队列，key=(agent_id, session_id)；前端订阅时新建 Queue，取消时移除。
    _sse_subscribers: dict[tuple[str, str], list[asyncio.Queue]] = {}
    _sse_lock: asyncio.Lock = asyncio.Lock()
    _sse_event_subscriptions: dict[asyncio.Queue, AnalystEventSubscription] = {}

    # SSE 历史持久化：stream / reasoning_stream 合并缓冲（用于回放，避免逐字 delta 落库）
    # key=(agent_id, session_id) -> {"delta": str, "last_flush_at": datetime, "created_at": datetime}
    _sse_stream_buffers: dict[tuple[str, str], dict[str, Any]] = {}
    _sse_reasoning_stream_buffers: dict[tuple[str, str], dict[str, Any]] = {}
    _sse_persist_lock: asyncio.Lock = asyncio.Lock()

    # 当前 Worker 的本地执行句柄；跨实例取消以 NanobotRunModel.desired_state 为准。
    _running_tasks: dict[str, asyncio.Task] = {}
    _task_lock: asyncio.Lock = asyncio.Lock()

    # 取消/暂停原因标注，key=session_id；业务工具可以据此决定落 paused / failed。
    _cancel_reasons: dict[str, str] = {}
    _owned_run_leases: dict[str, str] = {}

    # 进程级单例：Mongo backend 本身无状态（in-process cache 在 MongoSessionStore
    # 内部），共享后可以跨多个 AnalystService 调用复用 session 缓存。
    _memory_backend: MongoMemoryBackend | None = None
    _session_store: MongoSessionStore | None = None

    # stream 合并阈值（用于回放落库；实时 SSE 仍按原样逐条广播）
    _SSE_STREAM_FLUSH_MAX_CHARS: int = 2048
    _SSE_STREAM_FLUSH_MAX_MS: int = 200

    _MESSAGE_ALLOWED_STATUSES: frozenset[NanobotSessionStatusEnum] = frozenset(
        {
            NanobotSessionStatusEnum.COMPLETED,
            NanobotSessionStatusEnum.FAILED,
            NanobotSessionStatusEnum.CANCELLED,
        }
    )

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
        collection = NanobotAgentSseEventStateModel.get_motor_collection()
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
        compressed: bool = False,
    ) -> int | None:
        """将 SSE 事件写入事件日志（用于回放）。写失败不应影响主流程。"""
        try:
            seq = await cls._alloc_sse_seq(agent_id, session_id)
            await NanobotAgentSseEventModel(
                agent_id=agent_id,
                session_id=session_id,
                seq=seq,
                event=event,
                data=data,
                compressed=bool(compressed),
                created_at=datetime.now(),
            ).insert()
            return seq
        except Exception:
            logger.exception(
                f"持久化 SSE 事件失败（已忽略）: agent_id={agent_id} session_id={session_id} event={event}"
            )
            return None

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
                compressed=True,
            )

    @classmethod
    async def _maybe_persist_reasoning_stream_delta(cls, agent_id: str, data: Any) -> None:
        """合并 reasoning_stream delta 后再持久化，避免逐字落库。"""
        if not isinstance(data, dict):
            return
        session_id = str(data.get("session_id") or "").strip()
        delta = data.get("delta")
        if not session_id or not isinstance(delta, str) or delta == "":
            return

        now = datetime.now()
        key = (agent_id, session_id)
        async with cls._sse_persist_lock:
            buf = cls._sse_reasoning_stream_buffers.get(key)
            if buf is None:
                buf = {"delta": "", "created_at": now, "last_flush_at": now}
                cls._sse_reasoning_stream_buffers[key] = buf
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
                event="reasoning_stream",
                data={**data, "delta": merged},
                compressed=True,
            )

    @classmethod
    async def _flush_reasoning_stream_buffer(cls, agent_id: str, session_id: str) -> None:
        key = (agent_id, session_id)
        async with cls._sse_persist_lock:
            buf = cls._sse_reasoning_stream_buffers.get(key)
            if not buf:
                return
            merged = str(buf.get("delta") or "")
            buf["delta"] = ""
            buf["last_flush_at"] = datetime.now()
        if merged:
            await cls._persist_sse_event(
                agent_id=agent_id,
                session_id=session_id,
                event="reasoning_stream",
                data={"agent_id": agent_id, "session_id": session_id, "delta": merged},
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

    @staticmethod
    def _slice_replay_events(
        events: list[Any], *, limit: int | None, offset: int
    ) -> list[Any]:
        n = len(events)
        if offset == 0 and limit is None:
            return events
        if limit is None:
            return events[: max(0, n - offset)]
        start = max(0, n - offset - limit)
        end = max(0, n - offset)
        return events[start:end]

    @classmethod
    async def _load_replay_events(
        cls,
        agent_id: str,
        session_id: str,
        *,
        limit: int | None = None,
        offset: int = 0,
    ) -> list[NanobotAgentSseEventModel]:
        filt = {"agent_id": agent_id, "session_id": session_id}
        if offset == 0 and limit is None:
            return await NanobotAgentSseEventModel.find(filt).sort("+seq").to_list()

        total = await NanobotAgentSseEventModel.find(filt).count()
        if limit is None:
            take = max(0, total - offset)
            if take == 0:
                return []
            return await NanobotAgentSseEventModel.find(filt).sort("+seq").limit(take).to_list()

        skip = max(0, total - offset - limit)
        take = max(0, min(limit, total - offset))
        if take == 0:
            return []
        return (
            await NanobotAgentSseEventModel.find(filt)
            .sort("+seq")
            .skip(skip)
            .limit(take)
            .to_list()
        )

    @classmethod
    async def _latest_persisted_sse_seq(
        cls,
        agent_id: str,
        session_id: str,
    ) -> int:
        """读取 MongoDB 中该会话已持久化的最大事件序号。"""
        rows = (
            await NanobotAgentSseEventModel.find(
                {"agent_id": agent_id, "session_id": session_id}
            )
            .sort("-seq")
            .limit(1)
            .to_list()
        )
        return int(rows[0].seq or 0) if rows else 0

    @classmethod
    async def _build_session_fallback_replay(
        cls,
        agent_id: str,
        session_id: str,
        *,
        limit: int | None = None,
        offset: int = 0,
    ) -> list[dict[str, Any]]:
        """SSE 事件库为空时，从 NanobotSessionModel 合成可回放事件（如 TTL 过期后的旧会话）。"""
        session = await NanobotSessionModel.find_one({"_id": session_id})
        if session is None:
            return []

        aid = str(session.agent_id or agent_id)
        sid = str(session.id)
        status_val = (
            session.status.value
            if hasattr(session.status, "value")
            else str(session.status or "unknown")
        )
        payloads: list[dict[str, Any]] = []
        seq = 0

        def add(event: str, data: dict[str, Any]) -> None:
            nonlocal seq
            seq += 1
            payloads.append({"event": event, "data": data, "id": seq})

        prompt = str(session.user_prompt or "").strip()
        if prompt:
            add(
                "user_message",
                {"agent_id": aid, "session_id": sid, "content": prompt},
            )

        add("status", {"agent_id": aid, "session_id": sid, "status": status_val})

        for i, step in enumerate(list(session.steps or [])):
            if not isinstance(step, dict):
                continue
            add(
                "step",
                {
                    "phase": "after_iteration",
                    "iteration": step.get("iteration", i),
                    "session_id": sid,
                    "step": step,
                },
            )
            content = str(step.get("content") or "").strip()
            if content:
                add(
                    "stream",
                    {"agent_id": aid, "session_id": sid, "delta": content},
                )
                add(
                    "stream_end",
                    {"agent_id": aid, "session_id": sid, "resuming": False},
                )

        if session.todos:
            add(
                "todos",
                {"agent_id": aid, "session_id": sid, "todos": list(session.todos)},
            )

        if isinstance(session.pending_approval, dict) and session.pending_approval:
            add(
                "approval_required",
                {**session.pending_approval, "agent_id": aid, "session_id": sid},
            )

        for sub in list(session.task_submissions or []):
            if isinstance(sub, dict):
                add("task_submitted", {"agent_id": aid, "session_id": sid, **sub})

        if session.result is not None:
            add(
                "result",
                {
                    "agent_id": aid,
                    "session_id": sid,
                    "status": status_val,
                    "result": session.result,
                    "error": session.error_message,
                },
            )

        return cls._slice_replay_events(payloads, limit=limit, offset=offset)

    @classmethod
    async def subscribe(
        cls,
        agent_id: str,
        session_id: str,
        *,
        limit: int | None = None,
        offset: int = 0,
    ) -> asyncio.Queue:
        """前端订阅某次会话的事件流；返回一个 per-subscriber 的 Queue。"""
        session_id = str(session_id or "").strip()
        if not session_id:
            raise AgentServiceError(
                status_codes.INVALID_ARGUMENT, "订阅 SSE 必须提供 session_id"
            )
        session = await NanobotSessionModel.find_one(
            {"_id": session_id, "agent_id": agent_id}
        )
        if session is None:
            raise AgentServiceError(
                status_codes.NOT_FOUND_SESSION,
                f"会话不存在或不属于该 Agent: session_id={session_id}",
            )
        queue: asyncio.Queue = asyncio.Queue()
        event_subscription = await AnalystEventBus.prepare_subscription(
            agent_id, session_id, queue
        )
        replay_max_seq = 0
        persisted_max_seq = 0
        try:
            await cls._flush_stream_buffer(agent_id, session_id)
            await cls._flush_reasoning_stream_buffer(agent_id, session_id)
            events = await cls._load_replay_events(
                agent_id, session_id, limit=limit, offset=offset
            )
            if events:
                for ev in events:
                    queue.put_nowait({"event": ev.event, "data": ev.data, "id": ev.seq})
                    replay_max_seq = max(replay_max_seq, int(ev.seq or 0))
            else:
                fallback = await cls._build_session_fallback_replay(
                    agent_id, session_id, limit=limit, offset=offset
                )
                for payload in fallback:
                    queue.put_nowait(payload)
            persisted_max_seq = await cls._latest_persisted_sse_seq(
                agent_id,
                session_id,
            )
        except Exception:
            logger.exception(
                f"回放 SSE 历史失败（已忽略）: agent_id={agent_id} session_id={session_id}"
            )
        async with cls._sse_lock:
            cls._sse_subscribers.setdefault((agent_id, session_id), []).append(queue)
            if event_subscription is not None:
                cls._sse_event_subscriptions[queue] = event_subscription
        if event_subscription is not None:
            AnalystEventBus.start_subscription(
                event_subscription,
                replay_max_seq=replay_max_seq,
                persisted_max_seq=persisted_max_seq,
            )
        return queue

    @classmethod
    async def unsubscribe(
        cls, agent_id: str, session_id: str, queue: asyncio.Queue
    ) -> None:
        session_id = str(session_id or "").strip()
        key = (agent_id, session_id)
        event_subscription: AnalystEventSubscription | None = None
        async with cls._sse_lock:
            event_subscription = cls._sse_event_subscriptions.pop(queue, None)
            subs = cls._sse_subscribers.get(key)
            if subs:
                try:
                    subs.remove(queue)
                except ValueError:
                    pass
                if not subs:
                    cls._sse_subscribers.pop(key, None)
        if event_subscription is not None:
            await event_subscription.close()

    @classmethod
    async def broadcast_sse(
        cls, agent_id: str, event: str, data: Any, *, persist: bool = True
    ) -> None:
        """把一条事件广播给订阅了该 (agent_id, session_id) 的 SSE 队列。

        persist=False 时仅推送给当前在线订阅者，不写 `nanobot_agent_sse_events`（用于审批
        已决等对「首条已持久化事件」的就地补丁后的实时刷新）。
        """
        current_run = get_current_run_id()
        if current_run and cls._owned_run_leases.get(current_run) != get_current_run_lease_token():
            logger.warning(
                "忽略已失租 Run 的 SSE 事件: run_id={} event={}",
                current_run,
                event,
            )
            return
        payload = {"event": event, "data": data}
        session_key: str | None = None
        persisted_seq: int | None = None
        if isinstance(data, dict):
            sid = str(data.get("session_id") or "").strip()
            if sid:
                session_key = sid
        if persist:
            if event == "stream":
                if session_key:
                    persisted_seq = await cls._alloc_sse_seq(agent_id, session_key)
                await cls._maybe_persist_stream_delta(agent_id, data)
            elif event == "reasoning_stream":
                if session_key:
                    persisted_seq = await cls._alloc_sse_seq(agent_id, session_key)
                await cls._maybe_persist_reasoning_stream_delta(agent_id, data)
            else:
                if isinstance(data, dict) and data.get("session_id"):
                    persisted_seq = await cls._persist_sse_event(
                        agent_id=agent_id,
                        session_id=str(data.get("session_id")),
                        event=event,
                        data=data,
                        compressed=False,
                    )
        if not session_key:
            logger.warning(
                f"SSE 广播缺少 session_id，已跳过实时推送: agent={agent_id} event={event}"
            )
            return
        payload["id"] = persisted_seq
        published = await AnalystEventBus.publish(
            agent_id=agent_id,
            session_id=session_key,
            event=event,
            data=data,
            seq=persisted_seq,
        )
        async with cls._sse_lock:
            subs = list(cls._sse_subscribers.get((agent_id, session_key), []))
            if published:
                subs = [
                    queue
                    for queue in subs
                    if queue not in cls._sse_event_subscriptions
                ]
        for queue in subs:
            try:
                queue.put_nowait(payload)
            except asyncio.QueueFull:
                logger.warning(
                    f"SSE 队列已满丢弃事件: agent={agent_id} session={session_key} event={event}"
                )

    @classmethod
    async def submit_approval(
        cls,
        agent_id: str,
        session_id: str,
        approval_request_id: str,
        decisions: list[dict],
        resolver_user_id: str | None = None,
    ) -> None:
        """路由层 `/agent/approve` 调用，委托 `HitlService.submit_decisions`。"""
        from app.service.analyst.hitl import HitlService

        await HitlService.submit_decisions(
            agent_id,
            session_id,
            approval_request_id,
            decisions,
            resolver_user_id=resolver_user_id,
        )

    # ------------------------------------------------------------------
    # build_bot：拉配置 + 构造 provider + Nanobot
    # ------------------------------------------------------------------

    @classmethod
    async def _assemble_bot(
        cls,
        agent: NanobotAgentModel,
        workspace: NanobotWorkspaceModel,
    ) -> Nanobot:
        """按 Agent/Workspace 配置装配 Nanobot（不创建会话文档）。"""
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

        if agent.llm_provider == NanobotLLMProviderEnum.ANTHROPIC_COMPAT:
            provider = AnthropicProvider(
                api_key=model_cfg.api_key,
                api_base=model_cfg.base_url,
                default_model=model_cfg.model,
            )
        elif agent.llm_provider == NanobotLLMProviderEnum.OPENAI_COMPAT:
            provider = OpenAICompatProvider(
                api_key=model_cfg.api_key,
                api_base=model_cfg.base_url,
                default_model=model_cfg.model,
            )
        else:
            raise AgentServiceError(
                status_codes.INVALID_ARGUMENT,
                f"不支持的 LLM 提供商: {agent.llm_provider}",
            )

        # OpenAI 兼容 provider：将 llm_config 透传给 SDK 的 extra_body。
        # 说明：这里不负责解析/拆分 temperature、max_tokens 等顶层生成参数；
        # llm_config 仅用于“额外载荷”直传。
        set_extra_body = getattr(provider, "set_extra_body", None)
        if callable(set_extra_body):
            set_extra_body(getattr(agent, "llm_config", None))

        # 将 Agent 的 reasoning_effort 应用到 provider 生成参数（未设置则为 None）。
        if isinstance(provider, LLMProvider):
            prev = provider.generation
            provider.generation = GenerationSettings(
                temperature=prev.temperature,
                max_tokens=prev.max_tokens,
                reasoning_effort=(
                    agent.reasoning_effort.value
                    if agent.reasoning_effort is not None
                    else None
                ),
            )

        mcp_subset: dict[str, dict] = {}
        for server_name in agent.mcp_servers:
            if server_name in (workspace.enabled_mcp_servers or {}):
                mcp_subset[server_name] = workspace.enabled_mcp_servers[server_name]

        always_skills_content = await SkillService.load_always_content(
            list(agent.skills or []),
            list(workspace.enabled_skills or []),
        )
        metas = await SkillService.list_enabled_for_agent(
            list(agent.skills or []),
            list(workspace.enabled_skills or []),
        )
        exclude_always = {m.skill_id for m in metas if m.always}
        skills_summary = await SkillService.build_summary(
            list(agent.skills or []),
            list(workspace.enabled_skills or []),
            exclude_skill_ids=exclude_always,
        )

        prompt_repo = AgentPromptRepository()
        prompt_ids = list(agent.agent_builtin_prompt_ids)
        if prompt_ids:
            jinja_ctx = await prompt_repo.resolve_builtin_render_context(
                prompt_ids,
                channel="cli",
                skills_summary=skills_summary,
                max_iterations=AgentDefaults().max_tool_iterations,
            )
            builtin_sections = await prompt_repo.render_many_by_ids(
                prompt_ids,
                **jinja_ctx,
            )
        else:
            builtin_sections = []

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
            prompt_repo=prompt_repo,
            builtin_prompt_sections=builtin_sections,
            always_skills_content=always_skills_content,
            skills_summary=skills_summary,
        )

        for tool in build_business_tools(agent.tools):
            bot.loop.tools.register(tool)
        bot.loop.tools.register(SubmitTaskResultTool())

        system_suffix_parts: list[str] = []
        if prompt_tpl.system_prompt and prompt_tpl.system_prompt.strip():
            system_suffix_parts.append(prompt_tpl.system_prompt.strip())
        system_suffix_parts.append(TASK_SUBMIT_GUIDANCE)
        bot.loop.context.extra_system_suffix = "\n\n".join(system_suffix_parts)

        return bot

    @classmethod
    async def build_bot(
        cls,
        agent: NanobotAgentModel,
        workspace: NanobotWorkspaceModel,
    ) -> tuple[Nanobot, str]:
        """构造本次 /start 的 Nanobot，并分配新的 session_id。"""
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

        bot = await cls._assemble_bot(agent, workspace)
        return bot, session_id

    @classmethod
    async def _launch_background_run(
        cls,
        *,
        agent_id: str,
        session_id: str,
        bot: Nanobot,
        user_prompt: str,
        context: dict[str, Any],
        auto_approve: bool = False,
    ) -> None:
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
                context=context,
                auto_approve=auto_approve,
            ),
            name=f"analyst-run:{agent_id}:{session_id}",
        )
        async with cls._task_lock:
            cls._running_tasks[session_id] = task

        await cls.broadcast_sse(
            agent_id,
            "user_message",
            {
                "agent_id": agent_id,
                "session_id": session_id,
                "content": user_prompt,
            },
        )
        await cls.broadcast_sse(
            agent_id,
            "status",
            {
                "agent_id": agent_id,
                "session_id": session_id,
                "status": NanobotSessionStatusEnum.RUNNING.value,
            },
        )

    # ------------------------------------------------------------------
    # /agent/start：启动分析任务
    # ------------------------------------------------------------------

    @classmethod
    async def start_agent(
        cls,
        agent_id: str,
        user_prompt: str,
        context: dict[str, Any] | None = None,
        auto_approve: bool = False,
        initiator_user_id: str | None = None,
    ) -> str:
        """持久化投递首轮 Run 并立即返回 session_id。"""
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

        now = datetime.now()
        session_id = generate_id(f"session:{agent.id}:{now.isoformat()}")
        run_id = generate_id(f"run:{session_id}:1:{uuid.uuid4()}")
        session = NanobotSessionModel(
            id=session_id,
            agent_id=agent.id,
            workspace_id=agent.workspace_id,
            metadata={},
            last_consolidated_seq=0,
            active_run_id=run_id,
            active_run_lease_token=None,
            run_generation=1,
            initiator_user_id=initiator_user_id,
            status=NanobotSessionStatusEnum.RUNNING,
            steps=[],
            todos=[],
            pending_approval=None,
            result=None,
            user_prompt=user_prompt,
            error_message=None,
            started_at=now,
            finished_at=None,
            created_at=now,
            updated_at=now,
        )
        await session.insert()
        try:
            await AnalystRuntimeStore.create_run(
                run_id=run_id,
                session_id=session_id,
                agent_id=agent_id,
                workspace_id=workspace.id,
                generation=1,
                user_prompt=user_prompt,
                context=context,
                auto_approve=auto_approve,
                initiator_user_id=initiator_user_id,
            )
        except AnalystRuntimeCapacityError as exc:
            await NanobotSessionModel.get_motor_collection().delete_one(
                {"_id": session_id, "active_run_id": run_id}
            )
            max_parallel = settings.NANOBOT_AGENT_MAX_PARALLEL_SESSIONS
            logger.info(
                "拒绝启动: agent_id={} 已达持久化并行上限 max={}",
                agent_id,
                max_parallel,
            )
            raise AgentServiceError(
                status_codes.CONFLICT_STATE,
                f"该 Agent 已达到并行上限 {max_parallel}，请稍后再试",
            ) from exc
        except Exception:
            await NanobotSessionModel.get_motor_collection().delete_one(
                {"_id": session_id, "active_run_id": run_id}
            )
            raise

        await cls.broadcast_sse(
            agent_id,
            "user_message",
            {
                "agent_id": agent_id,
                "session_id": session_id,
                "run_id": run_id,
                "content": user_prompt,
            },
        )
        await cls.broadcast_sse(
            agent_id,
            "status",
            {
                "agent_id": agent_id,
                "session_id": session_id,
                "run_id": run_id,
                "status": NanobotSessionStatusEnum.RUNNING.value,
            },
        )
        if not await AnalystRuntimeStore.activate_queued(run_id):
            await AnalystRuntimeStore.abandon_queued(run_id, "Run 投递激活失败")
            await cls.finalize_persistent_run(
                run_id=run_id,
                agent_id=agent_id,
                session_id=session_id,
                outcome=AnalystRunOutcome(
                    status=NanobotSessionStatusEnum.FAILED,
                    result=None,
                    error_message="Run 投递激活失败",
                ),
            )
            raise AgentServiceError(
                status_codes.INTERNAL_ERROR,
                "分析任务投递失败，请稍后重试",
            )

        logger.info(
            f"启动 agent 成功: agent_id={agent_id} session_id={session_id}"
        )
        return session_id

    # ------------------------------------------------------------------
    # /agent/message：已结束会话续聊
    # ------------------------------------------------------------------

    @classmethod
    def _validate_session_for_message(cls, sess: NanobotSessionModel) -> None:
        if sess.status in (
            NanobotSessionStatusEnum.RUNNING,
            NanobotSessionStatusEnum.AWAITING_APPROVAL,
        ):
            raise AgentServiceError(
                status_codes.CONFLICT_STATE,
                "会话仍在运行中，请等待输出完成后再提交消息",
            )
        if sess.status == NanobotSessionStatusEnum.PAUSED:
            raise AgentServiceError(
                status_codes.CONFLICT_STATE,
                "会话已暂停，当前不支持续聊",
            )
        if sess.status == NanobotSessionStatusEnum.IDLE:
            raise AgentServiceError(
                status_codes.CONFLICT_STATE,
                "会话尚未完成首轮执行，无法续聊",
            )
        if sess.status not in cls._MESSAGE_ALLOWED_STATUSES:
            raise AgentServiceError(
                status_codes.CONFLICT_STATE,
                f"当前会话状态不允许续聊: {sess.status.value}",
            )

    @classmethod
    async def send_message(
        cls,
        agent_id: str,
        session_id: str,
        user_prompt: str,
        context: dict[str, Any] | None = None,
        auto_approve: bool = False,
        initiator_user_id: str | None = None,
    ) -> str:
        """向已结束会话原子投递下一代持久化 Run。"""
        session_id = str(session_id or "").strip()
        if not session_id:
            raise AgentServiceError(
                status_codes.INVALID_ARGUMENT, "session_id 不能为空"
            )

        sess = await NanobotSessionModel.find_one({"_id": session_id})
        if sess is None or sess.agent_id != agent_id:
            raise AgentServiceError(
                status_codes.NOT_FOUND_AGENT,
                f"会话不存在或不属于该 Agent: session_id={session_id}",
            )

        cls._validate_session_for_message(sess)

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

        generation = int(sess.run_generation or 0) + 1
        run_id = generate_id(
            f"run:{session_id}:{generation}:{uuid.uuid4()}"
        )
        try:
            await AnalystRuntimeStore.create_run(
                run_id=run_id,
                session_id=session_id,
                agent_id=agent_id,
                workspace_id=workspace.id,
                generation=generation,
                user_prompt=user_prompt,
                context=context,
                auto_approve=auto_approve,
                initiator_user_id=initiator_user_id,
            )
        except AnalystRuntimeCapacityError as exc:
            max_parallel = settings.NANOBOT_AGENT_MAX_PARALLEL_SESSIONS
            logger.info(
                "拒绝续聊: agent_id={} 已达持久化并行上限 max={}",
                agent_id,
                max_parallel,
            )
            raise AgentServiceError(
                status_codes.CONFLICT_STATE,
                f"该 Agent 已达到并行上限 {max_parallel}，请稍后再试",
            ) from exc
        except DuplicateKeyError as exc:
            raise AgentServiceError(
                status_codes.CONFLICT_STATE,
                "会话已有新一轮任务被提交，请刷新后查看",
            ) from exc

        now = datetime.now()
        session_filter: dict[str, Any] = {
                "_id": session_id,
                "agent_id": agent_id,
                "active_run_id": None,
                "status": {"$in": [item.value for item in cls._MESSAGE_ALLOWED_STATUSES]},
        }
        previous_generation = int(sess.run_generation or 0)
        if previous_generation:
            session_filter["run_generation"] = previous_generation
        else:
            session_filter["$or"] = [
                {"run_generation": 0},
                {"run_generation": {"$exists": False}},
            ]
        update = await NanobotSessionModel.get_motor_collection().update_one(
            session_filter,
            {
                "$set": {
                    "active_run_id": run_id,
                    "active_run_lease_token": None,
                    "run_generation": generation,
                    "initiator_user_id": initiator_user_id,
                    "status": NanobotSessionStatusEnum.RUNNING.value,
                    "user_prompt": user_prompt,
                    "finished_at": None,
                    "error_message": None,
                    "pending_approval": None,
                    "started_at": now,
                    "updated_at": now,
                }
            },
        )
        if update.modified_count != 1:
            await AnalystRuntimeStore.abandon_queued(
                run_id,
                "会话状态已变化，投递已撤销",
            )
            raise AgentServiceError(
                status_codes.CONFLICT_STATE,
                "会话状态已变化，请刷新后重试",
            )

        await cls.broadcast_sse(
            agent_id,
            "user_message",
            {
                "agent_id": agent_id,
                "session_id": session_id,
                "run_id": run_id,
                "content": user_prompt,
            },
        )
        await cls.broadcast_sse(
            agent_id,
            "status",
            {
                "agent_id": agent_id,
                "session_id": session_id,
                "run_id": run_id,
                "status": NanobotSessionStatusEnum.RUNNING.value,
            },
        )
        if not await AnalystRuntimeStore.activate_queued(run_id):
            await AnalystRuntimeStore.abandon_queued(run_id, "Run 投递激活失败")
            await cls.finalize_persistent_run(
                run_id=run_id,
                agent_id=agent_id,
                session_id=session_id,
                outcome=AnalystRunOutcome(
                    status=NanobotSessionStatusEnum.FAILED,
                    result=None,
                    error_message="Run 投递激活失败",
                ),
            )
            raise AgentServiceError(
                status_codes.INTERNAL_ERROR,
                "分析任务投递失败，请稍后重试",
            )

        logger.info(
            f"续聊消息已提交: agent_id={agent_id} session_id={session_id}"
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
        auto_approve: bool = False,
        *,
        run_id: str | None = None,
        worker_id: str | None = None,
        lease_token: str | None = None,
        initiator_user_id: str | None = None,
        persist_result: bool = True,
        raise_cancelled: bool = True,
    ) -> AnalystRunOutcome:
        """后台任务：设 ContextVar → bot.run → 解析结果 → 写回会话 → 广播 SSE。"""
        token_completion = current_task_completion.set(None)
        token_agent = current_agent_id.set(agent_id)
        token_session = current_session_id.set(session_id)
        token_auto_approve = current_auto_approve_hitl.set(auto_approve)
        token_run = current_run_id.set(run_id)
        token_worker = current_run_worker_id.set(worker_id)
        token_lease = current_run_lease_token.set(lease_token)
        token_initiator = current_initiator_user_id.set(initiator_user_id)
        final_session_status = NanobotSessionStatusEnum.COMPLETED
        result_payload: dict | None = None
        error_message: str | None = None
        try:
            try:
                await bot.loop.context.refresh_memory_snapshot()
                system_prompt = bot.loop.context.build_system_prompt(channel="cli")
                await cls.broadcast_sse(
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

                async def _on_reasoning_stream(delta: str) -> None:
                    await cls.broadcast_sse(
                        agent_id,
                        "reasoning_stream",
                        {"agent_id": agent_id, "session_id": session_id, "delta": delta},
                    )

                async def _on_stream_end(*, resuming: bool = False, **_kw: Any) -> None:
                    # stream_end 到来时把当前缓冲的 stream 合并块先落库（用于回放）
                    await cls._flush_stream_buffer(agent_id, session_id)
                    await cls._flush_reasoning_stream_buffer(agent_id, session_id)
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
                    on_reasoning_stream=_on_reasoning_stream,
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

            stop_reason = AgentStopReasonEnum.coerce(stop_reason_meta)
            completion = get_current_task_completion()
            final_session_status, result_payload, resolved_error = _resolve_run_outcome(
                content=content,
                tools_used=tools_used,
                stop_reason=stop_reason,
                completion=completion,
            )
            if resolved_error:
                error_message = resolved_error
        except asyncio.CancelledError:
            final_session_status = NanobotSessionStatusEnum.CANCELLED
            error_message = cls._cancel_reasons.get(session_id) or "任务被取消"
            if cls._cancel_reasons.get(session_id) == "pause":
                final_session_status = NanobotSessionStatusEnum.PAUSED
            logger.info(
                f"agent 任务取消: agent_id={agent_id} session_id={session_id} "
                f"reason={error_message}"
            )
            if raise_cancelled:
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
                # run 结束前冲刷一次 stream 缓冲，保证回放不缺尾巴
                await cls._flush_stream_buffer(agent_id, session_id)
                await cls._flush_reasoning_stream_buffer(agent_id, session_id)
                if persist_result:
                    sess = await NanobotSessionModel.find_one({"_id": session_id})
                    if sess is not None:
                        sess.status = final_session_status
                        sess.result = result_payload or {"error": error_message}
                        sess.pending_approval = None
                        sess.error_message = error_message
                        sess.finished_at = datetime.now()
                        sess.updated_at = datetime.now()
                        await sess.save()
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
                current_auto_approve_hitl.reset(token_auto_approve)
                current_initiator_user_id.reset(token_initiator)
                current_run_lease_token.reset(token_lease)
                current_run_worker_id.reset(token_worker)
                current_run_id.reset(token_run)

        return AnalystRunOutcome(
            status=final_session_status,
            result=result_payload,
            error_message=error_message,
        )

    @classmethod
    async def finalize_persistent_run(
        cls,
        *,
        run_id: str,
        agent_id: str,
        session_id: str,
        outcome: AnalystRunOutcome,
    ) -> bool:
        """仅在会话仍指向该 Run 时写终态并发布结果事件。"""
        now = datetime.now()
        update = await NanobotSessionModel.get_motor_collection().update_one(
            {
                "_id": session_id,
                "agent_id": agent_id,
                "active_run_id": run_id,
            },
            {
                "$set": {
                    "active_run_id": None,
                    "active_run_lease_token": None,
                    "status": outcome.status.value,
                    "result": outcome.result or {"error": outcome.error_message},
                    "pending_approval": None,
                    "error_message": outcome.error_message,
                    "finished_at": now,
                    "updated_at": now,
                }
            },
        )
        if update.matched_count != 1:
            logger.warning(
                "忽略已过期 Run 的会话终态: run_id={} session_id={}",
                run_id,
                session_id,
            )
            return False
        await cls.broadcast_sse(
            agent_id,
            "result",
            {
                "agent_id": agent_id,
                "session_id": session_id,
                "run_id": run_id,
                "status": outcome.status.value,
                "result": outcome.result,
                "error": outcome.error_message,
            },
        )
        return True

    # ------------------------------------------------------------------
    # 取消 / 暂停
    # ------------------------------------------------------------------

    @classmethod
    async def cancel_agent(
        cls, agent_id: str, session_id: str, *, reason: str = "cancel"
    ) -> bool:
        """持久化取消意图；任意 API 实例都可取消由其他 Worker 执行的 Run。"""
        session_id = str(session_id or "").strip()
        if not session_id:
            return False
        sess = await NanobotSessionModel.find_one({"_id": session_id})
        if sess is None or sess.agent_id != agent_id:
            return False
        if sess.active_run_id:
            desired_state = (
                NanobotRunDesiredStateEnum.PAUSED
                if reason == "pause"
                else NanobotRunDesiredStateEnum.CANCELLED
            )
            run = await AnalystRuntimeStore.request_session_stop(
                agent_id=agent_id,
                session_id=session_id,
                desired_state=desired_state,
                reason=reason,
            )
            if run is None:
                return False
            if not run.active:
                outcome = AnalystRunOutcome(
                    status=(
                        NanobotSessionStatusEnum.PAUSED
                        if desired_state == NanobotRunDesiredStateEnum.PAUSED
                        else NanobotSessionStatusEnum.CANCELLED
                    ),
                    result=None,
                    error_message=reason,
                )
                await AnalystApprovalStore.cancel_pending_for_run(run.id, reason)
                await cls.finalize_persistent_run(
                    run_id=run.id,
                    agent_id=agent_id,
                    session_id=session_id,
                    outcome=outcome,
                )
            return True

        # 兼容尚未迁移的进程内旧会话；新投递不会进入此分支。
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
