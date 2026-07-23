from __future__ import annotations

import hashlib
import json
import os
import shutil
import tempfile
import threading
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable
from urllib.parse import urlparse

from filelock import FileLock
from pydantic import ValidationError


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass(frozen=True, slots=True)
class ConfigField:
    key: str
    label: str
    group: str
    apply_mode: str
    value_type: str
    description: str = ""
    sensitive: bool = False
    constraints: dict[str, Any] = field(default_factory=dict)


GROUPS = [
    {"key": "basic", "label": "基础信息"},
    {"key": "integration", "label": "外部集成"},
    {"key": "network", "label": "网络代理"},
    {"key": "search", "label": "搜索缓存"},
    {"key": "agent", "label": "Agent 与沙盒"},
    {"key": "security", "label": "认证安全"},
    {"key": "infrastructure", "label": "核心基础设施"},
]


def _f(key: str, label: str, group: str, mode: str, value_type: str, **kwargs: Any) -> ConfigField:
    return ConfigField(key, label, group, mode, value_type, **kwargs)


POSITIVE = {"min": 1}
NON_NEGATIVE = {"min": 0}

CONFIG_FIELDS = (
    _f("API_V1_STR", "API 路由前缀", "basic", "readonly", "string", description="服务 API 的固定路由前缀"),
    _f("APP_NAME", "应用名称", "basic", "restart", "string", constraints={"min_length": 1, "max_length": 100}),
    _f("DEBUG", "调试模式", "basic", "restart", "boolean", description="影响日志级别和数据库调试输出"),
    _f("ENVIRONMENT", "运行环境", "basic", "readonly", "string"),
    _f("SERVER_HOST", "服务地址", "basic", "readonly", "string"),
    _f("SERVER_PORT", "服务端口", "basic", "readonly", "integer"),
    _f("MARIADB_URL", "MariaDB 地址", "infrastructure", "readonly", "string", sensitive=True),
    _f("MONGODB_URL", "MongoDB 地址", "infrastructure", "readonly", "string", sensitive=True),
    _f("MONGODB_USERNAME", "MongoDB 用户名", "infrastructure", "readonly", "string"),
    _f("MONGODB_PASSWORD", "MongoDB 密码", "infrastructure", "readonly", "string", sensitive=True),
    _f("MONGODB_DB_NAME", "MongoDB 数据库", "infrastructure", "readonly", "string"),
    _f("REDIS_URL", "Redis 地址", "infrastructure", "readonly", "string", sensitive=True),
    _f("REDIS_PASSWORD", "Redis 密码", "infrastructure", "readonly", "string", sensitive=True),
    _f("ACTION_CACHE_TTL", "行动缓存有效期", "search", "runtime", "integer", description="单位：秒", constraints=POSITIVE),
    _f("ACTION_SCHEDULER_POLL_SECONDS", "行动调度扫描间隔", "infrastructure", "restart", "integer", description="单位：秒", constraints=POSITIVE),
    _f("ACTION_SCHEDULER_BATCH_SIZE", "行动调度单批上限", "infrastructure", "restart", "integer", constraints=POSITIVE),
    _f("ACTION_SCHEDULER_LOCK_SECONDS", "行动调度锁定时长", "infrastructure", "restart", "integer", description="单位：秒", constraints=POSITIVE),
    _f("ACTION_SCHEDULER_HEARTBEAT_TTL_SECONDS", "行动调度心跳有效期", "infrastructure", "restart", "integer", description="单位：秒", constraints=POSITIVE),
    _f("ELASTICSEARCH_URL", "Elasticsearch 地址", "infrastructure", "readonly", "string"),
    _f("ELASTICSEARCH_USER", "Elasticsearch 用户", "infrastructure", "readonly", "string"),
    _f("ELASTICSEARCH_PASSWORD", "Elasticsearch 密码", "infrastructure", "readonly", "string", sensitive=True),
    _f("COMPONENT_LOG_DATA_STREAM", "组件日志数据流", "infrastructure", "restart", "string"),
    _f("COMPONENT_LOG_RETENTION_DAYS", "组件日志保留天数", "infrastructure", "restart", "integer", constraints=POSITIVE),
    _f("RABBITMQ_HOST", "RabbitMQ 主机", "infrastructure", "readonly", "string"),
    _f("RABBITMQ_PORT", "RabbitMQ 端口", "infrastructure", "readonly", "integer"),
    _f("RABBITMQ_USERNAME", "RabbitMQ 用户名", "infrastructure", "readonly", "string"),
    _f("RABBITMQ_PASSWORD", "RabbitMQ 密码", "infrastructure", "readonly", "string", sensitive=True),
    _f("RABBITMQ_VHOST", "RabbitMQ VHost", "infrastructure", "readonly", "string"),
    # TODO(native-scheduler): 自研调度上线后删除 Crawlab 临时系统配置项。
    _f("CRAWLAB_BASE_URL", "Crawlab 地址", "integration", "runtime", "string", constraints={"format": "url"}),
    _f("CRAWLAB_TOKEN", "Crawlab Token", "integration", "runtime", "string", sensitive=True),
    _f("COS_ENDPOINT", "COS Endpoint", "integration", "restart", "string", constraints={"format": "url"}),
    _f("COS_ACCESS_KEY_ID", "COS Access Key", "integration", "restart", "string", sensitive=True),
    _f("COS_SECRET_ACCESS_KEY", "COS Secret Key", "integration", "restart", "string", sensitive=True),
    _f("COS_BUCKET_NAME", "COS Bucket", "integration", "restart", "string"),
    _f("COS_REGION", "COS Region", "integration", "restart", "string"),
    _f("USE_PROXY", "启用外部代理", "network", "runtime", "boolean"),
    _f("OUT_SERVICE_PROXY", "外部代理地址", "network", "runtime", "string", sensitive=True, constraints={"format": "url", "optional": True}),
    _f("MAX_LOGO_SIZE", "Logo 最大大小", "network", "runtime", "integer", description="单位：字节", constraints=POSITIVE),
    _f("NANOBOT_AGENT_MAX_PARALLEL_SESSIONS", "Agent 最大并行会话", "agent", "runtime", "integer", description="0 表示不限制", constraints=NON_NEGATIVE),
    _f("NANOBOT_SHUTDOWN_TIMEOUT_S", "Agent 关闭超时", "agent", "runtime", "number", description="单位：秒", constraints={"min": 1}),
    _f("NANOBOT_RUNTIME_WORKER_ENABLED", "启用分析任务 Worker", "agent", "restart", "boolean"),
    _f("NANOBOT_RUNTIME_WORKER_CONCURRENCY", "分析 Worker 并发数", "agent", "restart", "integer", constraints=POSITIVE),
    _f("NANOBOT_RUNTIME_POLL_SECONDS", "分析任务扫描间隔", "agent", "runtime", "number", description="单位：秒", constraints={"min": 0.01}),
    _f("NANOBOT_RUNTIME_LEASE_SECONDS", "分析任务租约时长", "agent", "restart", "integer", description="单位：秒", constraints=POSITIVE),
    _f("NANOBOT_RUNTIME_HEARTBEAT_SECONDS", "分析 Worker 心跳间隔", "agent", "restart", "integer", description="单位：秒，必须小于租约时长", constraints=POSITIVE),
    _f("NANOBOT_RUNTIME_MAX_ATTEMPTS", "分析任务最大领取次数", "agent", "runtime", "integer", constraints=POSITIVE),
    _f("NANOBOT_EVENT_STREAM_MAXLEN", "实时事件流最大长度", "agent", "runtime", "integer", constraints={"min": 100}),
    _f("NANOBOT_EVENT_STREAM_TTL_SECONDS", "实时事件流保留时间", "agent", "runtime", "integer", description="单位：秒", constraints={"min": 60}),
    _f("EMBEDDING_MODEL", "Embedding 模型", "integration", "restart", "string"),
    _f("EMBEDDING_MODEL_URL", "Embedding 地址", "integration", "restart", "string", constraints={"format": "url"}),
    _f("EMBEDDING_MODEL_API_KEY", "Embedding API Key", "integration", "restart", "string", sensitive=True),
    _f("DOCKER_HOST", "Docker Host", "agent", "runtime", "string", sensitive=True, constraints={"optional": True}),
    _f("AIO_SANDBOX_IMAGE", "一体化沙盒镜像", "agent", "runtime", "string"),
    _f("WINDOWS_SANDBOX_IMAGE", "Windows 沙盒镜像", "agent", "runtime", "string"),
    _f("WINDOWS_TEMPLATE_VOLUME", "Windows 模板卷", "agent", "runtime", "string"),
    _f("SANDBOX_PORT_RANGE", "沙盒端口范围", "agent", "runtime", "string", description="例如 16700-16799", constraints={"format": "port_range"}),
    _f("HYBRID_TOTAL_CAP", "混合检索总量上限", "search", "runtime", "integer", constraints=POSITIVE),
    _f("RRF_K", "RRF K 值", "search", "runtime", "integer", constraints=POSITIVE),
    _f("VECTOR_NUM_CANDIDATES_MULTIPLIER", "向量候选倍数", "search", "runtime", "integer", constraints=POSITIVE),
    _f("VECTOR_NUM_CANDIDATES_MIN", "向量候选最小值", "search", "runtime", "integer", constraints=POSITIVE),
    _f("VECTOR_NUM_CANDIDATES_MAX", "向量候选最大值", "search", "runtime", "integer", constraints=POSITIVE),
    _f("AUTH_SECRET_KEY", "认证签名密钥", "security", "readonly", "string", sensitive=True),
    _f("AUTH_ISSUER", "认证签发方", "security", "readonly", "string"),
    _f("AUTH_AUDIENCE", "用户 Token Audience", "security", "readonly", "string"),
    _f("COMPONENT_AUTH_AUDIENCE", "组件 Token Audience", "security", "readonly", "string"),
    _f("ACCESS_TOKEN_EXPIRE_MINUTES", "用户 Token 有效期", "security", "runtime", "integer", description="单位：分钟，仅影响新签发 Token", constraints=POSITIVE),
    _f("COMPONENT_TOKEN_EXPIRE_MINUTES", "组件 Token 有效期", "security", "runtime", "integer", description="单位：分钟，仅影响新签发 Token", constraints=POSITIVE),
    _f("COMPONENT_BOOTSTRAP_EXPIRE_SECONDS", "组件引导凭证有效期", "security", "runtime", "integer", description="单位：秒", constraints=POSITIVE),
    _f("COMPONENT_HEARTBEAT_INTERVAL_SECONDS", "组件心跳间隔", "security", "runtime", "integer", description="单位：秒", constraints=POSITIVE),
    _f("COMPONENT_LEASE_SECONDS", "组件租约时长", "security", "runtime", "integer", description="单位：秒", constraints=POSITIVE),
    _f("COMPONENT_RUN_TIMEOUT_SECONDS", "组件默认运行超时", "security", "runtime", "integer", description="单位：秒，0 表示不限制", constraints=NON_NEGATIVE),
    _f("ACTION_TIMEOUT_CHECK_INTERVAL_SECONDS", "行动超时检查间隔", "security", "runtime", "number", description="单位：秒", constraints={"min": 0.1}),
    _f("AUTH_REDIS_NAMESPACE", "认证 Redis 命名空间", "security", "readonly", "string"),
    _f("LOGIN_FAILURE_THRESHOLD", "登录失败阈值", "security", "runtime", "integer", constraints=POSITIVE),
    _f("LOGIN_FAILURE_WINDOW_SECONDS", "登录失败统计窗口", "security", "runtime", "integer", description="单位：秒", constraints=POSITIVE),
    _f("LOGIN_LOCK_SECONDS", "登录锁定时长", "security", "runtime", "integer", description="单位：秒", constraints=POSITIVE),
    _f("LOGIN_RATE_LIMIT_ACCOUNT", "账号登录频率上限", "security", "runtime", "integer", constraints=POSITIVE),
    _f("LOGIN_RATE_LIMIT_SOURCE", "来源登录频率上限", "security", "runtime", "integer", constraints=POSITIVE),
    _f("LOGIN_RATE_LIMIT_WINDOW_SECONDS", "登录限流窗口", "security", "runtime", "integer", description="单位：秒", constraints=POSITIVE),
    _f("TEMPORARY_ACCOUNT_MAX_DAYS", "临时账号最长有效期", "security", "runtime", "integer", description="单位：天", constraints=POSITIVE),
    _f("INIT_SYSTEM_USERNAME", "内置系统用户名", "security", "readonly", "string"),
    _f("INIT_SYSTEM_PASSWORD", "内置系统初始密码", "security", "readonly", "string", sensitive=True),
    _f("INIT_SYSTEM_DISPLAY_NAME", "内置系统显示名", "security", "readonly", "string"),
    _f("INIT_SYSTEM_EMAIL", "内置系统邮箱", "security", "readonly", "string"),
    _f("INIT_SYSTEM_GROUP_NAME", "内置系统权限组", "security", "readonly", "string"),
)

