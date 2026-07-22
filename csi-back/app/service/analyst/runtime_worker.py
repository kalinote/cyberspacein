"""可水平扩容的分析 Run Worker。"""

from __future__ import annotations

import asyncio
import os
import socket
import uuid
from contextlib import suppress
from datetime import datetime, timedelta

from loguru import logger

from app.core.config import settings
from app.models.agent.nanobot import (
    NanobotAgentModel,
    NanobotSessionModel,
    NanobotWorkspaceModel,
)
from app.models.agent.runtime import NanobotRunModel
from app.schemas.agent.runtime_state import (
    NanobotRunDesiredStateEnum,
    NanobotRunStatusEnum,
)
from app.schemas.constants import NanobotSessionStatusEnum
from app.service.analyst.approval_store import AnalystApprovalStore
from app.service.analyst.runtime_store import AnalystRuntimeStore
from app.service.analyst.service import AnalystRunOutcome, AnalystService
from app.service.analyst.tool_execution_store import AnalystToolExecutionStore

logger = logger.bind(name=__name__)


class AnalystRuntimeWorker:
    """从 MongoDB 原子领取 Run，并以租约和 fencing token 保护执行结果。"""

    def __init__(self) -> None:
        suffix = uuid.uuid4().hex[:10]
        self.worker_id = f"{socket.gethostname()}:{os.getpid()}:{suffix}"
        self._poll_task: asyncio.Task | None = None
        self._executions: dict[str, asyncio.Task] = {}
        self._stopping = False

    async def start(self) -> None:
        """启动领取循环，并先收敛上次崩溃遗留的过期租约。"""
        if self._poll_task is not None:
            return
        self._stopping = False
        await self._reap_expired_runs()
        self._poll_task = asyncio.create_task(
            self._poll_loop(),
            name=f"analyst-runtime-worker:{self.worker_id}",
        )
        logger.info("分析 Runtime Worker 已启动: worker_id={}", self.worker_id)

    async def stop(self) -> None:
        """停止领取新 Run，并有界取消本实例持有的执行。"""
        self._stopping = True
        if self._poll_task is not None:
            self._poll_task.cancel()
            with suppress(asyncio.CancelledError):
                await self._poll_task
            self._poll_task = None

        executions = list(self._executions.values())
        for task in executions:
            if not task.done():
                task.cancel()
        if executions:
            await asyncio.gather(*executions, return_exceptions=True)
        self._executions.clear()
        logger.info("分析 Runtime Worker 已停止: worker_id={}", self.worker_id)

    async def _poll_loop(self) -> None:
        capacity = max(1, settings.NANOBOT_RUNTIME_WORKER_CONCURRENCY)
        poll_seconds = max(0.1, settings.NANOBOT_RUNTIME_POLL_SECONDS)
        last_reap_at = 0.0
        loop = asyncio.get_running_loop()
        while True:
            try:
                self._executions = {
                    run_id: task
                    for run_id, task in self._executions.items()
                    if not task.done()
                }
                now = loop.time()
                if now - last_reap_at >= max(
                    1.0,
                    settings.NANOBOT_RUNTIME_HEARTBEAT_SECONDS,
                ):
                    await self._reap_expired_runs()
                    last_reap_at = now

                claimed = False
                while len(self._executions) < capacity and not self._stopping:
                    run = await AnalystRuntimeStore.claim_next(self.worker_id)
                    if run is None:
                        break
                    claimed = True
                    task = asyncio.create_task(
                        self._execute_run(run),
                        name=f"analyst-persistent-run:{run.id}",
                    )
                    task.add_done_callback(self._log_execution_result)
                    self._executions[run.id] = task
                if not claimed:
                    await asyncio.sleep(poll_seconds)
            except asyncio.CancelledError:
                raise
            except Exception:
                logger.exception(
                    "分析 Runtime Worker 领取循环异常，将继续重试: worker_id={}",
                    self.worker_id,
                )
                await asyncio.sleep(poll_seconds)

    def _log_execution_result(self, task: asyncio.Task) -> None:
        """记录未被执行主流程消化的 Run 任务异常。"""
        if task.cancelled():
            return
        error = task.exception()
        if error is not None:
            logger.error("持久化 Run 任务异常退出: {}", error)

    async def _execute_run(self, run: NanobotRunModel) -> None:
        lease_token = str(run.lease_token or "")
        if not lease_token:
            logger.error("已领取 Run 缺少 lease_token: run_id={}", run.id)
            return

        outcome: AnalystRunOutcome
        lost_lease = False
        analysis_task: asyncio.Task | None = None
        monitor_task: asyncio.Task | None = None
        bot = None
        try:
            if not await AnalystRuntimeStore.renew_lease(
                run.id,
                self.worker_id,
                lease_token,
            ):
                logger.warning("Run 执行前已失去租约: run_id={}", run.id)
                return
            session = await NanobotSessionModel.find_one(
                {
                    "_id": run.session_id,
                    "agent_id": run.agent_id,
                    "active_run_id": run.id,
                }
            )
            agent = await NanobotAgentModel.find_one({"_id": run.agent_id})
            workspace = await NanobotWorkspaceModel.find_one({"_id": run.workspace_id})
            if session is None:
                raise RuntimeError("Run 对应会话不存在或已被新一轮运行替代")
            if agent is None:
                raise RuntimeError(f"Run 对应 Agent 不存在: {run.agent_id}")
            if workspace is None or workspace.id != agent.workspace_id:
                raise RuntimeError(f"Run 对应工作区不存在: {run.workspace_id}")

            bound = await NanobotSessionModel.get_motor_collection().update_one(
                {
                    "_id": run.session_id,
                    "agent_id": run.agent_id,
                    "active_run_id": run.id,
                },
                {
                    "$set": {
                        "active_run_lease_token": lease_token,
                        "updated_at": datetime.now(),
                    }
                },
            )
            if bound.matched_count != 1:
                raise RuntimeError("绑定 Run fencing token 时会话状态已变化")
            AnalystService._owned_run_leases[run.id] = lease_token

            await AnalystService._get_session_store().invalidate(run.session_id)
            bot = await AnalystService._assemble_bot(agent, workspace)
            if not await AnalystRuntimeStore.renew_lease(
                run.id,
                self.worker_id,
                lease_token,
            ):
                lost_lease = True
                logger.warning("Run 装配完成后已失去租约: run_id={}", run.id)
                return
            async with AnalystService._bots_lock:
                AnalystService._bots[run.session_id] = bot

            analysis_task = asyncio.create_task(
                AnalystService.run_analysis(
                    agent_id=run.agent_id,
                    session_id=run.session_id,
                    bot=bot,
                    user_prompt=run.user_prompt,
                    context=dict(run.context or {}),
                    auto_approve=run.auto_approve,
                    run_id=run.id,
                    worker_id=self.worker_id,
                    lease_token=lease_token,
                    initiator_user_id=run.initiator_user_id,
                    persist_result=False,
                    raise_cancelled=False,
                ),
                name=f"analyst-run:{run.agent_id}:{run.session_id}",
            )
            async with AnalystService._task_lock:
                AnalystService._running_tasks[run.session_id] = analysis_task
            monitor_task = asyncio.create_task(
                self._monitor_lease(run, lease_token, analysis_task, bot),
                name=f"analyst-run-lease:{run.id}",
            )
            outcome = await analysis_task
            lost_lease = bool(await monitor_task)
        except asyncio.CancelledError:
            if analysis_task is not None and not analysis_task.done():
                AnalystService._cancel_reasons[run.session_id] = "shutdown"
                analysis_task.cancel()
                await asyncio.gather(analysis_task, return_exceptions=True)
            outcome = AnalystRunOutcome(
                status=NanobotSessionStatusEnum.FAILED,
                result=None,
                error_message="Worker 正在关闭，运行已中断",
            )
        except Exception as exc:
            logger.exception("执行持久化 Run 失败: run_id={}", run.id)
            outcome = AnalystRunOutcome(
                status=NanobotSessionStatusEnum.FAILED,
                result=None,
                error_message=str(exc),
            )
        finally:
            AnalystService._owned_run_leases.pop(run.id, None)
            if monitor_task is not None:
                if not monitor_task.done():
                    monitor_task.cancel()
                    with suppress(asyncio.CancelledError):
                        await monitor_task
                elif not monitor_task.cancelled():
                    try:
                        lost_lease = lost_lease or bool(monitor_task.result())
                    except Exception:
                        logger.exception(
                            "读取 Run 租约监视结果失败: run_id={}",
                            run.id,
                        )
                        lost_lease = True
            if analysis_task is None and bot is not None:
                with suppress(Exception):
                    await bot.close()

        if lost_lease:
            logger.warning("Worker 已失去租约，放弃提交结果: run_id={}", run.id)
            return

        current = await AnalystRuntimeStore.get(run.id)
        if (
            current is None
            or not current.active
            or current.worker_id != self.worker_id
            or current.lease_token != lease_token
        ):
            logger.warning("Run 已被其他状态收敛，放弃提交结果: run_id={}", run.id)
            return

        run_status = self._run_status_for_outcome(outcome.status)
        if self._stopping:
            run_status = NanobotRunStatusEnum.INTERRUPTED
            outcome = AnalystRunOutcome(
                status=NanobotSessionStatusEnum.FAILED,
                result=None,
                error_message="Worker 正在关闭，运行已中断",
            )
        elif current.desired_state == NanobotRunDesiredStateEnum.CANCELLED:
            run_status = NanobotRunStatusEnum.CANCELLED
            outcome = AnalystRunOutcome(
                status=NanobotSessionStatusEnum.CANCELLED,
                result=None,
                error_message=current.requested_reason or "任务被取消",
            )
        elif current.desired_state == NanobotRunDesiredStateEnum.PAUSED:
            run_status = NanobotRunStatusEnum.PAUSED
            outcome = AnalystRunOutcome(
                status=NanobotSessionStatusEnum.PAUSED,
                result=None,
                error_message=current.requested_reason or "任务已暂停",
            )

        committed = await AnalystRuntimeStore.finish(
            run_id=run.id,
            worker_id=self.worker_id,
            lease_token=lease_token,
            status=run_status,
            result=outcome.result,
            error_message=outcome.error_message,
        )
        if not committed:
            logger.warning("Run 终态提交被 fencing 拒绝: run_id={}", run.id)
            return
        await AnalystToolExecutionStore.mark_unfinished_unknown(
            run.id,
            outcome.error_message or "运行已结束，但工具未提交结果",
        )
        await AnalystApprovalStore.cancel_pending_for_run(
            run.id,
            outcome.error_message or "运行已结束",
        )
        await AnalystService.finalize_persistent_run(
            run_id=run.id,
            agent_id=run.agent_id,
            session_id=run.session_id,
            outcome=outcome,
        )

    async def _monitor_lease(
        self,
        run: NanobotRunModel,
        lease_token: str,
        analysis_task: asyncio.Task,
        bot,
    ) -> bool:
        """续租并观察取消意图；返回 True 表示租约已经丢失。"""
        heartbeat_seconds = max(1.0, settings.NANOBOT_RUNTIME_HEARTBEAT_SECONDS)
        poll_seconds = min(1.0, max(0.2, settings.NANOBOT_RUNTIME_POLL_SECONDS))
        loop = asyncio.get_running_loop()
        next_heartbeat = loop.time() + heartbeat_seconds
        while not analysis_task.done():
            await asyncio.sleep(poll_seconds)
            try:
                current = await AnalystRuntimeStore.get(run.id)
                if (
                    current is None
                    or not current.active
                    or current.worker_id != self.worker_id
                    or current.lease_token != lease_token
                    or current.lease_expires_at is None
                    or current.lease_expires_at <= datetime.now()
                ):
                    AnalystService._owned_run_leases.pop(run.id, None)
                    AnalystService._cancel_reasons[run.session_id] = "lost lease"
                    analysis_task.cancel()
                    return True
                if current.desired_state != NanobotRunDesiredStateEnum.RUNNING:
                    AnalystService._owned_run_leases.pop(run.id, None)
                    reason = current.requested_reason or current.desired_state.value
                    AnalystService._cancel_reasons[run.session_id] = (
                        "pause"
                        if current.desired_state == NanobotRunDesiredStateEnum.PAUSED
                        else reason
                    )
                    try:
                        await bot.loop.subagents.cancel_by_session(run.session_id)
                    except Exception as exc:
                        logger.warning(
                            "取消持久化 Run 时清理子代理失败: run_id={} err={}",
                            run.id,
                            exc,
                        )
                    analysis_task.cancel()
                    return False
                if loop.time() >= next_heartbeat:
                    renewed = await AnalystRuntimeStore.renew_lease(
                        run.id,
                        self.worker_id,
                        lease_token,
                    )
                    if not renewed:
                        AnalystService._owned_run_leases.pop(run.id, None)
                        AnalystService._cancel_reasons[run.session_id] = "lost lease"
                        analysis_task.cancel()
                        return True
                    next_heartbeat = loop.time() + heartbeat_seconds
            except asyncio.CancelledError:
                raise
            except Exception:
                logger.exception(
                    "Run 租约检查异常，停止执行以避免失租后继续产生副作用: run_id={}",
                    run.id,
                )
                AnalystService._owned_run_leases.pop(run.id, None)
                AnalystService._cancel_reasons[run.session_id] = "lost lease"
                analysis_task.cancel()
                return True
        return False

    async def _reap_expired_runs(self) -> None:
        """将崩溃 Worker 遗留的过期 Run 收敛为可解释终态。"""
        expired = await AnalystRuntimeStore.expire_stale()
        expired.extend(await AnalystRuntimeStore.expire_unready())
        for run in expired:
            await AnalystToolExecutionStore.mark_unfinished_unknown(
                run.id,
                run.error_message or "Worker 租约过期",
            )
            await AnalystApprovalStore.cancel_pending_for_run(
                run.id,
                run.error_message or "Worker 租约过期",
            )
            await AnalystService.finalize_persistent_run(
                run_id=run.id,
                agent_id=run.agent_id,
                session_id=run.session_id,
                outcome=AnalystRunOutcome(
                    status=NanobotSessionStatusEnum.FAILED,
                    result=None,
                    error_message=run.error_message,
                ),
            )
        if expired:
            logger.warning("已收敛 {} 个租约过期的分析 Run", len(expired))
        await self._reconcile_terminal_sessions()

    async def _reconcile_terminal_sessions(self) -> None:
        """修复 Run 已终态但 Worker 未完成会话写回的跨文档中断窗口。"""
        sessions = await NanobotSessionModel.find(
            {"active_run_id": {"$ne": None}}
        ).to_list()
        missing_deadline = datetime.now() - timedelta(
            seconds=settings.NANOBOT_RUNTIME_LEASE_SECONDS
        )
        for session in sessions:
            run_id = str(session.active_run_id or "")
            if not run_id:
                continue
            run = await AnalystRuntimeStore.get(run_id)
            if run is not None and run.active:
                continue
            if run is None and session.updated_at > missing_deadline:
                continue

            if run is None:
                outcome = AnalystRunOutcome(
                    status=NanobotSessionStatusEnum.FAILED,
                    result=None,
                    error_message="会话引用的持久化 Run 不存在",
                )
            else:
                status = {
                    NanobotRunStatusEnum.COMPLETED: NanobotSessionStatusEnum.COMPLETED,
                    NanobotRunStatusEnum.CANCELLED: NanobotSessionStatusEnum.CANCELLED,
                    NanobotRunStatusEnum.PAUSED: NanobotSessionStatusEnum.PAUSED,
                }.get(run.status, NanobotSessionStatusEnum.FAILED)
                outcome = AnalystRunOutcome(
                    status=status,
                    result=run.result,
                    error_message=run.error_message,
                )
            await AnalystService.finalize_persistent_run(
                run_id=run_id,
                agent_id=session.agent_id,
                session_id=session.id,
                outcome=outcome,
            )

    @staticmethod
    def _run_status_for_outcome(
        session_status: NanobotSessionStatusEnum,
    ) -> NanobotRunStatusEnum:
        """将会话终态映射为持久化 Run 终态。"""
        return {
            NanobotSessionStatusEnum.COMPLETED: NanobotRunStatusEnum.COMPLETED,
            NanobotSessionStatusEnum.CANCELLED: NanobotRunStatusEnum.CANCELLED,
            NanobotSessionStatusEnum.PAUSED: NanobotRunStatusEnum.PAUSED,
        }.get(session_status, NanobotRunStatusEnum.FAILED)


__all__ = ["AnalystRuntimeWorker"]
