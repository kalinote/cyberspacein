from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from starlette.testclient import TestClient

from app.api.v1.endpoints import system_config as config_ep
from app.core.config import settings
from app.core.exceptions import ForbiddenException
from app.dependencies.auth import get_current_user
from app.models.auth.user import UserModel


def _user(username: str) -> UserModel:
    return UserModel.model_construct(
        id=f"user-{username}",
        username=username,
        display_name=username,
        password_hash="hash",
        enabled=True,
        is_system=username == settings.INIT_SYSTEM_USERNAME,
    )


def _client(username: str | None = None) -> TestClient:
    app = FastAPI()
    app.dependency_overrides[get_current_user] = lambda: _user(
        username or settings.INIT_SYSTEM_USERNAME
    )
    app.include_router(config_ep.router, prefix="/api/v1")
    return TestClient(app)


def test_get_system_config_returns_manager_payload(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        config_ep.system_config_manager,
        "public_config",
        lambda: {"version": 3, "fields": [], "groups": []},
    )

    body = _client().get("/api/v1/system/config").json()

    assert body["code"] == 0
    assert body["data"]["version"] == 3


@pytest.mark.asyncio
async def test_non_system_account_is_rejected() -> None:
    with pytest.raises(ForbiddenException):
        await config_ep.require_system_account(_user("ordinary-admin"))


def test_preview_reports_pending_restart_warning(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(config_ep.system_config_manager, "state", lambda: {"version": 2})
    monkeypatch.setattr(
        config_ep.system_config_manager,
        "preview",
        lambda changes: (changes, object(), {"runtime": [], "restart": ["APP_NAME"]}),
    )

    body = _client().post(
        "/api/v1/system/config/preview",
        json={"expected_version": 2, "changes": {"APP_NAME": "new-name"}},
    ).json()

    assert body["data"]["requires_restart"] is True
    assert "下次服务重启" in body["data"]["warnings"][0]
    assert "impact" not in body["data"]


def test_runtime_apply_passes_actor_and_version(monkeypatch: pytest.MonkeyPatch) -> None:
    captured = {}

    def apply(changes, version, actor):
        captured.update(changes=changes, version=version, actor=actor)
        return {
            "version": version + 1,
            "updated_at": "2026-01-01T00:00:00+00:00",
            "updated_by": actor,
            "restart_required": False,
            "pending_version": None,
            "pending_fields": [],
        }

    async def flush(_):
        return "ok"

    monkeypatch.setattr(config_ep.system_config_manager, "apply_runtime", apply)
    monkeypatch.setattr(config_ep.SystemConfigHistoryService, "flush_outbox", flush)
    monkeypatch.setattr(
        config_ep.system_config_manager,
        "public_config",
        lambda: {"history_sync_status": "ok"},
    )
    body = _client().patch(
        "/api/v1/system/config/runtime",
        json={"expected_version": 4, "changes": {"RRF_K": 90}},
    ).json()

    assert body["code"] == 0
    assert captured == {
        "changes": {"RRF_K": 90},
        "version": 4,
        "actor": settings.INIT_SYSTEM_USERNAME,
    }


def test_pending_save_does_not_request_process_restart(monkeypatch: pytest.MonkeyPatch) -> None:
    captured = {}

    def stage(changes, version, actor):
        captured.update(changes=changes, version=version, actor=actor)
        return {
            "version": version + 1,
            "updated_at": "2026-01-01T00:00:00+00:00",
            "updated_by": actor,
            "restart_required": True,
            "pending_version": version + 1,
            "pending_fields": ["APP_NAME"],
        }

    async def flush(_):
        return "ok"

    monkeypatch.setattr(config_ep.system_config_manager, "stage_pending", stage)
    monkeypatch.setattr(config_ep.SystemConfigHistoryService, "flush_outbox", flush)
    monkeypatch.setattr(
        config_ep.system_config_manager,
        "public_config",
        lambda: {"history_sync_status": "ok"},
    )

    body = _client().patch(
        "/api/v1/system/config/pending",
        json={"expected_version": 2, "changes": {"APP_NAME": "new-name"}},
    ).json()

    assert body["code"] == 0
    assert body["data"]["restart_required"] is True
    assert body["data"]["pending_fields"] == ["APP_NAME"]
    assert captured["actor"] == settings.INIT_SYSTEM_USERNAME


def test_history_detail_masks_sensitive_values(monkeypatch: pytest.MonkeyPatch) -> None:
    document = SimpleNamespace(
        version=3,
        parent_version=2,
        operation="runtime_update",
        status="applied",
        changes=[SimpleNamespace(
            key="CRAWLAB_TOKEN",
            apply_mode="runtime",
            before="old-secret",
            after="new-secret",
            sensitive=True,
        )],
        created_by="system",
        created_at=datetime.now(timezone.utc),
        applied_at=None,
        restored_from_version=None,
        message=None,
        snapshot={"CRAWLAB_TOKEN": "new-secret"},
    )
    monkeypatch.setattr(
        config_ep.system_config_manager,
        "restore_modes",
        lambda _: {
            "runtime": ["CRAWLAB_TOKEN"], "restart": []
        },
    )
    payload = config_ep._history_item(document, detail=True)

    assert payload["changes"][0]["before"] is None
    assert payload["changes"][0]["after"] is None
    assert payload["changes"][0]["before_configured"] is True
    assert "old-secret" not in str(payload)
    assert "new-secret" not in str(payload)


def test_coordination_preview_returns_service_payload(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def preview(_):
        return {
            "coordination_token": "a" * 64,
            "proposed_version": 6,
            "differences": [],
        }

    monkeypatch.setattr(
        config_ep.SystemConfigHistoryService, "coordination_preview", preview
    )

    body = _client().get("/api/v1/system/config/coordination/preview").json()

    assert body["code"] == 0
    assert body["data"]["proposed_version"] == 6


def test_coordination_commit_returns_apply_impact(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def commit(_, **kwargs):
        assert kwargs["coordination_token"] == "a" * 64
        assert kwargs["resolutions"] == {"RRF_K": "database"}
        return {
            "state": {
                "version": 6,
                "updated_at": "2026-01-01T00:00:00+00:00",
                "updated_by": "system",
                "restart_required": True,
                "pending_version": 6,
                "pending_fields": ["APP_NAME"],
            },
            "history_sync_status": "ok",
            "runtime_fields": ["RRF_K"],
            "restart_fields": ["APP_NAME"],
            "source_file_version": 0,
            "source_database_version": 5,
        }

    monkeypatch.setattr(
        config_ep.SystemConfigHistoryService, "commit_coordination", commit
    )
    monkeypatch.setattr(
        config_ep.system_config_manager,
        "public_config",
        lambda: {"history_sync_status": "ok"},
    )

    body = _client().post(
        "/api/v1/system/config/coordination/commit",
        json={
            "coordination_token": "a" * 64,
            "resolutions": {"RRF_K": "database"},
            "confirmed": True,
        },
    ).json()

    assert body["code"] == 0
    assert body["data"]["version"] == 6
    assert body["data"]["resolved_from"] == {
        "file_version": 0,
        "database_version": 5,
    }
