"""实体单例综合内容分析节点的持久化运行时。"""

from __future__ import annotations

import asyncio
import json
import os
import socket
import uuid
from contextlib import suppress
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Sequence

from loguru import logger
from pymongo import ReturnDocument
from pymongo.errors import DuplicateKeyError

from app.core.config import settings
from app.db import rabbitmq
from app.models.action.entity_content_analysis_run import (
    EntityContentAnalysisDesiredStateEnum,
    EntityContentAnalysisRunModeEnum,
    EntityContentAnalysisRunModel,
    EntityContentAnalysisRunStatusEnum,
)
from app.schemas.action.reference import ReferenceStreamDescriptor
from app.utils.id_lib import generate_id

logger = logger.bind(name=__name__)

ENTITY_CONTENT_ANALYSIS_RUNTIME_POLL_SECONDS = max(
    0.1,
    settings.ACTION_TIMEOUT_CHECK_INTERVAL_SECONDS,
)
ENTITY_CONTENT_ANALYSIS_RUNTIME_LEASE_SECONDS = 30
ENTITY_CONTENT_ANALYSIS_RUNTIME_HEARTBEAT_SECONDS = 10
ENTITY_CONTENT_ANALYSIS_RUNTIME_CONCURRENCY = 4
ENTITY_CONTENT_ANALYSIS_RUNTIME_MAX_ATTEMPTS = 3


class EntityContentAnalysisLeaseLostError(RuntimeError):
    """当前 Worker 已失去 Run 的 fencing 租约。"""


class _RunAlreadySettled(RuntimeError):
    """Reference 单步已经持久化 Run 终态。"""


class _MonitorResult(str, Enum):
    """租约监视结果。"""

    WORK_COMPLETED = "work_completed"
    CANCELLED = "cancelled"
    LEASE_LOST = "lease_lost"


@dataclass
class _RunOutcome:
    """Worker 内部使用的有限运行结果。"""

    status: EntityContentAnalysisRunStatusEnum
    single_output: dict[str, Any] | None = None
    processed_count: int | None = None
    skipped_count: int | None = None
    error_message: str | None = None


