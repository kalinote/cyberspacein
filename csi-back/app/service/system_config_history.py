from __future__ import annotations

import hashlib
import json
from datetime import datetime
from typing import Any

from beanie.operators import Set
from loguru import logger
from pymongo.errors import DuplicateKeyError

from app.core.system_config import (
    CONFIG_FIELDS,
    ConfigConflictError,
    ConfigError,
)
from app.models.system_config import SystemConfigVersionModel


logger = logger.bind(name=__name__)


class HistoryVersionConflictError(RuntimeError):
    pass


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
                raise HistoryVersionConflictError("配置历史版本内容冲突")
            return
        try:
            await SystemConfigVersionModel(**payload).insert()
        except DuplicateKeyError as exc:
            raise HistoryVersionConflictError("配置历史版本号或事件编号冲突") from exc

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
        except HistoryVersionConflictError as exc:
            manager.set_history_sync_status("conflict")
            logger.warning("系统配置历史同步冲突: {}", str(exc))
            return "conflict"
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
    async def latest_version() -> SystemConfigVersionModel | None:
        latest_rows = await SystemConfigVersionModel.find_all().sort(
            -SystemConfigVersionModel.version
        ).limit(1).to_list()
        return latest_rows[0] if latest_rows else None

    @staticmethod
    def _reconcile_latest(
        manager: Any, latest: SystemConfigVersionModel | None
    ) -> str:
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
        if latest.snapshot_checksum != manager._checksum(dict(latest.snapshot or {})):
            manager.set_history_sync_status("conflict")
            return "conflict"
        if (
            latest.status != "rolled_back"
            and latest.snapshot_checksum != manager.desired_snapshot_checksum()
        ):
            manager.set_history_sync_status("conflict")
            return "conflict"
        manager.set_history_sync_status("ok")
        return "ok"

    @classmethod
    async def reconcile(cls, manager: Any) -> str:
        return cls._reconcile_latest(manager, await cls.latest_version())

    @staticmethod
    def _coordination_token(
        source: dict[str, Any],
        latest: SystemConfigVersionModel,
        database_checksum: str,
    ) -> str:
        payload = {
            "file_signature": source["signature"],
            "database_version": latest.version,
            "database_event_id": latest.event_id,
            "database_status": latest.status,
            "database_stored_checksum": latest.snapshot_checksum,
            "database_actual_checksum": database_checksum,
        }
        encoded = json.dumps(
            payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")
        ).encode("utf-8")
        return hashlib.sha256(encoded).hexdigest()

    @classmethod
    async def _coordination_context(cls, manager: Any) -> dict[str, Any]:
        """读取并归一化文件与 MongoDB 快照，构造协调预览上下文。"""
        latest = await cls.latest_version()
        if cls._reconcile_latest(manager, latest) != "conflict" or latest is None:
            raise ConfigConflictError("当前不存在需要强制同步的存储冲突")

        source = manager.coordination_source()
        file_snapshot = source["desired_snapshot"]
        database_snapshot = dict(latest.snapshot or {})
        editable_fields = [
            meta for meta in CONFIG_FIELDS if meta.apply_mode != "readonly"
        ]
        editable_keys = {meta.key for meta in editable_fields}
        unknown_keys = sorted(set(database_snapshot) - editable_keys)
        database_checksum = manager._checksum(database_snapshot)
        warnings: list[str] = []
        if unknown_keys:
            warnings.append(
                f"MongoDB 快照包含 {len(unknown_keys)} 个当前版本未知字段，"
                "生成新版本时将忽略"
            )
        missing_keys = [
            meta.key for meta in editable_fields if meta.key not in database_snapshot
        ]
        if missing_keys:
            warnings.append(
                f"MongoDB 快照缺少 {len(missing_keys)} 个当前配置字段，"
                "这些字段必须采用文件侧值"
            )
        if source["outbox_ids"]:
            warnings.append(
                f"文件中有 {len(source['outbox_ids'])} 条冲突 outbox 事件，"
                "提交后将由协调版本取代"
            )
        if latest.snapshot_checksum != database_checksum:
            warnings.append("MongoDB 快照内容与其历史校验和不一致")

        file_display: dict[str, Any] = {}
        database_display: dict[str, Any] = {}
        differences: list[dict[str, Any]] = []
        fixed_impact = {"runtime": [], "restart": []}
        for meta in editable_fields:
            file_value = file_snapshot[meta.key]
            active_value = source["active_snapshot"][meta.key]
            database_available = meta.key in database_snapshot
            database_value = database_snapshot.get(meta.key)
            equal = database_available and file_value == database_value
            file_configured = file_value not in (None, "")
            database_configured = (
                database_available and database_value not in (None, "")
            )
            if meta.sensitive:
                if equal:
                    display_value = "已配置（两侧一致）" if file_configured else "未配置"
                    file_display[meta.key] = display_value
                    database_display[meta.key] = display_value
                else:
                    file_display[meta.key] = (
                        "已配置（文件侧敏感值）" if file_configured else "未配置"
                    )
                    database_display[meta.key] = (
                        "数据库缺失"
                        if not database_available
                        else "已配置（数据库侧敏感值）"
                        if database_configured
                        else "未配置"
                    )
            else:
                file_display[meta.key] = file_value
                database_display[meta.key] = (
                    database_value if database_available else "数据库缺失"
                )
            if equal:
                if active_value != file_value:
                    fixed_impact[meta.apply_mode].append(meta.key)
                continue
            differences.append(
                {
                    "key": meta.key,
                    "label": meta.label,
                    "group": meta.group,
                    "apply_mode": meta.apply_mode,
                    "value_type": meta.value_type,
                    "sensitive": meta.sensitive,
                    "file_value": None if meta.sensitive else file_value,
                    "database_value": (
                        None
                        if meta.sensitive or not database_available
                        else database_value
                    ),
                    "file_configured": file_configured,
                    "database_configured": database_configured,
                    "database_available": database_available,
                    "file_changes_active": active_value != file_value,
                    "database_changes_active": (
                        database_available and active_value != database_value
                    ),
                }
            )

        token = cls._coordination_token(source, latest, database_checksum)
        proposed_version = max(int(source["version"]), int(latest.version)) + 1
        public = {
            "coordination_token": token,
            "proposed_version": proposed_version,
            "file": {
                "version": int(source["version"]),
                "active_checksum": source["active_checksum"],
                "desired_checksum": source["desired_checksum"],
                "restart_required": source["restart_required"],
                "pending_version": source["pending_version"],
                "pending_status": source["pending_status"],
                "outbox_count": len(source["outbox_ids"]),
                "display_snapshot": file_display,
            },
            "database": {
                "version": int(latest.version),
                "event_id": latest.event_id,
                "snapshot_checksum": latest.snapshot_checksum,
                "actual_snapshot_checksum": database_checksum,
                "status": latest.status,
                "operation": latest.operation,
                "created_at": latest.created_at.isoformat(),
                "display_snapshot": database_display,
            },
            "differences": differences,
            "fixed_impact": fixed_impact,
            "warnings": warnings,
        }
        return {
            "public": public,
            "source": source,
            "latest": latest,
            "database_snapshot": {
                key: value
                for key, value in database_snapshot.items()
                if key in editable_keys
            },
            "database_checksum": database_checksum,
        }

    @classmethod
    async def coordination_preview(cls, manager: Any) -> dict[str, Any]:
        context = await cls._coordination_context(manager)
        return context["public"]

    @classmethod
    async def commit_coordination(
        cls,
        manager: Any,
        *,
        coordination_token: str,
        resolutions: dict[str, str],
        actor: str,
    ) -> dict[str, Any]:
        """校验协调选择并创建同时覆盖文件与 MongoDB 的新配置版本。"""
        context = await cls._coordination_context(manager)
        public = context["public"]
        if coordination_token != public["coordination_token"]:
            raise ConfigConflictError("存储状态已变化，请重新加载对比")

        differences = {item["key"]: item for item in public["differences"]}
        if set(resolutions) != set(differences):
            missing = sorted(set(differences) - set(resolutions))
            extra = sorted(set(resolutions) - set(differences))
            details = []
            if missing:
                details.append(f"尚未选择 {len(missing)} 个差异字段")
            if extra:
                details.append(f"包含 {len(extra)} 个非差异字段")
            raise ConfigError("；".join(details))
        for key, source_name in resolutions.items():
            if source_name not in {"file", "database"}:
                raise ConfigError(f"配置项 {key} 的协调来源无效")
            if source_name == "database" and not differences[key]["database_available"]:
                raise ConfigError(f"MongoDB 缺少配置项 {key}，必须采用文件侧值")

        merged_snapshot = dict(context["source"]["desired_snapshot"])
        for key, source_name in resolutions.items():
            if source_name == "database":
                merged_snapshot[key] = context["database_snapshot"][key]

        result = manager.apply_storage_coordination(
            merged_snapshot=merged_snapshot,
            database_snapshot=context["database_snapshot"],
            database_version=int(context["latest"].version),
            database_checksum=context["database_checksum"],
            proposed_version=int(public["proposed_version"]),
            expected_file_signature=context["source"]["signature"],
            resolutions=resolutions,
            actor=actor,
        )
        result["history_sync_status"] = await cls.flush_outbox(manager)
        return result

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
