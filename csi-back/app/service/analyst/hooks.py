"""业务 Hooks：在 `AgentLoop` 迭代的关键节点把运行状态写入 `NanobotSessionModel` 并通过 SSE 广播。

所有 Hook 共享 `_base_update_agent` 辅助：按 `current_agent_id` ContextVar 拉 agent → 更新字段 → save。
任一 Hook 抛出异常默认会被 `CompositeHook._for_each_hook_safe` 吞掉（reraise=False），从而
不阻断主 agent loop；业务侧对数据一致性的强依赖在工具自身（而非 Hook）中完成。

Hook 分工（MIGRATION_PLAN §3.2）：
- StatusHook  ：`before_execute_tools` / `after_iteration` → 写 step，SSE `status`。
- TodosHook   ：`after_iteration` 扫描 tool_events 里的 `write_todos` 事件 → SSE `todos`
                （DB 写由 `WriteTodosTool.execute` 完成，Hook 只做广播兜底）。
- ApprovalHook：`after_iteration` 清理残留 `pending_approval`（兜底，正常路径由 `HitlService` 清理）。
- ResultHook  ：`finalize_content` → 对助手正文做 strip；机读结果由工具 `submit_task_result` 写入。
"""
from __future__ import annotations

from datetime import datetime

from loguru import logger

from app.models.agent.nanobot import NanobotSessionModel
from app.schemas.constants import AgentStopReasonEnum, NanobotSessionStatusEnum
from app.service.analyst.context import (
    get_current_agent_id,
    get_current_run_id,
    get_current_run_lease_token,
    get_current_session_id,
)
from app.service.nanobot.agent.hook import AgentHook, AgentHookContext

logger = logger.bind(name=__name__)


async def _load_current_session() -> NanobotSessionModel | None:
    """按 ContextVar 拿 session_id 并查库；未绑定时返回 None。"""
    session_id = get_current_session_id()
    if not session_id:
        return None
    query: dict = {"_id": session_id}
    run_id = get_current_run_id()
    if run_id:
        from app.service.analyst.service import AnalystService

        if AnalystService._owned_run_leases.get(run_id) != get_current_run_lease_token():
            return None
        query["active_run_id"] = run_id
        query["active_run_lease_token"] = get_current_run_lease_token()
    return await NanobotSessionModel.find_one(query)


class StatusHook(AgentHook):
    """记录迭代步骤流水并通过 SSE 推送给前端。

    每次 `after_iteration` 追加一条 step 到 `NanobotSessionModel.steps`；
    `before_execute_tools` 时把即将发起的 tool calls 作为预告广播出去，便于前端尽早渲染。
    """

    def __init__(self) -> None:
        super().__init__(reraise=False)

    async def before_execute_tools(self, context: AgentHookContext) -> None:
        from app.service.analyst.service import AnalystService

        agent_id = get_current_agent_id()
        if not agent_id:
            return
        tool_calls_summary = [
            {"name": tc.name, "arguments": tc.arguments}
            for tc in context.tool_calls
        ]
        await AnalystService.broadcast_sse(
            agent_id,
            "step",
            {
                "phase": "before_tools",
                "iteration": context.iteration,
                "session_id": get_current_session_id(),
                "tool_calls": tool_calls_summary,
            },
        )

    async def after_iteration(self, context: AgentHookContext) -> None:
        from app.service.analyst.service import AnalystService

        session = await _load_current_session()
        if session is None:
            return

        step_entry = {
            "iteration": context.iteration,
            "content": (context.response.content if context.response else None) or "",
            "tool_calls": [
                {"name": tc.name, "arguments": tc.arguments}
                for tc in context.tool_calls
            ],
            "tool_events": list(context.tool_events),
            "usage": dict(context.usage) if context.usage else {},
            "stop_reason": (
                context.stop_reason.value if context.stop_reason is not None else None
            ),
            "error": context.error,
            "created_at": datetime.now().isoformat(),
        }
        try:
            query: dict = {"_id": session.id}
            run_id = get_current_run_id()
            if run_id:
                query["active_run_id"] = run_id
                query["active_run_lease_token"] = get_current_run_lease_token()
            update = await NanobotSessionModel.get_motor_collection().update_one(
                query,
                {
                    "$push": {"steps": step_entry},
                    "$set": {"updated_at": datetime.now()},
                },
            )
            if update.matched_count != 1:
                return
        except Exception:
            logger.exception(f"StatusHook 保存步骤失败: session_id={session.id}")
            return

        await AnalystService.broadcast_sse(
            session.agent_id,
            "step",
            {
                "phase": "after_iteration",
                "iteration": context.iteration,
                "session_id": get_current_session_id(),
                "step": step_entry,
            },
        )