class EntityContentAnalysisRuntimeService:
    """提交、查询、取消并维护实体内容分析持久化 Run。"""

    @staticmethod
    async def submit(
        action_id: str,
        node_instance_id: str,
        execution_key: str,
        model_config_id: str,
        llm_provider: str,
        single_input: dict[str, Any] | None = None,
        source_streams: Sequence[ReferenceStreamDescriptor] | None = None,
        destination_streams: Sequence[ReferenceStreamDescriptor] | None = None,
        analysis_field: str = "clean_content",
        min_analysis_length: int = 50,
        chunk_size: int = 8000,
        user_prompt_override: str | None = None,
    ) -> EntityContentAnalysisRunModel:
        """按行动节点执行键幂等提交一个待领取 Run。"""
        normalized_sources = [
            ReferenceStreamDescriptor.model_validate(item)
            for item in (source_streams or [])
        ]
        normalized_destinations = [
            ReferenceStreamDescriptor.model_validate(item)
            for item in (destination_streams or [])
        ]
        has_single = single_input is not None
        has_reference = bool(normalized_sources or normalized_destinations)
        if has_single == has_reference:
            raise ValueError("必须且只能选择单条输入或 Reference 输入")

        normalized_provider = str(
            getattr(llm_provider, "value", llm_provider)
        ).strip()
        if not normalized_provider:
            raise ValueError("llm_provider 不能为空")
        normalized_prompt = (
            str(user_prompt_override).strip()
            if user_prompt_override is not None
            else None
        )
        normalized_prompt = normalized_prompt or None
        run_id = generate_id(
            ":".join(
                (
                    "entity-content-analysis-run",
                    action_id,
                    node_instance_id,
                    execution_key,
                )
            )
        )
        now = datetime.now()
        run = EntityContentAnalysisRunModel(
            id=run_id,
            action_id=action_id,
            node_instance_id=node_instance_id,
            execution_key=execution_key,
            model_config_id=model_config_id,
            llm_provider=normalized_provider,
            analysis_field=analysis_field,
            min_analysis_length=min_analysis_length,
            chunk_size=chunk_size,
            user_prompt_override=normalized_prompt,
            mode=(
                EntityContentAnalysisRunModeEnum.SINGLE
                if has_single
                else EntityContentAnalysisRunModeEnum.REFERENCE
            ),
            single_input=dict(single_input) if single_input is not None else None,
            source_streams=normalized_sources,
            destination_streams=normalized_destinations,
            max_attempts=ENTITY_CONTENT_ANALYSIS_RUNTIME_MAX_ATTEMPTS,
            queued_at=now,
            created_at=now,
            updated_at=now,
        )
        try:
            await run.insert()
            return run
        except DuplicateKeyError:
            existing = await EntityContentAnalysisRunModel.find_one(
                {
                    "action_id": action_id,
                    "node_instance_id": node_instance_id,
                    "execution_key": execution_key,
                }
            )
            if existing is None:
                raise
            if not EntityContentAnalysisRuntimeService._same_submission(
                existing,
                run,
            ):
                raise ValueError(
                    f"分析 Run {existing.id} 已被不同的执行配置占用"
                )
            return existing

    @staticmethod
    async def get(run_id: str) -> EntityContentAnalysisRunModel | None:
        """按 ID 读取 Run。"""
        return await EntityContentAnalysisRunModel.find_one({"_id": run_id})

    @staticmethod
    async def reconcile(
        run_id: str,
    ) -> EntityContentAnalysisRunModel | None:
        """返回行动节点对账所需的最新持久化状态。"""
        return await EntityContentAnalysisRuntimeService.get(run_id)

    @staticmethod
    async def cancel(run_id: str, reason: str) -> bool:
        """幂等记录取消意图；未领取的 Run 直接进入取消终态。"""
        now = datetime.now()
        collection = EntityContentAnalysisRunModel.get_motor_collection()
        pending = await collection.update_one(
            {
                "_id": run_id,
                "active": True,
                "status": EntityContentAnalysisRunStatusEnum.PENDING.value,
            },
            {
                "$set": {
                    "active": False,
                    "status": EntityContentAnalysisRunStatusEnum.CANCELLED.value,
                    "desired_state": (
                        EntityContentAnalysisDesiredStateEnum.CANCELLED.value
                    ),
                    "requested_reason": reason,
                    "error_message": reason,
                    "finished_at": now,
                    "updated_at": now,
                }
            },
        )
        if pending.modified_count == 1:
            return True
        running = await collection.update_one(
            {
                "_id": run_id,
                "active": True,
                "status": EntityContentAnalysisRunStatusEnum.RUNNING.value,
            },
            {
                "$set": {
                    "desired_state": (
                        EntityContentAnalysisDesiredStateEnum.CANCELLED.value
                    ),
                    "requested_reason": reason,
                    "updated_at": now,
                }
            },
        )
        if running.modified_count == 1:
            return True
        current = await EntityContentAnalysisRuntimeService.get(run_id)
        return bool(
            current
            and current.status
            == EntityContentAnalysisRunStatusEnum.CANCELLED
        )

    @staticmethod
    async def claim_next(
        worker_id: str,
        *,
        lease_seconds: int = ENTITY_CONTENT_ANALYSIS_RUNTIME_LEASE_SECONDS,
    ) -> EntityContentAnalysisRunModel | None:
        """原子领取待执行或租约过期的 Run，并生成新 fencing token。"""
        if lease_seconds <= 0:
            raise ValueError("Run 租约必须大于 0 秒")
        now = datetime.now()
        raw = await (
            EntityContentAnalysisRunModel.get_motor_collection()
            .find_one_and_update(
                {
                    "active": True,
                    "desired_state": (
                        EntityContentAnalysisDesiredStateEnum.RUNNING.value
                    ),
                    "$expr": {"$lt": ["$attempt", "$max_attempts"]},
                    "$or": [
                        {
                            "status": (
                                EntityContentAnalysisRunStatusEnum.PENDING.value
                            )
                        },
                        {
                            "status": (
                                EntityContentAnalysisRunStatusEnum.RUNNING.value
                            ),
                            "lease_expires_at": {"$lte": now},
                        },
                    ],
                },
                {
                    "$set": {
                        "status": (
                            EntityContentAnalysisRunStatusEnum.RUNNING.value
                        ),
                        "worker_id": worker_id,
                        "lease_token": str(uuid.uuid4()),
                        "lease_expires_at": now
                        + timedelta(seconds=lease_seconds),
                        "last_heartbeat_at": now,
                        "started_at": now,
                        "error_message": None,
                        "updated_at": now,
                    },
                    "$inc": {"attempt": 1},
                },
                sort=[("queued_at", 1)],
                return_document=ReturnDocument.AFTER,
            )
        )
        return (
            EntityContentAnalysisRunModel.model_validate(raw)
            if raw
            else None
        )

    @staticmethod
    async def renew_lease(
        run_id: str,
        worker_id: str,
        lease_token: str,
        *,
        lease_seconds: int = ENTITY_CONTENT_ANALYSIS_RUNTIME_LEASE_SECONDS,
    ) -> bool:
        """仅允许当前有效租约持有者续租。"""
        now = datetime.now()
        result = await (
            EntityContentAnalysisRunModel.get_motor_collection().update_one(
                {
                    "_id": run_id,
                    "active": True,
                    "status": (
                        EntityContentAnalysisRunStatusEnum.RUNNING.value
                    ),
                    "worker_id": worker_id,
                    "lease_token": lease_token,
                    "lease_expires_at": {"$gt": now},
                },
                {
                    "$set": {
                        "lease_expires_at": now
                        + timedelta(seconds=lease_seconds),
                        "last_heartbeat_at": now,
                        "updated_at": now,
                    }
                },
            )
        )
        return result.modified_count == 1

    @staticmethod
    async def get_owned(
        run_id: str,
        worker_id: str,
        lease_token: str,
    ) -> EntityContentAnalysisRunModel | None:
        """读取当前 Worker 仍持有有效租约的 Run。"""
        return await EntityContentAnalysisRunModel.find_one(
            {
                "_id": run_id,
                "active": True,
                "status": EntityContentAnalysisRunStatusEnum.RUNNING.value,
                "worker_id": worker_id,
                "lease_token": lease_token,
                "lease_expires_at": {"$gt": datetime.now()},
            }
        )

    @staticmethod
    async def finish(
        *,
        run_id: str,
        worker_id: str,
        lease_token: str,
        status: EntityContentAnalysisRunStatusEnum,
        single_output: dict[str, Any] | None = None,
        processed_count: int | None = None,
        skipped_count: int | None = None,
        error_message: str | None = None,
        abort_key: str | None = None,
    ) -> bool:
        """使用 fencing token 原子提交终态。"""
        if status not in {
            EntityContentAnalysisRunStatusEnum.COMPLETED,
            EntityContentAnalysisRunStatusEnum.FAILED,
            EntityContentAnalysisRunStatusEnum.CANCELLED,
        }:
            raise ValueError("finish 只能提交终态")
        now = datetime.now()
        fields: dict[str, Any] = {
            "active": False,
            "status": status.value,
            "lease_expires_at": None,
            "error_message": error_message,
            "finished_at": now,
            "updated_at": now,
        }
        if single_output is not None:
            fields["single_output"] = single_output
        if processed_count is not None:
            fields["processed_count"] = processed_count
        if skipped_count is not None:
            fields["skipped_count"] = skipped_count
        update: dict[str, Any] = {"$set": fields}
        if abort_key:
            update["$addToSet"] = {"received_abort_keys": abort_key}
        result = await (
            EntityContentAnalysisRunModel.get_motor_collection().update_one(
                {
                    "_id": run_id,
                    "active": True,
                    "status": (
                        EntityContentAnalysisRunStatusEnum.RUNNING.value
                    ),
                    "worker_id": worker_id,
                    "lease_token": lease_token,
                    "lease_expires_at": {"$gt": now},
                },
                update,
            )
        )
        return result.modified_count == 1

    @staticmethod
    async def record_processed(
        *,
        run_id: str,
        worker_id: str,
        lease_token: str,
        byte_count: int,
        skipped: bool,
    ) -> bool:
        """在有效租约下记录一条已成功发布并确认的数据。"""
        increments = {
            "processed_count": 1,
            "processed_byte_count": max(0, byte_count),
        }
        if skipped:
            increments["skipped_count"] = 1
        result = await (
            EntityContentAnalysisRunModel.get_motor_collection().update_one(
                {
                    "_id": run_id,
                    "active": True,
                    "status": (
                        EntityContentAnalysisRunStatusEnum.RUNNING.value
                    ),
                    "worker_id": worker_id,
                    "lease_token": lease_token,
                    "lease_expires_at": {"$gt": datetime.now()},
                },
                {
                    "$inc": increments,
                    "$set": {
                        "error_message": None,
                        "updated_at": datetime.now(),
                    },
                },
            )
        )
        return result.modified_count == 1

    @staticmethod
    async def record_eos(
        *,
        run_id: str,
        worker_id: str,
        lease_token: str,
        control_key: str,
    ) -> EntityContentAnalysisRunModel | None:
        """幂等记录一个源生产者 EOS。"""
        raw = await (
            EntityContentAnalysisRunModel.get_motor_collection()
            .find_one_and_update(
                {
                    "_id": run_id,
                    "active": True,
                    "status": (
                        EntityContentAnalysisRunStatusEnum.RUNNING.value
                    ),
                    "worker_id": worker_id,
                    "lease_token": lease_token,
                    "lease_expires_at": {"$gt": datetime.now()},
                },
                {
                    "$addToSet": {"received_eos_keys": control_key},
                    "$set": {
                        "error_message": None,
                        "updated_at": datetime.now(),
                    },
                },
                return_document=ReturnDocument.AFTER,
            )
        )
        return (
            EntityContentAnalysisRunModel.model_validate(raw)
            if raw
            else None
        )

    @staticmethod
    async def set_transient_error(
        *,
        run_id: str,
        worker_id: str,
        lease_token: str,
        error_message: str,
    ) -> bool:
        """记录可重试异常，但不改变 Run 生命周期。"""
        result = await (
            EntityContentAnalysisRunModel.get_motor_collection().update_one(
                {
                    "_id": run_id,
                    "active": True,
                    "status": (
                        EntityContentAnalysisRunStatusEnum.RUNNING.value
                    ),
                    "worker_id": worker_id,
                    "lease_token": lease_token,
                    "lease_expires_at": {"$gt": datetime.now()},
                },
                {
                    "$set": {
                        "error_message": error_message,
                        "updated_at": datetime.now(),
                    }
                },
            )
        )
        return result.modified_count == 1

    @staticmethod
    async def settle_orphaned() -> int:
        """收敛已取消或超过最大尝试次数的失租 Run。"""
        now = datetime.now()
        collection = EntityContentAnalysisRunModel.get_motor_collection()
        cancelled = await collection.update_many(
            {
                "active": True,
                "desired_state": (
                    EntityContentAnalysisDesiredStateEnum.CANCELLED.value
                ),
                "$or": [
                    {
                        "status": (
                            EntityContentAnalysisRunStatusEnum.PENDING.value
                        )
                    },
                    {"lease_expires_at": {"$lte": now}},
                    {"lease_expires_at": None},
                ],
            },
            {
                "$set": {
                    "active": False,
                    "status": (
                        EntityContentAnalysisRunStatusEnum.CANCELLED.value
                    ),
                    "error_message": "任务被取消",
                    "finished_at": now,
                    "updated_at": now,
                }
            },
        )
        exhausted = await collection.update_many(
            {
                "active": True,
                "status": EntityContentAnalysisRunStatusEnum.RUNNING.value,
                "desired_state": (
                    EntityContentAnalysisDesiredStateEnum.RUNNING.value
                ),
                "lease_expires_at": {"$lte": now},
                "$expr": {"$gte": ["$attempt", "$max_attempts"]},
            },
            {
                "$set": {
                    "active": False,
                    "status": EntityContentAnalysisRunStatusEnum.FAILED.value,
                    "error_message": "Worker 租约过期且已达到最大尝试次数",
                    "finished_at": now,
                    "updated_at": now,
                }
            },
        )
        return cancelled.modified_count + exhausted.modified_count

    @staticmethod
    def _same_submission(
        current: EntityContentAnalysisRunModel,
        requested: EntityContentAnalysisRunModel,
    ) -> bool:
        """判断重复执行键是否对应完全相同的运行参数。"""
        fields = (
            "action_id",
            "node_instance_id",
            "execution_key",
            "model_config_id",
            "llm_provider",
            "analysis_field",
            "min_analysis_length",
            "chunk_size",
            "user_prompt_override",
            "mode",
            "single_input",
            "source_streams",
            "destination_streams",
        )
        return all(
            getattr(current, field) == getattr(requested, field)
            for field in fields
        )


