from __future__ import annotations

import json

import pytest

from app.core.config import Settings, SettingsProxy
from app.core.system_config import (
    CONFIG_FIELD_MAP,
    ConfigConflictError,
    ConfigError,
    SystemConfigManager,
)
from tests.conftest import apply_minimal_settings_env


def make_manager(monkeypatch: pytest.MonkeyPatch, path) -> tuple[SystemConfigManager, SettingsProxy]:
    monkeypatch.setenv("CSI_SYSTEM_CONFIG_FILE", str(path))
    manager = SystemConfigManager()
    proxy = SettingsProxy(manager.bootstrap(Settings))
    manager.bind_settings(proxy)
    return manager, proxy


def test_registry_covers_every_settings_field() -> None:
    assert set(CONFIG_FIELD_MAP) == set(Settings.model_fields)


def test_runtime_update_is_persisted_and_swapped(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    apply_minimal_settings_env(monkeypatch)
    manager, proxy = make_manager(monkeypatch, tmp_path / "config.json")

    state = manager.apply_runtime({"RRF_K": 88}, 0, "system")

    assert state["version"] == 1
    assert proxy.RRF_K == 88
    saved = json.loads((tmp_path / "config.json").read_text(encoding="utf-8"))
    assert saved["active"] == {"RRF_K": 88}
    assert saved["desired"] == {"RRF_K": 88}
    assert saved["schema_version"] == 2
    assert saved["restart_required"] is False


def test_readonly_and_blank_secret_changes_are_rejected(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    apply_minimal_settings_env(monkeypatch)
    manager, _ = make_manager(monkeypatch, tmp_path / "config.json")

    with pytest.raises(ConfigError, match="不允许"):
        manager.preview({"MONGODB_URL": "mongodb://other"})
    with pytest.raises(ConfigError, match="没有可应用"):
        manager.preview({"CRAWLAB_TOKEN": ""})


def test_sensitive_values_are_never_returned(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    apply_minimal_settings_env(monkeypatch)
    manager, _ = make_manager(monkeypatch, tmp_path / "config.json")

    fields = {item["key"]: item for item in manager.public_config()["fields"]}

    assert fields["CRAWLAB_TOKEN"]["value"] is None
    assert fields["CRAWLAB_TOKEN"]["configured"] is True
    assert fields["MARIADB_URL"]["value"] is None


def test_pending_config_commits_after_successful_boot(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    apply_minimal_settings_env(monkeypatch)
    path = tmp_path / "config.json"
    first, _ = make_manager(monkeypatch, path)
    first.stage_pending({"APP_NAME": "changed"}, 0, "system")

    staged = first.state()
    assert staged["restart_required"] is True
    assert staged["active"] == {}
    assert staged["desired"] == {"APP_NAME": "changed"}

    second, proxy = make_manager(monkeypatch, path)
    assert proxy.APP_NAME == "changed"
    second.commit_bootstrap()

    state = second.state()
    assert state["version"] == 1
    assert state["restart_required"] is False
    assert state["active"] == {"APP_NAME": "changed"}


def test_attempted_pending_config_rolls_back_on_next_boot(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    apply_minimal_settings_env(monkeypatch)
    path = tmp_path / "config.json"
    first, _ = make_manager(monkeypatch, path)
    first.stage_pending({"APP_NAME": "broken"}, 0, "system")

    attempted, attempted_proxy = make_manager(monkeypatch, path)
    assert attempted_proxy.APP_NAME == "broken"
    del attempted

    recovered, recovered_proxy = make_manager(monkeypatch, path)
    assert recovered_proxy.APP_NAME == "test-app"
    assert recovered.state()["last_result"]["status"] == "rolled_back"


def test_runtime_update_is_preserved_while_restart_is_pending(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    apply_minimal_settings_env(monkeypatch)
    manager, proxy = make_manager(monkeypatch, tmp_path / "config.json")

    manager.stage_pending({"APP_NAME": "next-name"}, 0, "system")
    state = manager.apply_runtime({"RRF_K": 91}, 1, "system")

    assert proxy.RRF_K == 91
    assert proxy.APP_NAME == "test-app"
    assert state["active"] == {"RRF_K": 91}
    assert state["desired"] == {"APP_NAME": "next-name", "RRF_K": 91}
    assert state["restart_required"] is True
    assert state["version"] == 2


def test_cancel_pending_creates_version_and_keeps_runtime(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    apply_minimal_settings_env(monkeypatch)
    manager, proxy = make_manager(monkeypatch, tmp_path / "config.json")
    manager.apply_runtime({"RRF_K": 92}, 0, "system")
    manager.stage_pending({"APP_NAME": "next-name"}, 1, "system")

    state = manager.cancel_pending(2, "system")

    assert state["version"] == 3
    assert state["restart_required"] is False
    assert state["active"] == {"RRF_K": 92}
    assert state["desired"] == {"RRF_K": 92}
    assert proxy.RRF_K == 92


def test_v1_state_is_migrated_without_losing_pending(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    apply_minimal_settings_env(monkeypatch)
    path = tmp_path / "config.json"
    path.write_text(json.dumps({
        "schema_version": 1,
        "version": 1,
        "active": {"RRF_K": 80},
        "pending": {
            "version": 2,
            "overrides": {"RRF_K": 80, "APP_NAME": "next-name"},
            "attempted": False,
        },
        "updated_by": "system",
    }), encoding="utf-8")

    manager, proxy = make_manager(monkeypatch, path)
    state = manager.state()

    assert state["schema_version"] == 2
    assert state["version"] == 2
    assert state["restart_required"] is True
    assert state["desired"]["APP_NAME"] == "next-name"
    assert proxy.APP_NAME == "next-name"


def test_restore_applies_runtime_and_stages_restart_fields(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    apply_minimal_settings_env(monkeypatch)
    manager, proxy = make_manager(monkeypatch, tmp_path / "config.json")
    snapshot = manager._editable_snapshot(proxy.snapshot())
    snapshot["RRF_K"] = 93
    snapshot["APP_NAME"] = "restored-name"

    state = manager.restore_snapshot(snapshot, 0, 0, "system")

    assert state["version"] == 1
    assert state["restart_required"] is True
    assert set(state["pending_fields"]) == {"APP_NAME"}
    assert proxy.RRF_K == 93
    assert proxy.APP_NAME == "test-app"
    assert state["desired"]["APP_NAME"] == "restored-name"


def test_environment_change_blocks_pending_boot(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    apply_minimal_settings_env(monkeypatch)
    path = tmp_path / "config.json"
    first, _ = make_manager(monkeypatch, path)
    first.stage_pending({"APP_NAME": "next-name"}, 0, "system")
    monkeypatch.setenv("RRF_K", "99")

    restarted, proxy = make_manager(monkeypatch, path)

    assert proxy.APP_NAME == "test-app"
    assert restarted.state()["restart_required"] is True
    assert restarted.state()["pending_status"] == "baseline_conflict"
    assert restarted.state()["last_result"]["status"] == "baseline_conflict"


def test_outbox_is_persisted_until_acknowledged(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    apply_minimal_settings_env(monkeypatch)
    manager, _ = make_manager(monkeypatch, tmp_path / "config.json")
    manager.apply_runtime({"RRF_K": 87}, 0, "system")

    events = manager.outbox()
    assert len(events) == 1
    manager.ack_outbox([events[0]["outbox_id"]])
    assert manager.outbox() == []


def test_storage_coordination_uses_highest_version_and_preserves_apply_modes(
    monkeypatch: pytest.MonkeyPatch, tmp_path
) -> None:
    apply_minimal_settings_env(monkeypatch)
    manager, proxy = make_manager(monkeypatch, tmp_path / "config.json")
    source = manager.coordination_source()
    database_snapshot = dict(source["desired_snapshot"])
    database_snapshot["RRF_K"] = 93
    database_snapshot["APP_NAME"] = "database-name"

    result = manager.apply_storage_coordination(
        merged_snapshot=database_snapshot,
        database_snapshot=database_snapshot,
        database_version=5,
        database_checksum=manager._checksum(database_snapshot),
        proposed_version=6,
        expected_file_signature=source["signature"],
        resolutions={"RRF_K": "database", "APP_NAME": "database"},
        actor="system",
    )

    state = result["state"]
    assert state["version"] == 6
    assert proxy.RRF_K == 93
    assert proxy.APP_NAME == "test-app"
    assert state["desired"]["APP_NAME"] == "database-name"
    assert state["pending_version"] == 6
    assert "APP_NAME" in state["pending_fields"]
    assert result["runtime_fields"] == ["RRF_K"]
    event = state["audit_outbox"][-1]["payload"]
    assert event["operation"] == "storage_reconcile"
    assert event["parent_version"] == 5
    assert event["coordination"]["database_version"] == 5


def test_storage_coordination_rejects_stale_file_signature(
    monkeypatch: pytest.MonkeyPatch, tmp_path
) -> None:
    apply_minimal_settings_env(monkeypatch)
    manager, _ = make_manager(monkeypatch, tmp_path / "config.json")
    source = manager.coordination_source()

    with pytest.raises(ConfigConflictError, match="配置文件已变化"):
        manager.apply_storage_coordination(
            merged_snapshot=source["desired_snapshot"],
            database_snapshot=source["desired_snapshot"],
            database_version=5,
            database_checksum=source["desired_checksum"],
            proposed_version=6,
            expected_file_signature="stale",
            resolutions={},
            actor="system",
        )
