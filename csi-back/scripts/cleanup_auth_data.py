"""Development-only cleanup for CSI authentication and permission data.

This is intentionally a standalone operator script. It is not imported by the
FastAPI application, lifespan, API routes, or business services.
"""

from __future__ import annotations

import argparse
import asyncio
import os
import sys
from dataclasses import dataclass
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from motor.motor_asyncio import AsyncIOMotorClient
from redis.asyncio import Redis

from app.core.config import settings


AUTH_COLLECTIONS = (
    "auth_users",
    "auth_groups",
    "auth_permission_codes",
    "auth_login_sessions",
)


@dataclass(frozen=True, slots=True)
class CleanupTarget:
    environment: str
    database: str
    collections: tuple[str, ...]
    redis_namespace: str

    @property
    def confirmation_text(self) -> str:
        return f"DELETE AUTH DATA FROM {self.database}"


def build_cleanup_target() -> CleanupTarget:
    return CleanupTarget(
        environment=settings.normalized_environment,
        database=settings.MONGODB_DB_NAME,
        collections=AUTH_COLLECTIONS,
        redis_namespace=settings.AUTH_REDIS_NAMESPACE,
    )


def validate_cleanup_confirmation(target: CleanupTarget, confirmation: str) -> None:
    if os.environ.get("ENVIRONMENT", "").strip().lower() != "development":
        raise RuntimeError("必须显式设置 ENVIRONMENT=development 才能运行清理脚本")
    if target.environment != "development":
        raise RuntimeError("权限数据清理脚本仅允许在 ENVIRONMENT=development 时运行")
    if not target.database.strip():
        raise RuntimeError("目标 MongoDB 数据库名不能为空")
    if not target.redis_namespace.strip() or any(char in target.redis_namespace for char in "*?[]"):
        raise RuntimeError("Redis namespace 不能为空且不能包含通配符")
    if confirmation != target.confirmation_text:
        raise RuntimeError("确认文本不匹配，未执行任何清理")


async def _delete_redis_namespace(redis: Redis, namespace: str) -> int:
    keys: list[str] = []
    deleted = 0
    async for key in redis.scan_iter(match=f"{namespace}:*"):
        keys.append(key)
        if len(keys) >= 500:
            deleted += int(await redis.delete(*keys))
            keys.clear()
    if keys:
        deleted += int(await redis.delete(*keys))
    return deleted


async def run_cleanup(target: CleanupTarget) -> None:
    mongo_kwargs: dict[str, str] = {}
    if settings.MONGODB_USERNAME and settings.MONGODB_PASSWORD:
        mongo_kwargs.update(
            username=settings.MONGODB_USERNAME,
            password=settings.MONGODB_PASSWORD,
        )
    mongo = AsyncIOMotorClient(settings.MONGODB_URL, **mongo_kwargs)
    redis = Redis.from_url(
        settings.REDIS_URL,
        password=settings.REDIS_PASSWORD or None,
        decode_responses=True,
    )
    try:
        database = mongo[target.database]
        for collection_name in target.collections:
            result = await database[collection_name].delete_many({})
            print(f"MongoDB {collection_name}: deleted={result.deleted_count}")
        deleted_keys = await _delete_redis_namespace(redis, target.redis_namespace)
        print(f"Redis {target.redis_namespace}:*: deleted={deleted_keys}")
    finally:
        mongo.close()
        await redis.aclose()


def main() -> int:
    parser = argparse.ArgumentParser(description="清理开发环境 CSI 权限和登录会话数据")
    parser.add_argument(
        "--confirm",
        help="非交互确认文本；必须与脚本显示的确认文本完全一致",
    )
    args = parser.parse_args()
    target = build_cleanup_target()
    print("即将清理权限系统数据：")
    print(f"  environment: {target.environment}")
    print(f"  MongoDB database: {target.database}")
    print(f"  MongoDB collections: {', '.join(target.collections)}")
    print(f"  Redis namespace: {target.redis_namespace}:*")
    confirmation = args.confirm
    if confirmation is None:
        print(f"请输入以下确认文本：{target.confirmation_text}")
        confirmation = input("> ").strip()
    validate_cleanup_confirmation(target, confirmation)
    asyncio.run(run_cleanup(target))
    print("权限系统开发数据清理完成；请重启后端以重新协调标准权限和系统账号。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
