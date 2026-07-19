from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Query

import app.utils.status_codes as status_codes
from app.core.config import settings
from app.core.exceptions import BadRequestException, ForbiddenException
from app.core.system_config import (
    CONFIG_FIELD_MAP,
    ConfigConflictError,
    ConfigError,
    system_config_manager,
)
from app.dependencies.auth import get_current_user
from app.models.auth.user import UserModel
from app.schemas.response import ApiResponseSchema
from app.schemas.system_config import ConfigChangesRequest, ConfigVersionActionRequest
from app.service.system_config_history import SystemConfigHistoryService


router = APIRouter(prefix="/system/config", tags=["系统配置"])


def _raise_config_error(exc: ConfigError) -> None:
    if isinstance(exc, ConfigConflictError):
        from app.core.exceptions import ApiException

        raise ApiException(status_codes.CONFLICT_STATE, str(exc)) from exc
    raise BadRequestException(str(exc)) from exc


async def require_system_account(
    current_user: UserModel = Depends(get_current_user),
) -> UserModel:
    if current_user.username != settings.INIT_SYSTEM_USERNAME:
        raise ForbiddenException("系统配置仅允许内置系统账号访问")
    return current_user


def _mutation_response(state: dict[str, Any]) -> dict[str, Any]:
    return {
        "version": state["version"],
        "boot_id": system_config_manager.boot_id,
        "updated_at": state.get("updated_at"),
        "updated_by": state.get("updated_by"),
        "restart_required": bool(state.get("restart_required")),
        "pending_version": state.get("pending_version"),
        "pending_fields": list(state.get("pending_fields") or []),
        "history_sync_status": system_config_manager.public_config()[
            "history_sync_status"
        ],
    }


def _masked_change(change: Any) -> dict[str, Any]:
    meta = CONFIG_FIELD_MAP.get(change.key)
    return {
        "key": change.key,
        "label": meta.label if meta else change.key,
        "apply_mode": change.apply_mode,
        "sensitive": change.sensitive,
        "before": None if change.sensitive else change.before,
        "after": None if change.sensitive else change.after,
        "before_configured": change.before not in (None, ""),
        "after_configured": change.after not in (None, ""),
    }


def _history_item(document: Any, *, detail: bool = False) -> dict[str, Any]:
    item = {
        "version": document.version,
        "parent_version": document.parent_version,
        "operation": document.operation,
        "status": document.status,
        "changed_fields": [change.key for change in document.changes],
        "change_count": len(document.changes),
        "created_by": document.created_by,
        "created_at": document.created_at.isoformat(),
        "applied_at": document.applied_at.isoformat() if document.applied_at else None,
        "restored_from_version": document.restored_from_version,
        "message": document.message,
    }
    if detail:
        item["changes"] = [_masked_change(change) for change in document.changes]
        restore_modes = system_config_manager.restore_modes(document.snapshot)
        item["restore_runtime_fields"] = restore_modes["runtime"]
        item["restore_restart_fields"] = restore_modes["restart"]
    return item


@router.get("", response_model=ApiResponseSchema[dict[str, Any]], summary="读取系统配置")
async def get_system_config(_: UserModel = Depends(require_system_account)):
    return ApiResponseSchema.success(data=system_config_manager.public_config())


@router.get("/status", response_model=ApiResponseSchema[dict[str, Any]], summary="读取配置应用状态")
async def get_system_config_status(_: UserModel = Depends(require_system_account)):
    data = system_config_manager.public_config()
    data.pop("fields", None)
    data.pop("groups", None)
    return ApiResponseSchema.success(data=data)


@router.post("/preview", response_model=ApiResponseSchema[dict[str, Any]], summary="预览系统配置变更")
async def preview_system_config(
    request: ConfigChangesRequest,
    _: UserModel = Depends(require_system_account),
):
    state = system_config_manager.state()
    if int(state["version"]) != request.expected_version:
        _raise_config_error(ConfigConflictError("配置版本已变化，请刷新后重试"))
    try:
        normalized, _, modes = system_config_manager.preview(request.changes)
    except ConfigError as exc:
        _raise_config_error(exc)
    warnings: list[str] = []
    if modes["restart"]:
        warnings.append("这些配置保存后将在下次服务重启时生效")
    return ApiResponseSchema.success(
        data={
            "changes": [
                {
                    "key": key,
                    "apply_mode": "restart" if key in modes["restart"] else "runtime",
                }
                for key in normalized
            ],
            "runtime_fields": modes["runtime"],
            "restart_fields": modes["restart"],
            "requires_restart": bool(modes["restart"]),
            "warnings": warnings,
        }
    )