CONFIG_FIELD_MAP = {item.key: item for item in CONFIG_FIELDS}


class ConfigError(RuntimeError):
    pass


class ConfigConflictError(ConfigError):
    pass


class SystemConfigManager:
    def __init__(self) -> None:
        configured = os.environ.get("CSI_SYSTEM_CONFIG_FILE", "./data/system-config.json")
        self.path = Path(configured).expanduser().resolve()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.lock = FileLock(str(self.path) + ".lock")
        self._settings_cls: Callable[..., Any] | None = None
        self._settings_ref: Any = None
        self._boot_pending_version: int | None = None
        self._version = 0
        self._state_lock = threading.RLock()
        self.boot_id = uuid.uuid4().hex
        self.started_at = _utcnow()
        self.ready = False
        self._history_sync_status = "pending"

    @staticmethod
    def _default_state() -> dict[str, Any]:
        return {
            "schema_version": 2,
            "version": 0,
            "active": {},
            "desired": {},
            "restart_required": False,
            "pending_version": None,
            "pending_fields": [],
            "pending_baseline_fingerprint": None,
            "pending_status": None,
            "boot_attempt": None,
            "baseline_fingerprint": None,
            "audit_outbox": [],
            "updated_at": None,
            "updated_by": None,
            "last_result": None,
        }

    @staticmethod
    def _checksum(value: Any) -> str:
        encoded = json.dumps(
            value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str
        ).encode("utf-8")
        return hashlib.sha256(encoded).hexdigest()

    def _migrate_state(self, raw: dict[str, Any]) -> dict[str, Any]:
        if raw.get("schema_version") == 2:
            state = {**self._default_state(), **raw}
            state["desired"] = dict(state.get("desired") or state.get("active") or {})
            state["audit_outbox"] = list(state.get("audit_outbox") or [])
            return state
        if raw.get("schema_version") != 1:
            raise ValueError("unsupported config schema")
        active = dict(raw.get("active") or {})
        pending = raw.get("pending") if isinstance(raw.get("pending"), dict) else None
        desired = dict(pending.get("overrides") or active) if pending else dict(active)
        pending_fields = [
            key
            for key in desired
            if CONFIG_FIELD_MAP.get(key)
            and CONFIG_FIELD_MAP[key].apply_mode == "restart"
            and desired.get(key) != active.get(key)
        ]
        version = int(pending.get("version") if pending else raw.get("version") or 0)
        return {
            **self._default_state(),
            "version": version,
            "active": active,
            "desired": desired,
            "restart_required": bool(pending),
            "pending_version": version if pending else None,
            "pending_fields": pending_fields,
            "pending_status": "pending_restart" if pending else None,
            "boot_attempt": (
                {"version": version, "attempted_at": pending.get("attempted_at")}
                if pending and pending.get("attempted")
                else None
            ),
            "updated_at": raw.get("updated_at"),
            "updated_by": raw.get("updated_by"),
            "last_result": raw.get("last_result"),
        }

    def _read_unlocked(self) -> dict[str, Any]:
        if not self.path.exists():
            return self._default_state()
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
            if not isinstance(raw, dict):
                raise ValueError("config state must be an object")
            return self._migrate_state(raw)
        except Exception as exc:
            backup = self.path.with_suffix(self.path.suffix + ".bak")
            if backup.exists():
                raw = json.loads(backup.read_text(encoding="utf-8"))
                if isinstance(raw, dict):
                    return self._migrate_state(raw)
            raise ConfigError(f"系统配置文件损坏且无可用备份: {exc}") from exc

    def _write_unlocked(self, state: dict[str, Any]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if self.path.exists():
            try:
                current = json.loads(self.path.read_text(encoding="utf-8"))
                if isinstance(current, dict) and current.get("schema_version") in {1, 2}:
                    shutil.copy2(self.path, self.path.with_suffix(self.path.suffix + ".bak"))
            except (OSError, ValueError, json.JSONDecodeError):
                pass
        fd, temp_name = tempfile.mkstemp(prefix=f".{self.path.name}.", dir=self.path.parent)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                json.dump(state, handle, ensure_ascii=False, indent=2, sort_keys=True)
                handle.flush()
                os.fsync(handle.fileno())
            try:
                os.chmod(temp_name, 0o600)
            except OSError:
                pass
            os.replace(temp_name, self.path)
        finally:
            if os.path.exists(temp_name):
                os.unlink(temp_name)

    def bootstrap(self, settings_cls: Callable[..., Any]) -> Any:
        self._settings_cls = settings_cls
        with self.lock:
            state = self._read_unlocked()
            overrides = dict(state.get("active") or {})
            baseline = self._candidate({})
            baseline_fingerprint = self._checksum(baseline.model_dump())
            if state.get("restart_required"):
                pending_version = int(state.get("pending_version") or state["version"])
                stored_fingerprint = state.get("pending_baseline_fingerprint")
                if stored_fingerprint and stored_fingerprint != baseline_fingerprint:
                    if state.get("pending_status") != "baseline_conflict":
                        self._enqueue_status(
                            state,
                            pending_version,
                            "baseline_conflict",
                            "部署环境基线已变化，请重新预览并保存待重启配置",
                        )
                    state["pending_status"] = "baseline_conflict"
                    state["boot_attempt"] = None
                    state["last_result"] = {
                        "status": "baseline_conflict",
                        "version": pending_version,
                        "at": _utcnow(),
                        "message": "部署环境基线已变化，待重启配置未应用",
                    }
                elif state.get("boot_attempt"):
                    state["desired"] = dict(state.get("active") or {})
                    state["restart_required"] = False
                    state["pending_fields"] = []
                    state["pending_version"] = None
                    state["pending_status"] = None
                    state["boot_attempt"] = None
                    self._enqueue_status(
                        state,
                        pending_version,
                        "rolled_back",
                        "候选配置未能完成上次启动，已自动恢复旧配置",
                    )
                    state["last_result"] = {
                        "status": "rolled_back",
                        "version": pending_version,
                        "at": _utcnow(),
                        "message": "候选配置未能完成上次启动，已自动恢复旧配置",
                    }
                else:
                    state["boot_attempt"] = {
                        "version": pending_version,
                        "attempted_at": _utcnow(),
                        "boot_id": self.boot_id,
                    }
                    state["pending_status"] = "applying"
                    overrides = dict(state.get("desired") or {})
                    self._boot_pending_version = pending_version
            state["baseline_fingerprint"] = baseline_fingerprint
            self._write_unlocked(state)
            self._version = int(state.get("version") or 0)
        return self._candidate(overrides)

    def bind_settings(self, settings_ref: Any) -> None:
        self._settings_ref = settings_ref

    def _candidate(self, overrides: dict[str, Any]) -> Any:
        if self._settings_cls is None:
            raise ConfigError("配置管理器尚未初始化")
        try:
            candidate = self._settings_cls(**overrides)
            candidate.validate_auth_security()
            self._validate_cross_fields(candidate)
            return candidate
        except ValidationError as exc:
            details = []
            for item in exc.errors(include_input=False, include_url=False):
                field_name = ".".join(str(part) for part in item.get("loc", ())) or "配置"
                details.append(f"{field_name}: {item.get('msg', '值无效')}")
            raise ConfigError("; ".join(details) or "配置校验失败") from exc
        except (ValueError, RuntimeError) as exc:
            raise ConfigError(str(exc)) from exc

    @staticmethod
    def _validate_cross_fields(candidate: Any) -> None:
        if candidate.VECTOR_NUM_CANDIDATES_MIN > candidate.VECTOR_NUM_CANDIDATES_MAX:
            raise ValueError("VECTOR_NUM_CANDIDATES_MIN 不能大于 VECTOR_NUM_CANDIDATES_MAX")
        port_range = str(candidate.SANDBOX_PORT_RANGE or "")
        parts = port_range.split("-", 1)
        if len(parts) != 2 or not all(part.isdigit() for part in parts):
            raise ValueError("SANDBOX_PORT_RANGE 必须是 start-end 格式")
        start, end = map(int, parts)
        if start < 1 or end > 65535 or start > end:
            raise ValueError("SANDBOX_PORT_RANGE 必须位于 1-65535 且起始端口不大于结束端口")
        for item in CONFIG_FIELDS:
            if item.constraints.get("format") != "url":
                continue
            value = getattr(candidate, item.key)
            if not value and item.constraints.get("optional"):
                continue
            parsed = urlparse(str(value))
            if parsed.scheme not in {"http", "https"} or not parsed.netloc:
                raise ValueError(f"{item.key} 必须是有效的 HTTP(S) URL")

    def _normalize_changes(self, changes: dict[str, Any], allowed_modes: set[str]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        state = self.state()
        current = self._candidate(state.get("desired") or {})
        for key, value in changes.items():
            meta = CONFIG_FIELD_MAP.get(key)
            if meta is None:
                raise ConfigError(f"未知配置项: {key}")
            if meta.apply_mode not in allowed_modes:
                raise ConfigError(f"配置项 {key} 不允许通过此接口修改")
            if meta.sensitive and (value is None or value == ""):
                continue
            if value != getattr(current, key):
                result[key] = value
        return result

    def preview(self, changes: dict[str, Any]) -> tuple[dict[str, Any], Any, dict[str, Any]]:
        normalized = self._normalize_changes(changes, {"runtime", "restart"})
        if not normalized:
            raise ConfigError("没有可应用的配置变更")
        with self.lock:
            state = self._read_unlocked()
        overrides = dict(state.get("desired") or {})
        overrides.update(normalized)
        candidate = self._candidate(overrides)
        modes = {
            "runtime": [key for key in normalized if CONFIG_FIELD_MAP[key].apply_mode == "runtime"],
            "restart": [key for key in normalized if CONFIG_FIELD_MAP[key].apply_mode == "restart"],
        }
        return normalized, candidate, modes

    def _ensure_writable(self) -> None:
        if self._history_sync_status == "conflict":
            raise ConfigConflictError("配置历史与当前状态冲突，请先完成存储协调")

    def _editable_snapshot(self, candidate: Any) -> dict[str, Any]:
        return {
            meta.key: getattr(candidate, meta.key)
            for meta in CONFIG_FIELDS
            if meta.apply_mode != "readonly"
        }

    def _build_changes(self, before: Any, after: Any) -> list[dict[str, Any]]:
        rows = []
        for meta in CONFIG_FIELDS:
            if meta.apply_mode == "readonly":
                continue
            old_value = getattr(before, meta.key)
            new_value = getattr(after, meta.key)
            if old_value != new_value:
                rows.append(
                    {
                        "key": meta.key,
                        "apply_mode": meta.apply_mode,
                        "before": old_value,
                        "after": new_value,
                        "sensitive": meta.sensitive,
                    }
                )
        return rows

    def _version_event(
        self,
        *,
        version: int,
        parent_version: int,
        operation: str,
        status: str,
        before: Any,
        after: Any,
        actor: str,
        restored_from_version: int | None = None,
    ) -> dict[str, Any]:
        snapshot = self._editable_snapshot(after)
        event_id = uuid.uuid4().hex
        payload = {
            "id": event_id,
            "event_id": event_id,
            "version": version,
            "parent_version": parent_version,
            "operation": operation,
            "status": status,
            "changes": self._build_changes(before, after),
            "snapshot": snapshot,
            "snapshot_checksum": self._checksum(snapshot),
            "created_by": actor,
            "created_at": _utcnow(),
            "applied_at": _utcnow() if status == "applied" else None,
            "boot_id": self.boot_id,
            "restored_from_version": restored_from_version,
            "baseline_fingerprint": self._baseline_fingerprint(),
            "message": None,
        }
        return {"kind": "version", "outbox_id": uuid.uuid4().hex, "payload": payload}

    @staticmethod
    def _enqueue_status(
        state: dict[str, Any], version: int, status: str, message: str
    ) -> None:
        state.setdefault("audit_outbox", []).append(
            {
                "kind": "status",
                "outbox_id": uuid.uuid4().hex,
                "version": version,
                "status": status,
                "message": message,
                "applied_at": _utcnow() if status == "applied" else None,
            }
        )

    def _baseline_fingerprint(self) -> str:
        return self._checksum(self._candidate({}).model_dump())

    def _pending_fields(self, active: Any, desired: Any) -> list[str]:
        return [
            meta.key
            for meta in CONFIG_FIELDS
            if meta.apply_mode == "restart"
            and getattr(active, meta.key) != getattr(desired, meta.key)
        ]

    def _prepare_version(
        self,
        state: dict[str, Any],
        before: Any,
        after: Any,
        operation: str,
        actor: str,
        restored_from_version: int | None = None,
    ) -> int:
        parent = int(state["version"])
        version = parent + 1
        active_candidate = self._candidate(state.get("active") or {})
        pending_fields = self._pending_fields(active_candidate, after)
        if state.get("restart_required") and state.get("pending_version"):
            self._enqueue_status(
                state,
                int(state["pending_version"]),
                "superseded",
                f"已被配置版本 v{version} 取代",
            )
        restart_required = bool(pending_fields)
        status = "pending_restart" if restart_required else "applied"
        state["version"] = version
        state["restart_required"] = restart_required
        state["pending_fields"] = pending_fields
        state["pending_version"] = version if restart_required else None
        state["pending_status"] = status if restart_required else None
        state["pending_baseline_fingerprint"] = (
            self._baseline_fingerprint() if restart_required else None
        )
        state["boot_attempt"] = None
        state["updated_at"] = _utcnow()
        state["updated_by"] = actor
        state["last_result"] = {
            "status": status,
            "version": version,
            "at": state["updated_at"],
            "message": (
                "配置已保存，等待服务重启" if restart_required else "配置已生效"
            ),
        }
        state.setdefault("audit_outbox", []).append(
            self._version_event(
                version=version,
                parent_version=parent,
                operation=operation,
                status=status,
                before=before,
                after=after,
                actor=actor,
                restored_from_version=restored_from_version,
            )
        )
        return version

    def apply_runtime(self, changes: dict[str, Any], expected_version: int, actor: str) -> dict[str, Any]:
        self._ensure_writable()
        normalized = self._normalize_changes(changes, {"runtime"})
        if not normalized:
            raise ConfigError("没有可应用的运行时配置变更")
        with self._state_lock, self.lock:
            state = self._read_unlocked()
            if int(state["version"]) != expected_version:
                raise ConfigConflictError("配置版本已变化，请刷新后重试")
            before = self._candidate(state.get("desired") or {})
            active = dict(state.get("active") or {})
            desired = dict(state.get("desired") or {})
            active.update(normalized)
            desired.update(normalized)
            candidate = self._candidate(active)
            desired_candidate = self._candidate(desired)
            state["active"] = active
            state["desired"] = desired
            self._prepare_version(state, before, desired_candidate, "runtime_update", actor)
            self._write_unlocked(state)
            self._settings_ref.swap(candidate)
            self._version = int(state["version"])
            return state

    def stage_pending(self, changes: dict[str, Any], expected_version: int, actor: str) -> dict[str, Any]:
        self._ensure_writable()
        normalized = self._normalize_changes(changes, {"restart"})
        if not normalized:
            raise ConfigError("没有可保存的待重启配置变更")
        with self._state_lock, self.lock:
            state = self._read_unlocked()
            if int(state["version"]) != expected_version:
                raise ConfigConflictError("配置版本已变化，请刷新后重试")
            before = self._candidate(state.get("desired") or {})
            desired = dict(state.get("desired") or {})
            desired.update(normalized)
            desired_candidate = self._candidate(desired)
            state["desired"] = desired
            self._prepare_version(state, before, desired_candidate, "restart_update", actor)
            self._write_unlocked(state)
            return state

    def cancel_pending(self, expected_version: int, actor: str) -> dict[str, Any]:
        self._ensure_writable()
        with self._state_lock, self.lock:
            state = self._read_unlocked()
            if int(state["version"]) != expected_version:
                raise ConfigConflictError("配置版本已变化，请刷新后重试")
            if not state.get("restart_required"):
                raise ConfigError("当前没有待重启配置")
            before = self._candidate(state.get("desired") or {})
            active = dict(state.get("active") or {})
            desired = dict(state.get("desired") or {})
            for meta in CONFIG_FIELDS:
                if meta.apply_mode != "restart":
                    continue
                if meta.key in active:
                    desired[meta.key] = active[meta.key]
                else:
                    desired.pop(meta.key, None)
            after = self._candidate(desired)
            state["desired"] = desired
            self._prepare_version(state, before, after, "cancel_pending", actor)
            self._write_unlocked(state)
            return state

    def restore_snapshot(
        self,
        snapshot: dict[str, Any],
        source_version: int,
        expected_version: int,
        actor: str,
    ) -> dict[str, Any]:
        self._ensure_writable()
        editable_keys = {
            meta.key for meta in CONFIG_FIELDS if meta.apply_mode != "readonly"
        }
        if set(snapshot) != editable_keys:
            raise ConfigError("历史版本快照不完整，无法执行一键还原")
        with self._state_lock, self.lock:
            state = self._read_unlocked()
            if int(state["version"]) != expected_version:
                raise ConfigConflictError("配置版本已变化，请刷新后重试")
            before = self._candidate(state.get("desired") or {})
            target = self._candidate(snapshot)
            if not self._build_changes(before, target):
                raise ConfigError("当前配置已经与目标历史版本一致")
            active = dict(state.get("active") or {})
            desired = dict(state.get("desired") or {})
            for meta in CONFIG_FIELDS:
                if meta.apply_mode == "runtime":
                    active[meta.key] = snapshot[meta.key]
                    desired[meta.key] = snapshot[meta.key]
                elif meta.apply_mode == "restart":
                    desired[meta.key] = snapshot[meta.key]
            active_candidate = self._candidate(active)
            desired_candidate = self._candidate(desired)
            state["active"] = active
            state["desired"] = desired
            self._prepare_version(
                state,
                before,
                desired_candidate,
                "restore",
                actor,
                restored_from_version=source_version,
            )
            self._write_unlocked(state)
            self._settings_ref.swap(active_candidate)
            self._version = int(state["version"])
            return state

    def restore_modes(self, snapshot: dict[str, Any]) -> dict[str, list[str]]:
        state = self.state()
        current = self._candidate(state.get("desired") or {})
        modes = {"runtime": [], "restart": []}
        for meta in CONFIG_FIELDS:
            if meta.apply_mode == "readonly" or meta.key not in snapshot:
                continue
            if getattr(current, meta.key) != snapshot[meta.key]:
                modes[meta.apply_mode].append(meta.key)
        return modes

    def commit_bootstrap(self) -> None:
        if self._boot_pending_version is None:
            self.ready = True
            return
        with self._state_lock, self.lock:
            state = self._read_unlocked()
            if (
                state.get("restart_required")
                and int(state.get("pending_version") or -1) == self._boot_pending_version
            ):
                state["active"] = dict(state.get("desired") or {})
                state["updated_at"] = _utcnow()
                state["restart_required"] = False
                state["pending_version"] = None
                state["pending_fields"] = []
                state["pending_status"] = None
                state["pending_baseline_fingerprint"] = None
                state["boot_attempt"] = None
                state["last_result"] = {
                    "status": "applied",
                    "version": state["version"],
                    "at": state["updated_at"],
                    "message": "服务重启成功，候选配置已生效",
                }
                self._enqueue_status(
                    state,
                    self._boot_pending_version,
                    "applied",
                    "服务重启成功，候选配置已生效",
                )
                self._write_unlocked(state)
                self._version = int(state["version"])
        self._boot_pending_version = None
        self.ready = True

    def mark_not_ready(self) -> None:
        self.ready = False

    def state(self) -> dict[str, Any]:
        with self.lock:
            return self._read_unlocked()

    def outbox(self) -> list[dict[str, Any]]:
        return list(self.state().get("audit_outbox") or [])

    def ack_outbox(self, outbox_ids: list[str]) -> None:
        if not outbox_ids:
            return
        acknowledged = set(outbox_ids)
        with self._state_lock, self.lock:
            state = self._read_unlocked()
            state["audit_outbox"] = [
                event
                for event in state.get("audit_outbox") or []
                if event.get("outbox_id") not in acknowledged
            ]
            self._write_unlocked(state)

    def set_history_sync_status(self, status: str) -> None:
        self._history_sync_status = status

    def desired_snapshot_checksum(self) -> str:
        state = self.state()
        desired = self._candidate(state.get("desired") or {})
        return self._checksum(self._editable_snapshot(desired))

    def baseline_history_event(self) -> dict[str, Any]:
        state = self.state()
        desired = self._candidate(state.get("desired") or {})
        version = int(state["version"])
        snapshot = self._editable_snapshot(desired)
        event_id = uuid.uuid4().hex
        payload = {
            "id": event_id,
            "event_id": event_id,
            "version": version,
            "parent_version": None,
            "operation": "migration_baseline",
            "status": "pending_restart" if state.get("restart_required") else "applied",
            "changes": [],
            "snapshot": snapshot,
            "snapshot_checksum": self._checksum(snapshot),
            "created_by": state.get("updated_by") or "deployment",
            "created_at": state.get("updated_at") or _utcnow(),
            "applied_at": None if state.get("restart_required") else _utcnow(),
            "boot_id": self.boot_id,
            "restored_from_version": None,
            "baseline_fingerprint": state.get("baseline_fingerprint"),
            "message": "配置历史基线",
        }
        return {"kind": "version", "outbox_id": uuid.uuid4().hex, "payload": payload}

    def public_config(self) -> dict[str, Any]:
        state = self.state()
        active = self._candidate(state.get("active") or {})
        desired = self._candidate(state.get("desired") or {})
        fields = []
        for meta in CONFIG_FIELDS:
            active_value = getattr(active, meta.key)
            desired_value = getattr(desired, meta.key)
            item = asdict(meta)
            item["editable"] = meta.apply_mode != "readonly"
            item["configured"] = desired_value not in (None, "")
            item["active_configured"] = active_value not in (None, "")
            item["pending_change"] = (
                meta.apply_mode == "restart" and active_value != desired_value
            )
            item["value"] = None if meta.sensitive else desired_value
            item["active_value"] = None if meta.sensitive else active_value
            fields.append(item)
        return {
            "version": int(state["version"]),
            "boot_id": self.boot_id,
            "started_at": self.started_at,
            "ready": self.ready,
            "updated_at": state.get("updated_at"),
            "updated_by": state.get("updated_by"),
            "restart_required": bool(state.get("restart_required")),
            "pending": bool(state.get("restart_required")),
            "pending_version": state.get("pending_version"),
            "pending_fields": list(state.get("pending_fields") or []),
            "pending_status": state.get("pending_status"),
            "boot_attempt": state.get("boot_attempt"),
            "history_sync_status": self._history_sync_status,
            "last_result": state.get("last_result"),
            "groups": GROUPS,
            "fields": fields,
        }


system_config_manager = SystemConfigManager()
