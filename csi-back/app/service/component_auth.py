from __future__ import annotations

import hashlib
import secrets
from dataclasses import dataclass

from app.core.config import settings
from app.core.exceptions import UnauthorizedException
from app.db.redis import get_redis


@dataclass(frozen=True, slots=True)
class ComponentBootstrapContext:
    action_id: str
    node_instance_id: str
    component_run_id: str


def _bootstrap_key(value: str) -> str:
    digest = hashlib.sha256(value.encode("utf-8")).hexdigest()
    return f"{settings.AUTH_REDIS_NAMESPACE}:component-bootstrap:{digest}"


async def issue_component_bootstrap(
    action_id: str,
    node_instance_id: str,
    component_run_id: str,
) -> str:
    """创建短期一次性引导码，Redis 中仅保存其哈希键。"""
    redis = get_redis()
    if redis is None:
        raise RuntimeError("Redis 未初始化，无法签发组件引导码")
    for _ in range(3):
        value = secrets.token_urlsafe(32)
        created = await redis.set(
            _bootstrap_key(value),
            f"{action_id}\n{node_instance_id}\n{component_run_id}",
            ex=settings.COMPONENT_BOOTSTRAP_EXPIRE_SECONDS,
            nx=True,
        )
        if created:
            return value
    raise RuntimeError("组件引导码签发冲突，请稍后重试")


async def consume_component_bootstrap(
    value: str,
    requested_component_run_id: str,
) -> ComponentBootstrapContext:
    """原子消费引导码并校验其 ComponentRun 绑定。"""
    if not value:
        raise UnauthorizedException("组件引导凭证无效或已过期")
    redis = get_redis()
    if redis is None:
        raise UnauthorizedException("组件引导凭证无效或已过期")
    stored = await redis.eval(
        "local v=redis.call('GET',KEYS[1]); if v then redis.call('DEL',KEYS[1]); end; return v",
        1,
        _bootstrap_key(value),
    )
    if not isinstance(stored, str):
        raise UnauthorizedException("组件引导凭证无效或已过期")
    try:
        action_id, node_instance_id, component_run_id = stored.split("\n", 2)
    except ValueError as exc:
        raise UnauthorizedException("组件引导凭证无效或已过期") from exc
    if not action_id or component_run_id != requested_component_run_id:
        raise UnauthorizedException("组件引导凭证无效或已过期")
    return ComponentBootstrapContext(
        action_id=action_id,
        node_instance_id=node_instance_id,
        component_run_id=component_run_id,
    )
