from __future__ import annotations

from datetime import datetime
from typing import Any

from beanie.operators import Set
from loguru import logger

from app.models.system_config import SystemConfigVersionModel


logger = logger.bind(name=__name__)


class SystemConfigHistoryService:
    @staticmethod
    async def _apply_event(event: dict[str, Any]) -> None:
        if event.get("kind") == "status":
            version = int(event["version"])
            values: dict[str, Any] = {
                "status": event["status"],
                "message": event.get("message"),
            }
            if event.get("applied_at"):
                values["applied_at"] = datetime.fromisoformat(event["applied_at"])
            await SystemConfigVersionModel.find_one(
                SystemConfigVersionModel.version == version
            ).update(Set(values))
            return

        payload = dict(event["payload"])
        payload["created_at"] = datetime.fromisoformat(payload["created_at"])
        if payload.get("applied_at"):
            payload["applied_at"] = datetime.fromisoformat(payload["applied_at"])
        existing = await SystemConfigVersionModel.find_one(
            SystemConfigVersionModel.version == payload["version"]
        )
        if existing:
            if existing.event_id != payload["event_id"]:
                raise RuntimeError("配置历史版本内容冲突")
            return
        await SystemConfigVersionModel(**payload).insert()

    @classmethod
    async def flush_outbox(cls, manager: Any) -> str:
        try:
            events = manager.outbox()
            if not events:
                return await cls.reconcile(manager)
            acknowledged: list[str] = []
            for event in events:
                await cls._apply_event(event)
                acknowledged.append(event["outbox_id"])
            manager.ack_outbox(acknowledged)
            return await cls.reconcile(manager)
        except Exception as exc:
            manager.set_history_sync_status("pending")
            logger.warning("系统配置历史同步待重试: {}", type(exc).__name__)
            return "pending"

    @classmethod
    async def ensure_baseline(cls, manager: Any) -> str:
        try:
            count = await SystemConfigVersionModel.find_all().count()
            if count == 0:
                await cls._apply_event(manager.baseline_history_event())
            return await cls.reconcile(manager)
        except Exception as exc:
            manager.set_history_sync_status("pending")
            logger.warning("系统配置历史基线同步待重试: {}", type(exc).__name__)
            return "pending"

    @staticmethod
    async def reconcile(manager: Any) -> str:
        latest_rows = await SystemConfigVersionModel.find_all().sort(
            -SystemConfigVersionModel.version
        ).limit(1).to_list()
        latest = latest_rows[0] if latest_rows else None
        if latest is None:
            manager.set_history_sync_status("pending")
            return "pending"
        file_version = manager.state()["version"]
        if latest.version > file_version:
            manager.set_history_sync_status("conflict")
            return "conflict"
        if latest.version < file_version:
            status = "pending" if manager.outbox() else "conflict"
            manager.set_history_sync_status(status)
            return status
        if (
            latest.status != "rolled_back"
            and latest.snapshot_checksum != manager.desired_snapshot_checksum()
        ):
            manager.set_history_sync_status("conflict")
            return "conflict"
        manager.set_history_sync_status("ok")
        return "ok"

    @staticmethod
    async def list_versions(page: int, page_size: int) -> tuple[list[SystemConfigVersionModel], int]:
        total = await SystemConfigVersionModel.find_all().count()
        rows = await SystemConfigVersionModel.find_all().sort(
            -SystemConfigVersionModel.version
        ).skip((page - 1) * page_size).limit(page_size).to_list()
        return rows, total

    @staticmethod
    async def get_version(version: int) -> SystemConfigVersionModel | None:
        return await SystemConfigVersionModel.find_one(
            SystemConfigVersionModel.version == version
        )
