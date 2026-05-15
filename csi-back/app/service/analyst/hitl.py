"""HITL 审批握手：会话状态、SSE、决策队列与持久化补丁。

业务工具或步骤只需调用 `HitlService.request_approval(agent_id, session_id, source, payload)`，
在 `outcome.approved` 非空时执行副作用。前端按 SSE `approval_required.data.source` 分支渲染
`data.payload`。

扩展新来源：
1. 在 `HitlSource` 增加常量（如 `tool:run_command`）；
2. （可选）在 `app/schemas/agent/hitl.py` 增加 Payload 模型；
3. 调用方组装 `payload` 并 `request_approval`；
4. 写操作工具建议 `exclusive = True`。
"""
from __future__ import annotations

import asyncio
import uuid
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from loguru import logger

from app.models.agent.nanobot import NanobotSessionModel
from app.models.agent.sse_event import NanobotAgentSseEventModel
from app.schemas.agent.hitl import validate_source
from app.schemas.agent.nanobot_agent import AgentServiceError
from app.schemas.constants import NanobotSessionStatusEnum
from app.utils import status_codes

logger = logger.bind(name=__name__)


@dataclass
class HitlOutcome:
    approved: list[dict[str, Any]]
    rejections: list[str]
    resolution: str
    approval_request_id: str
    raw: dict[str, Any]


def parse_approval_decisions(
    decisions: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[str]]:
    approved: list[dict[str, Any]] = []
    rejections: list[str] = []
    for item in decisions or []:
        action = str(item.get("action") or "").lower()
        if not action:
            action = "approve" if item.get("approved") else "reject"
        if action in {"approve", "approved", "yes"}:
            approved.append(item)
        else:
            rejections.append(str(item.get("reason") or ""))
    return approved, rejections


def approval_resolution_label(
    approved: list[dict[str, Any]], rejections: list[str]
) -> str:
    if rejections and approved:
        return "mixed"
    if rejections:
        return "rejected"
    if approved:
        return "approved"
    return "rejected"