class EntityContentAnalysisRuntimeWorker:
    """以租约和 fencing token 执行实体内容分析 Run。"""

    def __init__(
        self,
        *,
        poll_seconds: float = ENTITY_CONTENT_ANALYSIS_RUNTIME_POLL_SECONDS,
        lease_seconds: int = ENTITY_CONTENT_ANALYSIS_RUNTIME_LEASE_SECONDS,
        heartbeat_seconds: float = (
            ENTITY_CONTENT_ANALYSIS_RUNTIME_HEARTBEAT_SECONDS
        ),
        concurrency: int = ENTITY_CONTENT_ANALYSIS_RUNTIME_CONCURRENCY,
    ) -> None:
        suffix = uuid.uuid4().hex[:10]
        self.worker_id = f"{socket.gethostname()}:{os.getpid()}:{suffix}"
        self.poll_seconds = max(0.1, poll_seconds)
        self.lease_seconds = max(1, lease_seconds)
        self.heartbeat_seconds = max(0.1, heartbeat_seconds)
        self.concurrency = max(1, concurrency)
        self._poll_task: asyncio.Task | None = None
        self._executions: dict[str, asyncio.Task] = {}
        self._stopping = False

    async def start(self) -> None:
        """启动领取循环并先收敛无法再次领取的失租 Run。"""
        if self._poll_task is not None:
            return
        self._stopping = False
        await EntityContentAnalysisRuntimeService.settle_orphaned()
        self._poll_task = asyncio.create_task(
            self._poll_loop(),
            name=f"entity-content-analysis-worker:{self.worker_id}",
        )
        logger.info(
            "实体内容分析 Runtime Worker 已启动: worker_id={}",
            self.worker_id,
        )

    async def stop(self) -> None:
        """停止领取，并取消本进程正在执行的任务。"""
        self._stopping = True
        if self._poll_task is not None:
            self._poll_task.cancel()
            with suppress(asyncio.CancelledError):
                await self._poll_task
            self._poll_task = None
        tasks = list(self._executions.values())
        for task in tasks:
            if not task.done():
                task.cancel()
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
        self._executions.clear()
        logger.info(
            "实体内容分析 Runtime Worker 已停止: worker_id={}",
            self.worker_id,
        )

    async def _poll_loop(self) -> None:
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
                if now - last_reap_at >= self.heartbeat_seconds:
                    await EntityContentAnalysisRuntimeService.settle_orphaned()
                    last_reap_at = now
                claimed = False
                while (
                    len(self._executions) < self.concurrency
                    and not self._stopping
                ):
                    run = (
                        await EntityContentAnalysisRuntimeService.claim_next(
                            self.worker_id,
                            lease_seconds=self.lease_seconds,
                        )
                    )
                    if run is None:
                        break
                    claimed = True
                    task = asyncio.create_task(
                        self._execute_run(run),
                        name=f"entity-content-analysis-run:{run.id}",
                    )
                    task.add_done_callback(self._log_execution_result)
                    self._executions[run.id] = task
                if not claimed:
                    await asyncio.sleep(self.poll_seconds)
            except asyncio.CancelledError:
                raise
            except Exception:
                logger.exception(
                    "实体内容分析 Worker 领取循环异常，将继续重试"
                )
                await asyncio.sleep(self.poll_seconds)

    @staticmethod
    def _log_execution_result(task: asyncio.Task) -> None:
        """记录未被主流程消化的后台任务异常。"""
        if task.cancelled():
            return
        error = task.exception()
        if error is not None:
            logger.error("实体内容分析 Run 异常退出: {}", error)

    async def _execute_run(
        self,
        run: EntityContentAnalysisRunModel,
    ) -> None:
        lease_token = str(run.lease_token or "")
        if not lease_token:
            logger.error("已领取分析 Run 缺少 lease_token: run_id={}", run.id)
            return

        work_task = asyncio.create_task(
            self._process_run(run, lease_token),
            name=f"entity-content-analysis-work:{run.id}",
        )
        monitor_task = asyncio.create_task(
            self._monitor_run(run.id, lease_token, work_task),
            name=f"entity-content-analysis-lease:{run.id}",
        )
        outcome: _RunOutcome | None = None
        monitor_result = _MonitorResult.WORK_COMPLETED
        try:
            outcome = await work_task
        except _RunAlreadySettled:
            return
        except EntityContentAnalysisLeaseLostError:
            return
        except asyncio.CancelledError:
            if self._stopping:
                work_task.cancel()
                await asyncio.gather(work_task, return_exceptions=True)
                return
            monitor_result = await monitor_task
        except Exception as exc:
            logger.exception("实体内容分析 Run 执行失败: run_id={}", run.id)
            outcome = _RunOutcome(
                status=EntityContentAnalysisRunStatusEnum.FAILED,
                error_message=str(exc),
            )
        finally:
            if not monitor_task.done():
                monitor_task.cancel()
                with suppress(asyncio.CancelledError):
                    await monitor_task
            elif not monitor_task.cancelled():
                with suppress(Exception):
                    monitor_result = monitor_task.result()

        if monitor_result == _MonitorResult.LEASE_LOST:
            logger.warning("分析 Run 已失去租约，放弃提交: run_id={}", run.id)
            return
        current = await EntityContentAnalysisRuntimeService.get_owned(
            run.id,
            self.worker_id,
            lease_token,
        )
        if current is None:
            return
        if (
            monitor_result == _MonitorResult.CANCELLED
            or current.desired_state
            == EntityContentAnalysisDesiredStateEnum.CANCELLED
        ):
            outcome = _RunOutcome(
                status=EntityContentAnalysisRunStatusEnum.CANCELLED,
                error_message=current.requested_reason or "任务被取消",
            )
        if outcome is None:
            return
        committed = await EntityContentAnalysisRuntimeService.finish(
            run_id=run.id,
            worker_id=self.worker_id,
            lease_token=lease_token,
            status=outcome.status,
            single_output=outcome.single_output,
            processed_count=outcome.processed_count,
            skipped_count=outcome.skipped_count,
            error_message=outcome.error_message,
        )
        if not committed:
            logger.warning(
                "分析 Run 终态提交被 fencing 拒绝: run_id={}",
                run.id,
            )

    async def _process_run(
        self,
        run: EntityContentAnalysisRunModel,
        lease_token: str,
    ) -> _RunOutcome:
        from app.service.entity_content_analysis import (
            EntityContentAnalysisService,
        )

        analyzer = await EntityContentAnalysisService.from_model_config(
            run.model_config_id,
            run.llm_provider,
        )
        if run.mode == EntityContentAnalysisRunModeEnum.SINGLE:
            output, skipped = await self._analyze_or_skip(
                analyzer,
                run,
                dict(run.single_input or {}),
            )
            return _RunOutcome(
                status=EntityContentAnalysisRunStatusEnum.COMPLETED,
                single_output=output,
                processed_count=1,
                skipped_count=1 if skipped else 0,
            )
        return await self._process_reference_run(
            analyzer,
            run,
            lease_token,
        )

    async def _process_reference_run(
        self,
        analyzer,
        run: EntityContentAnalysisRunModel,
        lease_token: str,
    ) -> _RunOutcome:
        """逐条处理 Reference DATA，直到聚合全部源生产者 EOS。"""
        while True:
            current = await EntityContentAnalysisRuntimeService.get_owned(
                run.id,
                self.worker_id,
                lease_token,
            )
            if current is None:
                raise EntityContentAnalysisLeaseLostError("分析 Run 租约已失效")
            if self._all_sources_ended(current):
                return _RunOutcome(
                    status=EntityContentAnalysisRunStatusEnum.COMPLETED
                )

            ended = self._ended_stream_ids(current)
            handled = False
            for source in current.source_streams:
                if source.stream_id in ended:
                    continue
                try:
                    delivery = await rabbitmq.get_reference_message(
                        source.queue_name
                    )
                except Exception as exc:
                    await self._record_transient_error(
                        current,
                        lease_token,
                        f"读取 Reference 消息失败: {exc}",
                    )
                    await asyncio.sleep(self.poll_seconds)
                    handled = True
                    break
                if delivery is None:
                    continue
                handled = True
                await self._process_reference_delivery(
                    analyzer,
                    current,
                    source,
                    delivery,
                    lease_token,
                )
                break
            if not handled:
                await asyncio.sleep(self.poll_seconds)

    async def _process_reference_delivery(
        self,
        analyzer,
        run: EntityContentAnalysisRunModel,
        source: ReferenceStreamDescriptor,
        delivery,
        lease_token: str,
    ) -> None:
        """处理一条手动确认的 Reference DATA 或控制帧。"""
        try:
            control_kind = rabbitmq.get_reference_control_kind(
                delivery.message
            )
            if control_kind is not None:
                await self._process_reference_control(
                    run,
                    source,
                    delivery,
                    lease_token,
                    control_kind,
                )
                return

            try:
                payload = json.loads(delivery.message.body)
            except (TypeError, ValueError, UnicodeDecodeError) as exc:
                await self._fail_delivery(
                    run,
                    delivery,
                    lease_token,
                    f"Reference DATA 不是合法 JSON: {exc}",
                    acknowledge=False,
                )
                return
            if not isinstance(payload, dict):
                await self._fail_delivery(
                    run,
                    delivery,
                    lease_token,
                    "Reference DATA 必须是 JSON 对象",
                    acknowledge=False,
                )
                return
            try:
                output, skipped = await self._analyze_or_skip(
                    analyzer,
                    run,
                    payload,
                )
            except Exception as exc:
                await self._fail_delivery(
                    run,
                    delivery,
                    lease_token,
                    f"实体内容分析失败: {exc}",
                    acknowledge=False,
                )
                return

            try:
                await rabbitmq.publish_reference_json_delivery(
                    delivery,
                    [
                        item.queue_name
                        for item in run.destination_streams
                    ],
                    output,
                )
            except Exception as exc:
                if not getattr(delivery.message, "processed", False):
                    await delivery.nack(requeue=True)
                await self._record_transient_error(
                    run,
                    lease_token,
                    f"发布 Reference 分析结果失败: {exc}",
                )
                await asyncio.sleep(self.poll_seconds)
                return

            await delivery.ack()
            recorded = (
                await EntityContentAnalysisRuntimeService.record_processed(
                    run_id=run.id,
                    worker_id=self.worker_id,
                    lease_token=lease_token,
                    byte_count=len(delivery.message.body),
                    skipped=skipped,
                )
            )
            if not recorded:
                raise EntityContentAnalysisLeaseLostError(
                    "确认 Reference DATA 后分析 Run 租约已失效"
                )
        finally:
            await delivery.close()

    async def _process_reference_control(
        self,
        run: EntityContentAnalysisRunModel,
        source: ReferenceStreamDescriptor,
        delivery,
        lease_token: str,
        control_kind: str,
    ) -> None:
        """校验并持久化 Reference EOS 或 ABORT。"""
        stream_id, producer_id = rabbitmq.get_reference_control_identity(
            delivery.message
        )
        if stream_id != source.stream_id or not producer_id:
            await self._fail_delivery(
                run,
                delivery,
                lease_token,
                "Reference 控制消息缺少有效流或生产者身份",
                acknowledge=False,
            )
            return
        if (
            source.expected_producer_ids
            and producer_id not in source.expected_producer_ids
        ):
            await self._fail_delivery(
                run,
                delivery,
                lease_token,
                f"Reference 控制消息来自未声明的生产者: {producer_id}",
                acknowledge=False,
            )
            return
        control_key = self._control_key(stream_id, producer_id)
        if control_kind == "abort":
            await self._fail_delivery(
                run,
                delivery,
                lease_token,
                f"源流 {stream_id} 被生产者 {producer_id} 中止",
                acknowledge=True,
                abort_key=control_key,
            )
            return

        updated = await EntityContentAnalysisRuntimeService.record_eos(
            run_id=run.id,
            worker_id=self.worker_id,
            lease_token=lease_token,
            control_key=control_key,
        )
        if updated is None:
            await delivery.nack(requeue=True)
            raise EntityContentAnalysisLeaseLostError(
                "记录 Reference EOS 时分析 Run 租约已失效"
            )
        await delivery.ack()

    async def _fail_delivery(
        self,
        run: EntityContentAnalysisRunModel,
        delivery,
        lease_token: str,
        error_message: str,
        *,
        acknowledge: bool,
        abort_key: str | None = None,
    ) -> None:
        """先持久化失败终态，再终结不可继续处理的源消息。"""
        committed = await EntityContentAnalysisRuntimeService.finish(
            run_id=run.id,
            worker_id=self.worker_id,
            lease_token=lease_token,
            status=EntityContentAnalysisRunStatusEnum.FAILED,
            error_message=error_message,
            abort_key=abort_key,
        )
        if not committed:
            await delivery.nack(requeue=True)
            raise EntityContentAnalysisLeaseLostError(
                "提交 Reference 失败终态时分析 Run 租约已失效"
            )
        if acknowledge:
            await delivery.ack()
        else:
            await delivery.nack(requeue=False)
        raise _RunAlreadySettled(error_message)

    async def _record_transient_error(
        self,
        run: EntityContentAnalysisRunModel,
        lease_token: str,
        error_message: str,
    ) -> None:
        """记录瞬时错误，失租时立即停止后续副作用。"""
        recorded = (
            await EntityContentAnalysisRuntimeService.set_transient_error(
                run_id=run.id,
                worker_id=self.worker_id,
                lease_token=lease_token,
                error_message=error_message,
            )
        )
        if not recorded:
            raise EntityContentAnalysisLeaseLostError(
                "记录 Reference 瞬时异常时分析 Run 租约已失效"
            )

    @staticmethod
    async def _analyze_or_skip(
        analyzer,
        run: EntityContentAnalysisRunModel,
        record: dict[str, Any],
    ) -> tuple[dict[str, Any], bool]:
        """调用专用服务并返回显式跳过状态。"""
        outcome = await analyzer.analyze_with_outcome(
            dict(record),
            analysis_field=run.analysis_field,
            min_analysis_length=run.min_analysis_length,
            chunk_size=run.chunk_size,
            user_prompt_override=run.user_prompt_override,
        )
        if not isinstance(outcome.data, dict):
            raise TypeError("实体内容分析结果必须是对象")
        return outcome.data, outcome.skipped

    async def _monitor_run(
        self,
        run_id: str,
        lease_token: str,
        work_task: asyncio.Task,
    ) -> _MonitorResult:
        """续租并观察取消；失租时取消执行，阻止继续发布。"""
        loop = asyncio.get_running_loop()
        next_heartbeat = loop.time() + self.heartbeat_seconds
        check_seconds = min(1.0, self.poll_seconds)
        while not work_task.done():
            await asyncio.sleep(check_seconds)
            current = await EntityContentAnalysisRuntimeService.get(run_id)
            if (
                current is None
                or not current.active
                or current.worker_id != self.worker_id
                or current.lease_token != lease_token
                or current.lease_expires_at is None
                or current.lease_expires_at <= datetime.now()
            ):
                work_task.cancel()
                return _MonitorResult.LEASE_LOST
            if (
                current.desired_state
                == EntityContentAnalysisDesiredStateEnum.CANCELLED
            ):
                work_task.cancel()
                return _MonitorResult.CANCELLED
            if loop.time() >= next_heartbeat:
                renewed = (
                    await EntityContentAnalysisRuntimeService.renew_lease(
                        run_id,
                        self.worker_id,
                        lease_token,
                        lease_seconds=self.lease_seconds,
                    )
                )
                if not renewed:
                    work_task.cancel()
                    return _MonitorResult.LEASE_LOST
                next_heartbeat = loop.time() + self.heartbeat_seconds
        return _MonitorResult.WORK_COMPLETED

    @staticmethod
    def _control_key(stream_id: str, producer_id: str) -> str:
        """构造无歧义的流生产者终止键。"""
        return f"{stream_id}\x1f{producer_id}"

    @staticmethod
    def _received_producers(
        run: EntityContentAnalysisRunModel,
        stream_id: str,
    ) -> set[str]:
        """返回指定源流已收到 EOS 的生产者集合。"""
        prefix = f"{stream_id}\x1f"
        return {
            key[len(prefix) :]
            for key in run.received_eos_keys
            if key.startswith(prefix)
        }

    @staticmethod
    def _ended_stream_ids(
        run: EntityContentAnalysisRunModel,
    ) -> set[str]:
        """计算已经收齐生产者 EOS 的源流。"""
        ended: set[str] = set()
        for source in run.source_streams:
            received = (
                EntityContentAnalysisRuntimeWorker._received_producers(
                    run,
                    source.stream_id,
                )
            )
            if source.expected_producer_ids:
                if set(source.expected_producer_ids).issubset(received):
                    ended.add(source.stream_id)
            elif received:
                ended.add(source.stream_id)
        return ended

    @staticmethod
    def _all_sources_ended(
        run: EntityContentAnalysisRunModel,
    ) -> bool:
        """判断所有源流是否均已聚合完 EOS。"""
        return len(
            EntityContentAnalysisRuntimeWorker._ended_stream_ids(run)
        ) == len(run.source_streams)


__all__ = [
    "ENTITY_CONTENT_ANALYSIS_RUNTIME_CONCURRENCY",
    "ENTITY_CONTENT_ANALYSIS_RUNTIME_HEARTBEAT_SECONDS",
    "ENTITY_CONTENT_ANALYSIS_RUNTIME_LEASE_SECONDS",
    "ENTITY_CONTENT_ANALYSIS_RUNTIME_MAX_ATTEMPTS",
    "ENTITY_CONTENT_ANALYSIS_RUNTIME_POLL_SECONDS",
    "EntityContentAnalysisLeaseLostError",
    "EntityContentAnalysisRuntimeService",
    "EntityContentAnalysisRuntimeWorker",
]
