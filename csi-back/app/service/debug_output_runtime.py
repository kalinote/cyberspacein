"""调试输出节点的持久化运行时。"""

from __future__ import annotations

import asyncio
import base64
import hashlib
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

from app.db import rabbitmq
from app.models.action.debug_output_run import (
    DebugOutputDesiredStateEnum,
    DebugOutputInputEdgeModel,
    DebugOutputRunModel,
    DebugOutputRunStatusEnum,
)
from app.models.action.node_execution import ActionNodeExecutionModel
from app.service.action.log import ActionLogService
from app.utils.id_lib import generate_id

logger = logger.bind(name=__name__)

DEBUG_OUTPUT_PREVIEW_BYTES = 24 * 1024
DEBUG_OUTPUT_LOG_WRITE_ATTEMPTS = 3
DEBUG_OUTPUT_RUNTIME_POLL_SECONDS = 0.1
DEBUG_OUTPUT_RUNTIME_LEASE_SECONDS = 30
DEBUG_OUTPUT_RUNTIME_HEARTBEAT_SECONDS = 10
DEBUG_OUTPUT_RUNTIME_CONCURRENCY = 4
_CONTROL_KEY_SEPARATOR = "\x1f"


class DebugOutputLeaseLostError(RuntimeError):
    """当前 Worker 已失去 Run 的 fencing 租约。"""


class DebugOutputLogWriteError(RuntimeError):
    """调试日志在限定次数内仍未成功写入。"""


class _RunAlreadySettled(RuntimeError):
    """当前处理步骤已经持久化 Run 终态。"""


class _MonitorResult(str, Enum):
    """租约监视结果。"""

    WORK_COMPLETED = "work_completed"
    CANCELLED = "cancelled"
    PAUSED = "paused"
    LEASE_LOST = "lease_lost"


@dataclass(frozen=True)
class DebugOutputPreview:
    """调试日志可展示内容及其完整载荷摘要。"""

    message: str
    original_byte_count: int
    sha256: str
    truncated: bool
    content_kind: str


@dataclass
class _RunOutcome:
    """Worker 内部使用的有限运行结果。"""

    status: DebugOutputRunStatusEnum
    error_message: str | None = None


def _truncate_utf8(value: str) -> tuple[str, bool]:
    """按 UTF-8 字节安全截断调试预览。"""
    payload = value.encode("utf-8")
    if len(payload) <= DEBUG_OUTPUT_PREVIEW_BYTES:
        return value or "（空数据）", False
    suffix = "\n…（内容已截断）".encode("utf-8")
    prefix = payload[: DEBUG_OUTPUT_PREVIEW_BYTES - len(suffix)]
    return prefix.decode("utf-8", errors="ignore") + suffix.decode(), True


def build_value_preview(value: Any) -> DebugOutputPreview:
    """把任意 Value 数据转换为有界调试预览。"""
    try:
        if isinstance(value, bytes):
            raw = value
            rendered = base64.b64encode(value).decode("ascii")
            content_kind = "base64"
        elif isinstance(value, bytearray):
            raw = bytes(value)
            rendered = base64.b64encode(raw).decode("ascii")
            content_kind = "base64"
        elif isinstance(value, str):
            raw = value.encode("utf-8")
            rendered = value
            content_kind = "text"
        else:
            rendered = json.dumps(
                value,
                ensure_ascii=False,
                indent=2,
                default=str,
            )
            raw = rendered.encode("utf-8")
            content_kind = "json"
        message, truncated = _truncate_utf8(rendered)
    except Exception:
        rendered = "（数据无法安全序列化）"
        raw = rendered.encode("utf-8")
        message = rendered
        truncated = False
        content_kind = "unserializable"
    return DebugOutputPreview(
        message=message,
        original_byte_count=len(raw),
        sha256=hashlib.sha256(raw).hexdigest(),
        truncated=truncated,
        content_kind=content_kind,
    )


def build_reference_preview(
    body: bytes,
    *,
    content_type: str | None,
    content_encoding: str | None,
) -> DebugOutputPreview:
    """按 AMQP 内容属性格式化 Reference DATA。"""
    encoding = content_encoding or "utf-8"
    rendered: str
    content_kind: str
    try:
        decoded = body.decode(encoding)
        if content_type and "json" in content_type.lower():
            try:
                rendered = json.dumps(
                    json.loads(decoded),
                    ensure_ascii=False,
                    indent=2,
                )
                content_kind = "json"
            except (TypeError, ValueError):
                rendered = decoded
                content_kind = "text"
        else:
            rendered = decoded
            content_kind = "text"
    except (LookupError, UnicodeDecodeError):
        rendered = base64.b64encode(body).decode("ascii")
        content_kind = "base64"
    message, truncated = _truncate_utf8(rendered)
    return DebugOutputPreview(
        message=message,
        original_byte_count=len(body),
        sha256=hashlib.sha256(body).hexdigest(),
        truncated=truncated,
        content_kind=content_kind,
    )