class TodosHook(AgentHook):
    """扫描 `write_todos` 的 tool_events，对外广播最新 todos（DB 写由工具自己完成）。"""

    def __init__(self) -> None:
        super().__init__(reraise=False)

    async def after_iteration(self, context: AgentHookContext) -> None:
        from app.service.analyst.service import AnalystService

        agent_id = get_current_agent_id()
        if not agent_id:
            return

        touched = False
        for event in context.tool_events or []:
            if (event.get("tool") or event.get("name")) == "write_todos":
                touched = True
                break
        if not touched:
            return

        doc = await _load_current_session()
        if doc is None:
            return
        await AnalystService.broadcast_sse(
            agent_id,
            "todos",
            {
                "agent_id": agent_id,
                "session_id": get_current_session_id(),
                "todos": list(doc.todos),
            },
        )


class ApprovalHook(AgentHook):
    """兜底：`after_iteration` 时如果会话仍卡在 `AWAITING_APPROVAL` 但本轮已推进，则清掉 pending_approval。

    正常路径下 `HitlService.request_approval` 在收到决策之后会把 status 复位；
    本 Hook 仅用于防御性兜底，避免因异常退出导致会话永远停在待审批状态。
    """

    def __init__(self) -> None:
        super().__init__(reraise=False)

    async def after_iteration(self, context: AgentHookContext) -> None:
        session = await _load_current_session()
        if session is None:
            return
        if (
            session.status == NanobotSessionStatusEnum.AWAITING_APPROVAL
            and context.stop_reason
            and context.stop_reason != AgentStopReasonEnum.AWAITING_APPROVAL
        ):
            try:
                query: dict = {
                    "_id": session.id,
                    "status": NanobotSessionStatusEnum.AWAITING_APPROVAL.value,
                }
                run_id = get_current_run_id()
                if run_id:
                    query["active_run_id"] = run_id
                    query["active_run_lease_token"] = get_current_run_lease_token()
                await NanobotSessionModel.get_motor_collection().update_one(
                    query,
                    {
                        "$set": {
                            "status": NanobotSessionStatusEnum.RUNNING.value,
                            "pending_approval": None,
                            "updated_at": datetime.now(),
                        }
                    },
                )
            except Exception:
                logger.exception(
                    f"ApprovalHook 复位 pending_approval 失败: session_id={session.id}"
                )


class ResultHook(AgentHook):
    """最终可见正文出口：`finalize_content` 做基础 strip（用户向 Markdown 由该文本承载）。"""

    def __init__(self) -> None:
        super().__init__(reraise=False)

    def finalize_content(
        self, context: AgentHookContext, content: str | None
    ) -> str | None:
        if content is None:
            return None
        return content.strip()


def default_analyst_hooks() -> list[AgentHook]:
    """返回 AnalystService 默认注入的 Hook 列表。"""
    return [StatusHook(), TodosHook(), ApprovalHook(), ResultHook()]


__all__ = [
    "StatusHook",
    "TodosHook",
    "ApprovalHook",
    "ResultHook",
    "default_analyst_hooks",
]