class HitlService:
    _pending_resumes: dict[str, asyncio.Queue] = {}
    _resume_lock: asyncio.Lock = asyncio.Lock()

    @classmethod
    async def clear_session(cls, session_id: str) -> None:
        session_id = str(session_id or "").strip()
        if not session_id:
            return
        async with cls._resume_lock:
            cls._pending_resumes.pop(session_id, None)

    @classmethod
    async def _get_or_create_resume_queue(cls, session_id: str) -> asyncio.Queue:
        async with cls._resume_lock:
            queue = cls._pending_resumes.get(session_id)
            if queue is None:
                queue = asyncio.Queue()
                cls._pending_resumes[session_id] = queue
            return queue

    @classmethod
    def _build_approval_event_data(
        cls,
        *,
        agent_id: str,
        session_id: str,
        approval_request_id: str,
        source: str,
        payload: dict[str, Any],
        resolution: str | None,
        reject_reasons: list[str] | None,
    ) -> dict[str, Any]:
        return {
            "agent_id": agent_id,
            "session_id": session_id,
            "approval_request_id": approval_request_id,
            "source": source,
            "resolution": resolution,
            "reject_reasons": reject_reasons,
            "payload": payload,
        }

    @classmethod
    async def submit_decisions(
        cls, agent_id: str, session_id: str, decisions: list[dict]
    ) -> None:
        session_id = str(session_id or "").strip()
        if not session_id:
            raise AgentServiceError(
                status_codes.INVALID_ARGUMENT, "session_id 不能为空"
            )
        doc = await NanobotSessionModel.find_one({"_id": session_id})
        if doc is None or doc.agent_id != agent_id:
            raise AgentServiceError(
                status_codes.NOT_FOUND_AGENT,
                f"会话不存在或不属于该 Agent: session_id={session_id}",
            )
        if doc.status != NanobotSessionStatusEnum.AWAITING_APPROVAL:
            logger.warning(
                f"/approve 写入时会话非 AWAITING_APPROVAL 状态: "
                f"session_id={session_id} status={doc.status}"
            )
        queue = await cls._get_or_create_resume_queue(session_id)
        await queue.put({"decisions": decisions, "submitted_at": datetime.now()})

    @classmethod
    async def _await_decisions(cls, session_id: str) -> dict:
        session_id = str(session_id or "").strip()
        if not session_id:
            raise RuntimeError("HITL 等待决策需要非空 session_id")
        queue = await cls._get_or_create_resume_queue(session_id)
        return await queue.get()

    @classmethod
    async def patch_persisted_approval_required(
        cls,
        agent_id: str,
        session_id: str,
        approval_request_id: str,
        *,
        resolution: str,
        reject_reasons: list[str] | None,
    ) -> None:
        session_id = str(session_id or "").strip()
        if not session_id or not approval_request_id:
            return
        try:
            rows = (
                await NanobotAgentSseEventModel.find(
                    {
                        "agent_id": agent_id,
                        "session_id": session_id,
                        "event": "approval_required",
                        "data.approval_request_id": approval_request_id,
                    }
                )
                .sort("-seq")
                .limit(1)
                .to_list()
            )
        except Exception:
            logger.exception(
                "补丁 approval_required SSE 失败（查询）: agent_id={} session_id={} req={}",
                agent_id,
                session_id,
                approval_request_id,
            )
            return
        if not rows:
            logger.warning(
                "未找到可补丁的 approval_required 事件: agent_id={} session_id={} req={}",
                agent_id,
                session_id,
                approval_request_id,
            )
            return
        doc = rows[0]
        raw = doc.data
        data = dict(raw) if isinstance(raw, dict) else {}
        if data.get("resolution") is not None:
            return
        data["resolution"] = resolution
        data["reject_reasons"] = reject_reasons
        doc.data = data
        try:
            await doc.save()
        except Exception:
            logger.exception(
                "补丁 approval_required SSE 失败（保存）: agent_id={} session_id={} req={}",
                agent_id,
                session_id,
                approval_request_id,
            )

    @classmethod
    async def request_approval(
        cls,
        agent_id: str,
        session_id: str,
        source: str,
        payload: dict[str, Any],
    ) -> HitlOutcome:
        from app.service.analyst.service import AnalystService

        source = validate_source(source)
        session_id = str(session_id or "").strip()
        if not session_id:
            raise RuntimeError("HITL 需要非空 session_id")

        approval_request_id = str(uuid.uuid4())
        requested_at = datetime.now().isoformat()
        business_payload = dict(payload)

        pending_record = {
            "approval_request_id": approval_request_id,
            "source": source,
            "requested_at": requested_at,
            "payload": business_payload,
        }

        session = await NanobotSessionModel.find_one({"_id": session_id})
        if session is None:
            raise RuntimeError(f"当前会话不存在: {session_id}")

        session.status = NanobotSessionStatusEnum.AWAITING_APPROVAL
        session.pending_approval = pending_record
        session.updated_at = datetime.now()
        await session.save()

        event_pending = cls._build_approval_event_data(
            agent_id=agent_id,
            session_id=session_id,
            approval_request_id=approval_request_id,
            source=source,
            payload=business_payload,
            resolution=None,
            reject_reasons=None,
        )
        await AnalystService.broadcast_sse(
            agent_id, "approval_required", event_pending
        )
        await AnalystService.broadcast_sse(
            agent_id,
            "status",
            {
                "agent_id": agent_id,
                "session_id": session_id,
                "status": NanobotSessionStatusEnum.AWAITING_APPROVAL.value,
            },
        )

        try:
            decision_msg = await cls._await_decisions(session_id)
        except Exception:
            logger.exception(
                f"HITL 等待审批异常: agent_id={agent_id} session_id={session_id} source={source}"
            )
            raise

        decisions = decision_msg.get("decisions") or []
        approved, rejections = parse_approval_decisions(decisions)
        resolution = approval_resolution_label(approved, rejections)

        session = await NanobotSessionModel.find_one({"_id": session_id})
        if session is not None:
            session.status = NanobotSessionStatusEnum.RUNNING
            session.pending_approval = None
            session.updated_at = datetime.now()
            await session.save()

        await cls.patch_persisted_approval_required(
            agent_id,
            session_id,
            approval_request_id,
            resolution=resolution,
            reject_reasons=rejections or None,
        )
        event_resolved = cls._build_approval_event_data(
            agent_id=agent_id,
            session_id=session_id,
            approval_request_id=approval_request_id,
            source=source,
            payload=business_payload,
            resolution=resolution,
            reject_reasons=rejections or None,
        )
        await AnalystService.broadcast_sse(
            agent_id,
            "approval_required",
            event_resolved,
            persist=False,
        )
        await AnalystService.broadcast_sse(
            agent_id,
            "status",
            {
                "agent_id": agent_id,
                "session_id": session_id,
                "status": NanobotSessionStatusEnum.RUNNING.value,
            },
        )

        return HitlOutcome(
            approved=approved,
            rejections=rejections,
            resolution=resolution,
            approval_request_id=approval_request_id,
            raw=decision_msg,
        )