@router.patch("/runtime", response_model=ApiResponseSchema[dict[str, Any]], summary="应用运行时系统配置")
async def apply_runtime_system_config(
    request: ConfigChangesRequest,
    current_user: UserModel = Depends(require_system_account),
):
    try:
        state = system_config_manager.apply_runtime(
            request.changes, request.expected_version, current_user.username
        )
    except ConfigError as exc:
        _raise_config_error(exc)
    await SystemConfigHistoryService.flush_outbox(system_config_manager)
    return ApiResponseSchema.success(
        data=_mutation_response(state),
        message="运行时配置已生效",
    )


@router.patch("/pending", response_model=ApiResponseSchema[dict[str, Any]], summary="保存待重启系统配置")
async def stage_pending_system_config(
    request: ConfigChangesRequest,
    current_user: UserModel = Depends(require_system_account),
):
    try:
        state = system_config_manager.stage_pending(
            request.changes, request.expected_version, current_user.username
        )
    except ConfigError as exc:
        _raise_config_error(exc)
    await SystemConfigHistoryService.flush_outbox(system_config_manager)
    return ApiResponseSchema.success(
        data=_mutation_response(state),
        message="配置已保存，将在下次服务重启后生效",
    )


@router.post("/pending/cancel", response_model=ApiResponseSchema[dict[str, Any]], summary="取消待重启系统配置")
async def cancel_pending_system_config(
    request: ConfigVersionActionRequest,
    current_user: UserModel = Depends(require_system_account),
):
    if not request.confirmed:
        raise BadRequestException("必须确认后才能取消待重启配置")
    try:
        state = system_config_manager.cancel_pending(
            request.expected_version, current_user.username
        )
    except ConfigError as exc:
        _raise_config_error(exc)
    await SystemConfigHistoryService.flush_outbox(system_config_manager)
    return ApiResponseSchema.success(
        data=_mutation_response(state), message="待重启配置已取消"
    )


@router.get("/history", response_model=ApiResponseSchema[dict[str, Any]], summary="读取系统配置历史")
async def list_system_config_history(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    _: UserModel = Depends(require_system_account),
):
    rows, total = await SystemConfigHistoryService.list_versions(page, page_size)
    return ApiResponseSchema.success(
        data={
            "items": [_history_item(row) for row in rows],
            "total": total,
            "page": page,
            "page_size": page_size,
        }
    )


@router.get("/history/{version}", response_model=ApiResponseSchema[dict[str, Any]], summary="读取系统配置历史详情")
async def get_system_config_history(
    version: int,
    _: UserModel = Depends(require_system_account),
):
    document = await SystemConfigHistoryService.get_version(version)
    if document is None:
        raise BadRequestException("配置历史版本不存在")
    return ApiResponseSchema.success(data=_history_item(document, detail=True))


@router.post("/history/{version}/restore", response_model=ApiResponseSchema[dict[str, Any]], summary="还原系统配置历史版本")
async def restore_system_config_history(
    version: int,
    request: ConfigVersionActionRequest,
    current_user: UserModel = Depends(require_system_account),
):
    if not request.confirmed:
        raise BadRequestException("必须确认后才能还原配置版本")
    document = await SystemConfigHistoryService.get_version(version)
    if document is None:
        raise BadRequestException("配置历史版本不存在")
    try:
        state = system_config_manager.restore_snapshot(
            document.snapshot,
            version,
            request.expected_version,
            current_user.username,
        )
    except ConfigError as exc:
        _raise_config_error(exc)
    await SystemConfigHistoryService.flush_outbox(system_config_manager)
    return ApiResponseSchema.success(
        data=_mutation_response(state), message=f"已还原配置版本 v{version}"
    )