class DebugOutputRuntimeService:
    """提交、动态投递并维护调试输出持久化 Run。"""

    @staticmethod
    async def submit(
        *,
        action_id: str,
        node_instance_id: str,
        node_execution_id: str,
        execution_key: str,
        incoming_edges: Sequence[DebugOutputInputEdgeModel | dict[str, Any]],
    ) -> DebugOutputRunModel:
        """按行动节点执行键幂等提交一个调试观察 Run。"""
        normalized_edges = [
            DebugOutputInputEdgeModel.model_validate(edge)
            for edge in incoming_edges
        ]
        now = datetime.now()
        run = DebugOutputRunModel(
            id=generate_id(
                ":".join(
                    (
                        "debug-output-run",
                        action_id,
                        node_instance_id,
                        execution_key,
                    )
                )
            ),
            action_id=action_id,
            node_instance_id=node_instance_id,
            node_execution_id=node_execution_id,
            execution_key=execution_key,
            incoming_edges=normalized_edges,
            queued_at=now,
            created_at=now,
            updated_at=now,
        )
        try:
            await run.insert()
            return run
        except DuplicateKeyError:
            existing = await DebugOutputRunModel.find_one(
                {
                    "action_id": action_id,
                    "node_instance_id": node_instance_id,
                    "execution_key": execution_key,
                }
            )
            if existing is None:
                raise
            if not DebugOutputRuntimeService._same_submission(existing, run):
                raise ValueError(
                    f"调试输出 Run {existing.id} 已被不同的执行配置占用"
                )
            return existing

    @staticmethod
    async def get(run_id: str) -> DebugOutputRunModel | None:
        """按 ID 读取 Run。"""
        return await DebugOutputRunModel.find_one({"_id": run_id})

    @staticmethod
    async def reconcile(run_id: str) -> DebugOutputRunModel | None:
        """返回行动节点对账所需的最新持久化状态。"""
        return await DebugOutputRuntimeService.get(run_id)

    @staticmethod
    async def get_active_for_node(
        action_id: str,
        node_instance_id: str,
    ) -> DebugOutputRunModel | None:
        """查找节点当前仍可接收动态输入的 Run。"""
        return await DebugOutputRunModel.find_one(
            {
                "action_id": action_id,
                "node_instance_id": node_instance_id,
                "active": True,
            }
        )

    @staticmethod
    async def observe_value_for_node(
        action_id: str,
        node_instance_id: str,
        edge_id: str,
        value: Any,
        edge_metadata: dict[str, Any] | None = None,
    ) -> bool:
        """按节点定位活动 Run 并记录一条动态 Value 输入。"""
        run = await DebugOutputRuntimeService.get_active_for_node(
            action_id,
            node_instance_id,
        )
        if run is None:
            return False
        return await DebugOutputRuntimeService.observe_value(
            run.id,
            edge_id,
            value,
            edge_metadata=edge_metadata,
        )

    @staticmethod
    async def observe_value(
        run_id: str,
        edge_id: str,
        value: Any,
        *,
        edge_metadata: dict[str, Any] | None = None,
    ) -> bool:
        """日志成功后幂等确认一条 Value 输入边。"""
        run = await DebugOutputRuntimeService.get(run_id)
        if run is None or not run.active:
            return bool(run and edge_id in run.received_value_edge_ids)
        edge = DebugOutputRuntimeService._require_edge(
            run,
            edge_id,
            data_type="value",
        )
        if edge_id in run.received_value_edge_ids:
            return True
        if edge_id in run.aborted_input_edge_ids:
            return False

        preview = build_value_preview(value)
        fields = DebugOutputRuntimeService._edge_fields(edge)
        fields.update(edge_metadata or {})
        fields.update(
            {
                "content_kind": preview.content_kind,
                "original_byte_count": preview.original_byte_count,
                "sha256": preview.sha256,
                "truncated": preview.truncated,
            }
        )
        try:
            await DebugOutputRuntimeService._write_debug_log(
                run,
                event_key=DebugOutputRuntimeService._event_key(
                    "value",
                    edge_id,
                    "single",
                ),
                message=preview.message,
                fields=fields,
                truncated=preview.truncated,
            )
        except DebugOutputLogWriteError as exc:
            await DebugOutputRuntimeService._fail_unfenced(
                run.id,
                str(exc),
            )
            raise

        result = await DebugOutputRunModel.get_motor_collection().update_one(
            {
                "_id": run.id,
                "active": True,
                "received_value_edge_ids": {"$ne": edge_id},
                "aborted_input_edge_ids": {"$ne": edge_id},
            },
            {
                "$addToSet": {"received_value_edge_ids": edge_id},
                "$inc": {
                    "logged_count": 1,
                    "logged_byte_count": preview.original_byte_count,
                    "truncated_count": 1 if preview.truncated else 0,
                },
                "$set": {"updated_at": datetime.now(), "error_message": None},
            },
        )
        if result.modified_count == 1:
            return True
        current = await DebugOutputRuntimeService.get(run.id)
        return bool(current and edge_id in current.received_value_edge_ids)

    @staticmethod
    async def abort_input_for_node(
        action_id: str,
        node_instance_id: str,
        edge_id: str,
        reason: str,
    ) -> bool:
        """按节点定位活动 Run 并终止一条无法再产生数据的输入边。"""
        run = await DebugOutputRuntimeService.get_active_for_node(
            action_id,
            node_instance_id,
        )
        if run is None:
            return False
        return await DebugOutputRuntimeService.abort_input(
            run.id,
            edge_id,
            reason,
        )

    @staticmethod
    async def abort_input(
        run_id: str,
        edge_id: str,
        reason: str,
    ) -> bool:
        """记录上游未产生输入的诊断信息并终止该边。"""
        run = await DebugOutputRuntimeService.get(run_id)
        if run is None:
            return False
        if not run.active:
            return edge_id in {
                *run.received_value_edge_ids,
                *run.aborted_input_edge_ids,
            }
        if edge_id in run.aborted_input_edge_ids:
            return True
        if edge_id in run.received_value_edge_ids:
            return True
        edge = DebugOutputRuntimeService._require_edge(run, edge_id)
        fields = DebugOutputRuntimeService._edge_fields(edge)
        fields["reason"] = reason
        try:
            await DebugOutputRuntimeService._write_debug_log(
                run,
                event_key=DebugOutputRuntimeService._event_key(
                    "input-abort",
                    edge_id,
                    reason,
                ),
                message=f"输入边已中止：{reason}",
                fields=fields,
                level="WARNING",
            )
        except DebugOutputLogWriteError as exc:
            await DebugOutputRuntimeService._fail_unfenced(
                run.id,
                str(exc),
            )
            raise
        result = await DebugOutputRunModel.get_motor_collection().update_one(
            {
                "_id": run.id,
                "active": True,
                "aborted_input_edge_ids": {"$ne": edge_id},
                "received_value_edge_ids": {"$ne": edge_id},
            },
            {
                "$addToSet": {"aborted_input_edge_ids": edge_id},
                "$inc": {"warning_count": 1},
                "$set": {"updated_at": datetime.now()},
            },
        )
        if result.modified_count == 1:
            return True
        current = await DebugOutputRuntimeService.get(run.id)
        return bool(current and edge_id in current.aborted_input_edge_ids)

    @staticmethod
    async def cancel(run_id: str, reason: str) -> bool:
        """幂等记录取消意图，未运行的 Run 直接进入取消终态。"""
        now = datetime.now()
        collection = DebugOutputRunModel.get_motor_collection()
        idle = await collection.update_one(
            {
                "_id": run_id,
                "active": True,
                "status": {
                    "$in": [
                        DebugOutputRunStatusEnum.PENDING.value,
                        DebugOutputRunStatusEnum.PAUSED.value,
                    ]
                },
            },
            {
                "$set": {
                    "active": False,
                    "status": DebugOutputRunStatusEnum.CANCELLED.value,
                    "desired_state": DebugOutputDesiredStateEnum.CANCELLED.value,
                    "requested_reason": reason,
                    "error_message": reason,
                    "finished_at": now,
                    "updated_at": now,
                }
            },
        )
        if idle.modified_count == 1:
            return True
        running = await collection.update_one(
            {
                "_id": run_id,
                "active": True,
                "status": DebugOutputRunStatusEnum.RUNNING.value,
            },
            {
                "$set": {
                    "desired_state": DebugOutputDesiredStateEnum.CANCELLED.value,
                    "requested_reason": reason,
                    "updated_at": now,
                }
            },
        )
        if running.modified_count == 1:
            return True
        current = await DebugOutputRuntimeService.get(run_id)
        return bool(
            current and current.status == DebugOutputRunStatusEnum.CANCELLED
        )

    @staticmethod
    async def pause(run_id: str, reason: str = "行动已暂停") -> bool:
        """暂停 Run；活动消费者会关闭通道并释放未确认消息。"""
        now = datetime.now()
        collection = DebugOutputRunModel.get_motor_collection()
        pending = await collection.update_one(
            {
                "_id": run_id,
                "active": True,
                "status": DebugOutputRunStatusEnum.PENDING.value,
            },
            {
                "$set": {
                    "status": DebugOutputRunStatusEnum.PAUSED.value,
                    "desired_state": DebugOutputDesiredStateEnum.PAUSED.value,
                    "requested_reason": reason,
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
                "status": DebugOutputRunStatusEnum.RUNNING.value,
            },
            {
                "$set": {
                    "desired_state": DebugOutputDesiredStateEnum.PAUSED.value,
                    "requested_reason": reason,
                    "updated_at": now,
                }
            },
        )
        if running.modified_count == 1:
            return True
        current = await DebugOutputRuntimeService.get(run_id)
        return bool(current and current.status == DebugOutputRunStatusEnum.PAUSED)

    @staticmethod
    async def pause_for_action(
        action_id: str,
        reason: str = "行动已暂停",
    ) -> int:
        """暂停行动下全部仍活动的调试输出 Run。"""
        runs = await DebugOutputRunModel.find(
            {"action_id": action_id, "active": True}
        ).to_list()
        results = await asyncio.gather(
            *(
                DebugOutputRuntimeService.pause(run.id, reason)
                for run in runs
            ),
            return_exceptions=True,
        )
        return sum(result is True for result in results)

    @staticmethod
    async def resume(run_id: str) -> bool:
        """把暂停 Run 放回可领取队列。"""
        now = datetime.now()
        collection = DebugOutputRunModel.get_motor_collection()
        result = await collection.update_one(
            {
                "_id": run_id,
                "active": True,
                "status": DebugOutputRunStatusEnum.PAUSED.value,
            },
            {
                "$set": {
                    "status": DebugOutputRunStatusEnum.PENDING.value,
                    "desired_state": DebugOutputDesiredStateEnum.RUNNING.value,
                    "requested_reason": None,
                    "queued_at": now,
                    "updated_at": now,
                }
            },
        )
        if result.modified_count == 1:
            return True
        resuming = await collection.update_one(
            {
                "_id": run_id,
                "active": True,
                "status": DebugOutputRunStatusEnum.RUNNING.value,
                "desired_state": DebugOutputDesiredStateEnum.PAUSED.value,
            },
            {
                "$set": {
                    "desired_state": DebugOutputDesiredStateEnum.RUNNING.value,
                    "requested_reason": None,
                    "updated_at": now,
                }
            },
        )
        return resuming.modified_count == 1

    @staticmethod
    async def resume_for_action(action_id: str) -> int:
        """恢复行动下全部仍活动的调试输出 Run。"""
        runs = await DebugOutputRunModel.find(
            {
                "action_id": action_id,
                "active": True,
                "$or": [
                    {"status": DebugOutputRunStatusEnum.PAUSED.value},
                    {
                        "desired_state": (
                            DebugOutputDesiredStateEnum.PAUSED.value
                        )
                    },
                ],
            }
        ).to_list()
        results = await asyncio.gather(
            *(DebugOutputRuntimeService.resume(run.id) for run in runs),
            return_exceptions=True,
        )
        return sum(result is True for result in results)

    @staticmethod
    async def claim_next(
        worker_id: str,
        *,
        lease_seconds: int = DEBUG_OUTPUT_RUNTIME_LEASE_SECONDS,
    ) -> DebugOutputRunModel | None:
        """原子领取待执行或租约过期的 Run 并生成 fencing token。"""
        if lease_seconds <= 0:
            raise ValueError("调试输出 Run 租约必须大于 0 秒")
        now = datetime.now()
        raw = await DebugOutputRunModel.get_motor_collection().find_one_and_update(
            {
                "active": True,
                "desired_state": DebugOutputDesiredStateEnum.RUNNING.value,
                "$or": [
                    {"status": DebugOutputRunStatusEnum.PENDING.value},
                    {
                        "status": DebugOutputRunStatusEnum.RUNNING.value,
                        "lease_expires_at": {"$lte": now},
                    },
                ],
            },
            {
                "$set": {
                    "status": DebugOutputRunStatusEnum.RUNNING.value,
                    "worker_id": worker_id,
                    "lease_token": uuid.uuid4().hex,
                    "lease_expires_at": now + timedelta(seconds=lease_seconds),
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
        return DebugOutputRunModel.model_validate(raw) if raw else None

    @staticmethod
    async def renew_lease(
        run_id: str,
        worker_id: str,
        lease_token: str,
        *,
        lease_seconds: int = DEBUG_OUTPUT_RUNTIME_LEASE_SECONDS,
    ) -> bool:
        """仅允许当前有效租约持有者续租。"""
        now = datetime.now()
        result = await DebugOutputRunModel.get_motor_collection().update_one(
            {
                "_id": run_id,
                "active": True,
                "status": DebugOutputRunStatusEnum.RUNNING.value,
                "desired_state": DebugOutputDesiredStateEnum.RUNNING.value,
                "worker_id": worker_id,
                "lease_token": lease_token,
                "lease_expires_at": {"$gt": now},
            },
            {
                "$set": {
                    "lease_expires_at": now + timedelta(seconds=lease_seconds),
                    "last_heartbeat_at": now,
                    "updated_at": now,
                }
            },
        )
        return result.modified_count == 1

    @staticmethod
    async def get_owned(
        run_id: str,
        worker_id: str,
        lease_token: str,
    ) -> DebugOutputRunModel | None:
        """读取 Worker 仍持有有效租约的 Run。"""
        return await DebugOutputRunModel.find_one(
            {
                "_id": run_id,
                "active": True,
                "status": DebugOutputRunStatusEnum.RUNNING.value,
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
        status: DebugOutputRunStatusEnum,
        error_message: str | None = None,
    ) -> bool:
        """使用 fencing token 原子提交 Run 终态。"""
        if status not in {
            DebugOutputRunStatusEnum.COMPLETED,
            DebugOutputRunStatusEnum.FAILED,
            DebugOutputRunStatusEnum.CANCELLED,
        }:
            raise ValueError("finish 只能提交调试输出终态")
        now = datetime.now()
        result = await DebugOutputRunModel.get_motor_collection().update_one(
            {
                "_id": run_id,
                "active": True,
                "status": DebugOutputRunStatusEnum.RUNNING.value,
                "worker_id": worker_id,
                "lease_token": lease_token,
                "lease_expires_at": {"$gt": now},
            },
            {
                "$set": {
                    "active": False,
                    "status": status.value,
                    "lease_expires_at": None,
                    "error_message": error_message,
                    "finished_at": now,
                    "updated_at": now,
                }
            },
        )
        return result.modified_count == 1

    @staticmethod
    async def mark_paused(
        *,
        run_id: str,
        worker_id: str,
        lease_token: str,
    ) -> bool:
        """由当前租约持有者确认暂停并释放租约。"""
        now = datetime.now()
        result = await DebugOutputRunModel.get_motor_collection().update_one(
            {
                "_id": run_id,
                "active": True,
                "status": DebugOutputRunStatusEnum.RUNNING.value,
                "desired_state": DebugOutputDesiredStateEnum.PAUSED.value,
                "worker_id": worker_id,
                "lease_token": lease_token,
            },
            {
                "$set": {
                    "status": DebugOutputRunStatusEnum.PAUSED.value,
                    "lease_token": None,
                    "lease_expires_at": None,
                    "updated_at": now,
                }
            },
        )
        return result.modified_count == 1

    @staticmethod
    async def release_lease(
        *,
        run_id: str,
        worker_id: str,
        lease_token: str,
    ) -> bool:
        """进程退出时把持有的 Run 立即放回领取队列。"""
        now = datetime.now()
        result = await DebugOutputRunModel.get_motor_collection().update_one(
            {
                "_id": run_id,
                "active": True,
                "status": DebugOutputRunStatusEnum.RUNNING.value,
                "desired_state": DebugOutputDesiredStateEnum.RUNNING.value,
                "worker_id": worker_id,
                "lease_token": lease_token,
            },
            {
                "$set": {
                    "status": DebugOutputRunStatusEnum.PENDING.value,
                    "worker_id": None,
                    "lease_token": None,
                    "lease_expires_at": None,
                    "queued_at": now,
                    "updated_at": now,
                }
            },
        )
        return result.modified_count == 1

    @staticmethod
    async def record_reference_data(
        *,
        run_id: str,
        worker_id: str,
        lease_token: str,
        byte_count: int,
        truncated: bool,
    ) -> bool:
        """在有效租约下记录一条已经写日志并 ACK 的 DATA。"""
        result = await DebugOutputRunModel.get_motor_collection().update_one(
            {
                "_id": run_id,
                "active": True,
                "status": DebugOutputRunStatusEnum.RUNNING.value,
                "worker_id": worker_id,
                "lease_token": lease_token,
                "lease_expires_at": {"$gt": datetime.now()},
            },
            {
                "$inc": {
                    "logged_count": 1,
                    "logged_byte_count": max(0, byte_count),
                    "truncated_count": 1 if truncated else 0,
                },
                "$set": {"updated_at": datetime.now(), "error_message": None},
            },
        )
        return result.modified_count == 1

    @staticmethod
    async def record_control(
        *,
        run_id: str,
        worker_id: str,
        lease_token: str,
        control_key: str,
        status: str,
    ) -> tuple[DebugOutputRunModel | None, bool]:
        """首终态优先地记录生产者 EOS 或 ABORT。"""
        if status not in {"eos", "abort"}:
            raise ValueError("Reference 控制终态无效")
        field = (
            "received_eos_keys" if status == "eos" else "received_abort_keys"
        )
        update: dict[str, Any] = {
            "$addToSet": {field: control_key},
            "$set": {"updated_at": datetime.now(), "error_message": None},
        }
        if status == "abort":
            update["$inc"] = {"warning_count": 1}
        raw = await DebugOutputRunModel.get_motor_collection().find_one_and_update(
            {
                "_id": run_id,
                "active": True,
                "status": DebugOutputRunStatusEnum.RUNNING.value,
                "worker_id": worker_id,
                "lease_token": lease_token,
                "lease_expires_at": {"$gt": datetime.now()},
                "received_eos_keys": {"$ne": control_key},
                "received_abort_keys": {"$ne": control_key},
            },
            update,
            return_document=ReturnDocument.AFTER,
        )
        if raw:
            return DebugOutputRunModel.model_validate(raw), True
        current = await DebugOutputRuntimeService.get_owned(
            run_id,
            worker_id,
            lease_token,
        )
        if current is None:
            return None, False
        already_recorded = control_key in {
            *current.received_eos_keys,
            *current.received_abort_keys,
        }
        return (current, False) if already_recorded else (None, False)

    @staticmethod
    async def set_transient_error(
        *,
        run_id: str,
        worker_id: str,
        lease_token: str,
        error_message: str,
    ) -> bool:
        """记录瞬时异常但保持 Run 可恢复。"""
        result = await DebugOutputRunModel.get_motor_collection().update_one(
            {
                "_id": run_id,
                "active": True,
                "status": DebugOutputRunStatusEnum.RUNNING.value,
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
        return result.modified_count == 1

    @staticmethod
    async def settle_orphaned() -> int:
        """收敛已请求取消且不再被有效 Worker 持有的 Run。"""
        now = datetime.now()
        result = await DebugOutputRunModel.get_motor_collection().update_many(
            {
                "active": True,
                "desired_state": DebugOutputDesiredStateEnum.CANCELLED.value,
                "$or": [
                    {
                        "status": {
                            "$in": [
                                DebugOutputRunStatusEnum.PENDING.value,
                                DebugOutputRunStatusEnum.PAUSED.value,
                            ]
                        }
                    },
                    {"lease_expires_at": {"$lte": now}},
                    {"lease_expires_at": None},
                ],
            },
            {
                "$set": {
                    "active": False,
                    "status": DebugOutputRunStatusEnum.CANCELLED.value,
                    "error_message": "任务被取消",
                    "finished_at": now,
                    "updated_at": now,
                }
            },
        )
        return result.modified_count

    @staticmethod
    async def _write_debug_log(
        run: DebugOutputRunModel,
        *,
        event_key: str,
        message: str,
        fields: dict[str, Any],
        level: str = "DEBUG",
        truncated: bool = False,
    ) -> None:
        """限定三次尝试幂等写入一条调试日志。"""
        execution = await ActionNodeExecutionModel.find_one(
            {"_id": run.node_execution_id}
        )
        if execution is None:
            raise DebugOutputLogWriteError(
                f"调试输出执行记录不存在: {run.node_execution_id}"
            )
        last_error = "Elasticsearch 未确认写入"
        for attempt in range(1, DEBUG_OUTPUT_LOG_WRITE_ATTEMPTS + 1):
            try:
                accepted = await ActionLogService.ingest_debug_event(
                    execution,
                    event_key=event_key,
                    message=message,
                    fields=fields,
                    level=level,
                    truncated=truncated,
                    provider_run_id=run.id,
                )
                if accepted:
                    return
            except Exception as exc:
                last_error = str(exc)
            if attempt < DEBUG_OUTPUT_LOG_WRITE_ATTEMPTS:
                await asyncio.sleep(0.1 * attempt)
        raise DebugOutputLogWriteError(
            f"调试日志连续{DEBUG_OUTPUT_LOG_WRITE_ATTEMPTS}次写入失败: "
            f"{last_error}"
        )

    @staticmethod
    async def _fail_unfenced(run_id: str, error_message: str) -> bool:
        """由 Value 动态提交路径抢占式终止活动 Run。"""
        now = datetime.now()
        result = await DebugOutputRunModel.get_motor_collection().update_one(
            {"_id": run_id, "active": True},
            {
                "$set": {
                    "active": False,
                    "status": DebugOutputRunStatusEnum.FAILED.value,
                    "error_message": error_message,
                    "lease_expires_at": None,
                    "finished_at": now,
                    "updated_at": now,
                }
            },
        )
        return result.modified_count == 1

    @staticmethod
    def _same_submission(
        current: DebugOutputRunModel,
        requested: DebugOutputRunModel,
    ) -> bool:
        """判断重复执行键是否对应同一调试观察配置。"""
        return all(
            getattr(current, field) == getattr(requested, field)
            for field in (
                "action_id",
                "node_instance_id",
                "node_execution_id",
                "execution_key",
                "incoming_edges",
            )
        )

    @staticmethod
    def _require_edge(
        run: DebugOutputRunModel,
        edge_id: str,
        *,
        data_type: str | None = None,
    ) -> DebugOutputInputEdgeModel:
        """读取并校验 Run 内冻结的输入边。"""
        edge = next(
            (item for item in run.incoming_edges if item.edge_id == edge_id),
            None,
        )
        if edge is None:
            raise ValueError(f"调试输出 Run 不包含输入边: {edge_id}")
        if data_type is not None and edge.data_type != data_type:
            raise ValueError(
                f"调试输出边 {edge_id} 不是 {data_type} 类型"
            )
        return edge

    @staticmethod
    def _edge_fields(edge: DebugOutputInputEdgeModel) -> dict[str, Any]:
        """构造稳定的输入边日志元数据。"""
        fields: dict[str, Any] = {
            "edge_id": edge.edge_id,
            "data_type": edge.data_type,
            "source_node_id": edge.source_node_id,
            "source_port_id": edge.source_port_id,
            "target_port_id": edge.target_port_id,
        }
        if edge.value_slot:
            fields["value_slot"] = edge.value_slot
        if edge.reference_stream is not None:
            fields.update(
                {
                    "stream_id": edge.reference_stream.stream_id,
                    "queue_name": edge.reference_stream.queue_name,
                }
            )
        return fields

    @staticmethod
    def _event_key(kind: str, edge_id: str, identity: str) -> str:
        """生成受长度约束的稳定日志事件键。"""
        digest = hashlib.sha256(
            f"{kind}\x00{edge_id}\x00{identity}".encode("utf-8")
        ).hexdigest()
        return f"debug:{digest}"


class DebugOutputRuntimeWorker:
    """以租约和长驻 RabbitMQ 消费者执行调试输出 Run。"""

    def __init__(
        self,
        *,
        poll_seconds: float = DEBUG_OUTPUT_RUNTIME_POLL_SECONDS,
        lease_seconds: int = DEBUG_OUTPUT_RUNTIME_LEASE_SECONDS,
        heartbeat_seconds: float = DEBUG_OUTPUT_RUNTIME_HEARTBEAT_SECONDS,
        concurrency: int = DEBUG_OUTPUT_RUNTIME_CONCURRENCY,
    ) -> None:
        suffix = uuid.uuid4().hex[:10]
        self.worker_id = f"{socket.gethostname()}:{os.getpid()}:{suffix}"
        self.poll_seconds = max(0.05, poll_seconds)
        self.lease_seconds = max(1, lease_seconds)
        self.heartbeat_seconds = max(0.1, heartbeat_seconds)
        self.concurrency = max(1, concurrency)
        self._poll_task: asyncio.Task | None = None
        self._executions: dict[str, asyncio.Task] = {}
        self._stopping = False

    async def start(self) -> None:
        """启动领取循环并先收敛已取消的失租 Run。"""
        if self._poll_task is not None:
            return
        self._stopping = False
        await DebugOutputRuntimeService.settle_orphaned()
        self._poll_task = asyncio.create_task(
            self._poll_loop(),
            name=f"debug-output-worker:{self.worker_id}",
        )
        logger.info("调试输出 Runtime Worker 已启动: worker_id={}", self.worker_id)

    async def stop(self) -> None:
        """停止领取并释放本进程正在执行的 Run。"""
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
        logger.info("调试输出 Runtime Worker 已停止: worker_id={}", self.worker_id)

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
                    await DebugOutputRuntimeService.settle_orphaned()
                    last_reap_at = now
                claimed = False
                while len(self._executions) < self.concurrency and not self._stopping:
                    run = await DebugOutputRuntimeService.claim_next(
                        self.worker_id,
                        lease_seconds=self.lease_seconds,
                    )
                    if run is None:
                        break
                    claimed = True
                    task = asyncio.create_task(
                        self._execute_run(run),
                        name=f"debug-output-run:{run.id}",
                    )
                    task.add_done_callback(self._log_execution_result)
                    self._executions[run.id] = task
                if not claimed:
                    await asyncio.sleep(self.poll_seconds)
            except asyncio.CancelledError:
                raise
            except Exception:
                logger.exception("调试输出 Worker 领取循环异常，将继续重试")
                await asyncio.sleep(self.poll_seconds)

    @staticmethod
    def _log_execution_result(task: asyncio.Task) -> None:
        """记录未被主流程消化的后台任务异常。"""
        if task.cancelled():
            return
        error = task.exception()
        if error is not None:
            logger.error("调试输出 Run 异常退出: {}", error)

    async def _execute_run(self, run: DebugOutputRunModel) -> None:
        lease_token = str(run.lease_token or "")
        if not lease_token:
            logger.error("已领取调试输出 Run 缺少 lease_token: run_id={}", run.id)
            return
        work_task = asyncio.create_task(
            self._process_run(run, lease_token),
            name=f"debug-output-work:{run.id}",
        )
        monitor_task = asyncio.create_task(
            self._monitor_run(run.id, lease_token, work_task),
            name=f"debug-output-lease:{run.id}",
        )
        outcome: _RunOutcome | None = None
        monitor_result = _MonitorResult.WORK_COMPLETED
        try:
            outcome = await work_task
        except _RunAlreadySettled:
            return
        except DebugOutputLeaseLostError:
            return
        except asyncio.CancelledError:
            work_task.cancel()
            await asyncio.gather(work_task, return_exceptions=True)
            if self._stopping:
                await DebugOutputRuntimeService.release_lease(
                    run_id=run.id,
                    worker_id=self.worker_id,
                    lease_token=lease_token,
                )
                return
            monitor_result = await monitor_task
        except Exception as exc:
            logger.exception("调试输出 Run 执行失败: run_id={}", run.id)
            outcome = _RunOutcome(
                status=DebugOutputRunStatusEnum.FAILED,
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
            return
        current = await DebugOutputRuntimeService.get_owned(
            run.id,
            self.worker_id,
            lease_token,
        )
        if current is None:
            return
        if monitor_result == _MonitorResult.PAUSED:
            marked = await DebugOutputRuntimeService.mark_paused(
                run_id=run.id,
                worker_id=self.worker_id,
                lease_token=lease_token,
            )
            if not marked:
                await DebugOutputRuntimeService.release_lease(
                    run_id=run.id,
                    worker_id=self.worker_id,
                    lease_token=lease_token,
                )
            return
        if (
            monitor_result == _MonitorResult.CANCELLED
            or current.desired_state == DebugOutputDesiredStateEnum.CANCELLED
        ):
            outcome = _RunOutcome(
                status=DebugOutputRunStatusEnum.CANCELLED,
                error_message=current.requested_reason or "任务被取消",
            )
        if outcome is None:
            return
        committed = await DebugOutputRuntimeService.finish(
            run_id=run.id,
            worker_id=self.worker_id,
            lease_token=lease_token,
            status=outcome.status,
            error_message=outcome.error_message,
        )
        if not committed:
            logger.warning("调试输出 Run 终态提交被 fencing 拒绝: run_id={}", run.id)

    async def _process_run(
        self,
        run: DebugOutputRunModel,
        lease_token: str,
    ) -> _RunOutcome:
        consumers = {
            edge.edge_id: asyncio.create_task(
                self._consume_reference_edge(run, edge, lease_token),
                name=f"debug-output-stream:{run.id}:{edge.edge_id}",
            )
            for edge in run.incoming_edges
            if edge.data_type == "reference"
        }
        try:
            while True:
                current = await DebugOutputRuntimeService.get_owned(
                    run.id,
                    self.worker_id,
                    lease_token,
                )
                if current is None:
                    raise DebugOutputLeaseLostError("调试输出 Run 租约已失效")
                for edge_id, task in consumers.items():
                    if not task.done() or task.cancelled():
                        continue
                    error = task.exception()
                    if error is not None:
                        raise error
                    edge = DebugOutputRuntimeService._require_edge(
                        current,
                        edge_id,
                    )
                    if not self._edge_ended(current, edge):
                        raise RuntimeError(
                            f"Reference 调试消费者提前退出: {edge_id}"
                        )
                if self._all_inputs_ended(current):
                    break
                await asyncio.sleep(self.poll_seconds)
        finally:
            for task in consumers.values():
                if not task.done():
                    task.cancel()
            if consumers:
                await asyncio.gather(*consumers.values(), return_exceptions=True)

        current = await DebugOutputRuntimeService.get_owned(
            run.id,
            self.worker_id,
            lease_token,
        )
        if current is None:
            raise DebugOutputLeaseLostError("写入调试汇总前 Run 租约已失效")
        await DebugOutputRuntimeService._write_debug_log(
            current,
            event_key="debug:summary",
            message=json.dumps(
                {
                    "status": "completed",
                    "logged_count": current.logged_count,
                    "logged_byte_count": current.logged_byte_count,
                    "truncated_count": current.truncated_count,
                    "warning_count": current.warning_count,
                },
                ensure_ascii=False,
                indent=2,
            ),
            fields={
                "event": "summary",
                "logged_count": current.logged_count,
                "logged_byte_count": current.logged_byte_count,
                "truncated_count": current.truncated_count,
                "warning_count": current.warning_count,
            },
            level="WARNING" if current.warning_count else "DEBUG",
        )
        return _RunOutcome(status=DebugOutputRunStatusEnum.COMPLETED)

    async def _consume_reference_edge(
        self,
        run: DebugOutputRunModel,
        edge: DebugOutputInputEdgeModel,
        lease_token: str,
    ) -> None:
        """为一条 Reference 输入边维持独立长驻消费者。"""
        stream = edge.reference_stream
        if stream is None:
            raise ValueError("Reference 调试边缺少流描述符")
        while True:
            current = await DebugOutputRuntimeService.get_owned(
                run.id,
                self.worker_id,
                lease_token,
            )
            if current is None:
                raise DebugOutputLeaseLostError("调试输出 Run 租约已失效")
            if self._edge_ended(current, edge):
                return
            try:
                consumer = await rabbitmq.open_reference_consumer(
                    stream.queue_name,
                    prefetch_count=1,
                )
                async with consumer:
                    while True:
                        delivery = await consumer.receive()
                        if delivery is None:
                            break
                        ended = await self._process_reference_delivery(
                            current,
                            edge,
                            delivery,
                            lease_token,
                        )
                        if ended:
                            return
                        current = await DebugOutputRuntimeService.get_owned(
                            run.id,
                            self.worker_id,
                            lease_token,
                        )
                        if current is None:
                            raise DebugOutputLeaseLostError(
                                "调试输出 Run 租约已失效"
                            )
            except asyncio.CancelledError:
                raise
            except (_RunAlreadySettled, DebugOutputLeaseLostError):
                raise
            except Exception as exc:
                recorded = await DebugOutputRuntimeService.set_transient_error(
                    run_id=run.id,
                    worker_id=self.worker_id,
                    lease_token=lease_token,
                    error_message=f"读取 Reference 调试消息失败: {exc}",
                )
                if not recorded:
                    raise DebugOutputLeaseLostError(
                        "记录 Reference 瞬时异常时租约已失效"
                    ) from exc
                await asyncio.sleep(self.poll_seconds)

    async def _process_reference_delivery(
        self,
        run: DebugOutputRunModel,
        edge: DebugOutputInputEdgeModel,
        delivery,
        lease_token: str,
    ) -> bool:
        """日志成功后确认一条 Reference DATA 或控制帧。"""
        try:
            control_kind = rabbitmq.get_reference_control_kind(delivery.message)
            if control_kind is not None:
                return await self._process_reference_control(
                    run,
                    edge,
                    delivery,
                    lease_token,
                    control_kind,
                )

            preview = build_reference_preview(
                delivery.message.body,
                content_type=delivery.message.content_type,
                content_encoding=delivery.message.content_encoding,
            )
            raw_message_id = getattr(delivery.message, "message_id", None)
            message_id = str(raw_message_id) if raw_message_id else None
            event_identity = message_id or f"missing:{uuid.uuid4().hex}"
            fields = DebugOutputRuntimeService._edge_fields(edge)
            fields.update(
                {
                    "message_id": message_id,
                    "message_id_missing": message_id is None,
                    "content_type": delivery.message.content_type,
                    "content_encoding": delivery.message.content_encoding,
                    "content_kind": preview.content_kind,
                    "original_byte_count": preview.original_byte_count,
                    "sha256": preview.sha256,
                    "truncated": preview.truncated,
                }
            )
            try:
                await DebugOutputRuntimeService._write_debug_log(
                    run,
                    event_key=DebugOutputRuntimeService._event_key(
                        "reference-data",
                        edge.edge_id,
                        event_identity,
                    ),
                    message=preview.message,
                    fields=fields,
                    truncated=preview.truncated,
                )
            except DebugOutputLogWriteError as exc:
                if not getattr(delivery.message, "processed", False):
                    await delivery.nack(requeue=True)
                committed = await self._fail_owned(
                    run_id=run.id,
                    worker_id=self.worker_id,
                    lease_token=lease_token,
                    error_message=str(exc),
                )
                if not committed:
                    raise DebugOutputLeaseLostError(
                        "调试日志失败终态提交被 fencing 拒绝"
                    ) from exc
                raise _RunAlreadySettled(str(exc)) from exc

            renewed = await DebugOutputRuntimeService.renew_lease(
                run.id,
                self.worker_id,
                lease_token,
                lease_seconds=self.lease_seconds,
            )
            if not renewed:
                raise DebugOutputLeaseLostError(
                    "确认 Reference DATA 前调试输出 Run 租约已失效"
                )
            await delivery.ack()
            recorded = await DebugOutputRuntimeService.record_reference_data(
                run_id=run.id,
                worker_id=self.worker_id,
                lease_token=lease_token,
                byte_count=preview.original_byte_count,
                truncated=preview.truncated,
            )
            if not recorded:
                raise DebugOutputLeaseLostError(
                    "确认 Reference DATA 后调试输出 Run 租约已失效"
                )
            return False
        finally:
            await delivery.close()

    async def _process_reference_control(
        self,
        run: DebugOutputRunModel,
        edge: DebugOutputInputEdgeModel,
        delivery,
        lease_token: str,
        control_kind: str,
    ) -> bool:
        """首终态优先地收集 EOS/ABORT，ABORT 不影响其他输入。"""
        stream = edge.reference_stream
        if stream is None:
            raise ValueError("Reference 调试边缺少流描述符")
        stream_id, producer_id = rabbitmq.get_reference_control_identity(
            delivery.message
        )
        if stream_id != stream.stream_id or not producer_id:
            reason = "Reference 控制消息缺少有效流或生产者身份"
            await self._log_control_warning(
                run,
                edge,
                delivery,
                lease_token,
                reason,
            )
            recorded = await self._abort_owned_edge(
                run,
                edge.edge_id,
                lease_token,
            )
            await delivery.ack()
            return recorded
        if (
            stream.expected_producer_ids
            and producer_id not in stream.expected_producer_ids
        ):
            reason = f"Reference 控制消息来自未声明的生产者: {producer_id}"
            await self._log_control_warning(
                run,
                edge,
                delivery,
                lease_token,
                reason,
            )
            await self._record_owned_warning(run, lease_token)
            await delivery.ack()
            return False

        control_key = self._control_key(edge.edge_id, stream_id, producer_id)
        updated, _ = await DebugOutputRuntimeService.record_control(
            run_id=run.id,
            worker_id=self.worker_id,
            lease_token=lease_token,
            control_key=control_key,
            status=control_kind,
        )
        if updated is None:
            await delivery.nack(requeue=True)
            raise DebugOutputLeaseLostError(
                "记录 Reference 控制终态时调试输出 Run 租约已失效"
            )
        if (
            control_kind == "abort"
            and control_key in updated.received_abort_keys
        ):
            reason = self._control_reason(delivery.message.body) or (
                f"源流 {stream_id} 被生产者 {producer_id} 中止"
            )
            await self._log_control_warning(
                run,
                edge,
                delivery,
                lease_token,
                reason,
            )
        await delivery.ack()
        return self._edge_ended(updated, edge)

    async def _log_control_warning(
        self,
        run: DebugOutputRunModel,
        edge: DebugOutputInputEdgeModel,
        delivery,
        lease_token: str,
        reason: str,
    ) -> None:
        """幂等记录一条 Reference 控制异常。"""
        message_id = str(getattr(delivery.message, "message_id", "") or "")
        identity = message_id or uuid.uuid4().hex
        fields = DebugOutputRuntimeService._edge_fields(edge)
        fields.update({"reason": reason, "message_id": message_id or None})
        try:
            await DebugOutputRuntimeService._write_debug_log(
                run,
                event_key=DebugOutputRuntimeService._event_key(
                    "reference-control-warning",
                    edge.edge_id,
                    identity,
                ),
                message=reason,
                fields=fields,
                level="WARNING",
            )
        except DebugOutputLogWriteError as exc:
            if not getattr(delivery.message, "processed", False):
                await delivery.nack(requeue=True)
            committed = await self._fail_owned(
                run_id=run.id,
                worker_id=self.worker_id,
                lease_token=lease_token,
                error_message=str(exc),
            )
            if not committed:
                raise DebugOutputLeaseLostError(
                    "控制消息日志失败终态提交被 fencing 拒绝"
                ) from exc
            raise _RunAlreadySettled(str(exc)) from exc

    async def _record_owned_warning(
        self,
        run: DebugOutputRunModel,
        lease_token: str,
    ) -> None:
        """在有效租约下增加一条控制协议警告。"""
        result = await DebugOutputRunModel.get_motor_collection().update_one(
            {
                "_id": run.id,
                "active": True,
                "status": DebugOutputRunStatusEnum.RUNNING.value,
                "worker_id": self.worker_id,
                "lease_token": lease_token,
                "lease_expires_at": {"$gt": datetime.now()},
            },
            {
                "$inc": {"warning_count": 1},
                "$set": {"updated_at": datetime.now()},
            },
        )
        if result.modified_count != 1:
            raise DebugOutputLeaseLostError(
                "记录 Reference 控制警告时调试输出 Run 租约已失效"
            )

    async def _abort_owned_edge(
        self,
        run: DebugOutputRunModel,
        edge_id: str,
        lease_token: str,
    ) -> bool:
        """在有效租约下终止一条协议已损坏的输入边。"""
        result = await DebugOutputRunModel.get_motor_collection().update_one(
            {
                "_id": run.id,
                "active": True,
                "status": DebugOutputRunStatusEnum.RUNNING.value,
                "worker_id": self.worker_id,
                "lease_token": lease_token,
                "lease_expires_at": {"$gt": datetime.now()},
                "aborted_input_edge_ids": {"$ne": edge_id},
            },
            {
                "$addToSet": {"aborted_input_edge_ids": edge_id},
                "$inc": {"warning_count": 1},
                "$set": {"updated_at": datetime.now()},
            },
        )
        if result.modified_count != 1:
            current = await DebugOutputRuntimeService.get_owned(
                run.id,
                self.worker_id,
                lease_token,
            )
            if current is None:
                raise DebugOutputLeaseLostError(
                    "终止损坏输入边时调试输出 Run 租约已失效"
                )
        return True

    async def _monitor_run(
        self,
        run_id: str,
        lease_token: str,
        work_task: asyncio.Task,
    ) -> _MonitorResult:
        """续租并观察暂停、取消和失租。"""
        loop = asyncio.get_running_loop()
        next_heartbeat = loop.time() + self.heartbeat_seconds
        check_seconds = min(1.0, self.poll_seconds)
        while not work_task.done():
            await asyncio.sleep(check_seconds)
            current = await DebugOutputRuntimeService.get(run_id)
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
            if current.desired_state == DebugOutputDesiredStateEnum.CANCELLED:
                work_task.cancel()
                return _MonitorResult.CANCELLED
            if current.desired_state == DebugOutputDesiredStateEnum.PAUSED:
                work_task.cancel()
                return _MonitorResult.PAUSED
            if loop.time() >= next_heartbeat:
                renewed = await DebugOutputRuntimeService.renew_lease(
                    run_id,
                    self.worker_id,
                    lease_token,
                    lease_seconds=self.lease_seconds,
                )
                if not renewed:
                    work_task.cancel()
                    return _MonitorResult.LEASE_LOST
                next_heartbeat = loop.time() + self.heartbeat_seconds
        return _MonitorResult.WORK_COMPLETED

    @staticmethod
    async def _fail_owned(
        *,
        run_id: str,
        worker_id: str,
        lease_token: str,
        error_message: str,
    ) -> bool:
        """由有效租约持有者直接提交失败终态。"""
        return await DebugOutputRuntimeService.finish(
            run_id=run_id,
            worker_id=worker_id,
            lease_token=lease_token,
            status=DebugOutputRunStatusEnum.FAILED,
            error_message=error_message,
        )

    @staticmethod
    def _control_key(edge_id: str, stream_id: str, producer_id: str) -> str:
        """构造边、流和生产者维度的控制终态键。"""
        return _CONTROL_KEY_SEPARATOR.join((edge_id, stream_id, producer_id))

    @staticmethod
    def _received_producers(
        run: DebugOutputRunModel,
        edge: DebugOutputInputEdgeModel,
    ) -> set[str]:
        """返回指定边已收到首终态的生产者集合。"""
        stream = edge.reference_stream
        if stream is None:
            return set()
        prefix = _CONTROL_KEY_SEPARATOR.join(
            (edge.edge_id, stream.stream_id, "")
        )
        return {
            key[len(prefix) :]
            for key in {*run.received_eos_keys, *run.received_abort_keys}
            if key.startswith(prefix)
        }

    @staticmethod
    def _edge_ended(
        run: DebugOutputRunModel,
        edge: DebugOutputInputEdgeModel,
    ) -> bool:
        """判断一条 Value 或 Reference 输入边是否已经终止。"""
        if edge.edge_id in run.aborted_input_edge_ids:
            return True
        if edge.data_type == "value":
            return edge.edge_id in run.received_value_edge_ids
        stream = edge.reference_stream
        if stream is None:
            return False
        received = DebugOutputRuntimeWorker._received_producers(run, edge)
        if stream.expected_producer_ids:
            return set(stream.expected_producer_ids).issubset(received)
        return bool(received)

    @staticmethod
    def _all_inputs_ended(run: DebugOutputRunModel) -> bool:
        """判断 Run 的全部输入边是否均已交付或终止。"""
        return all(
            DebugOutputRuntimeWorker._edge_ended(run, edge)
            for edge in run.incoming_edges
        )

    @staticmethod
    def _control_reason(body: bytes) -> str | None:
        """尽力从控制帧载荷提取中止原因。"""
        try:
            payload = json.loads(body)
        except (TypeError, ValueError, UnicodeDecodeError):
            return None
        reason = payload.get("reason") if isinstance(payload, dict) else None
        return str(reason).strip() if reason else None


__all__ = [
    "DEBUG_OUTPUT_LOG_WRITE_ATTEMPTS",
    "DEBUG_OUTPUT_PREVIEW_BYTES",
    "DEBUG_OUTPUT_RUNTIME_CONCURRENCY",
    "DEBUG_OUTPUT_RUNTIME_HEARTBEAT_SECONDS",
    "DEBUG_OUTPUT_RUNTIME_LEASE_SECONDS",
    "DEBUG_OUTPUT_RUNTIME_POLL_SECONDS",
    "DebugOutputLeaseLostError",
    "DebugOutputLogWriteError",
    "DebugOutputPreview",
    "DebugOutputRuntimeService",
    "DebugOutputRuntimeWorker",
    "build_reference_preview",
    "build_value_preview",
]
