"""证据链本地验收服务，仅使用独立的临时 MongoDB 库。

运行：.venv/Scripts/python.exe -m uvicorn tests.evidence_preview:app --host 127.0.0.1 --port 8082
保留真实鉴权、权限矩阵和实体检索；不启动行动、采集或分析后台任务。
退出时只清理本次创建的随机测试库。
"""

from contextlib import asynccontextmanager
from uuid import uuid4

from app.core.config import settings


from app.main import app
from app.db.mongodb import close_mongodb, get_mongodb, init_mongodb
from app.db.elasticsearch import close_elasticsearch, init_elasticsearch
from app.db.redis import close_redis, get_redis, init_redis
from app.core.permissions import sync_standard_permissions
from app.service.auth.service import ensure_default_admin


preview_database = "csi_evidence_preview_" + uuid4().hex


@asynccontextmanager
async def preview_lifespan(application):
    """启动隔离验收环境，使用现有配置连接基础设施。"""
    settings.MONGODB_DB_NAME = preview_database
    settings.AUTH_REDIS_NAMESPACE = preview_database
    await init_mongodb()
    await init_elasticsearch()
    await init_redis()
    await sync_standard_permissions()
    await ensure_default_admin()
    try:
        yield
    finally:
        database = get_mongodb()
        if database.name == preview_database and database.name.startswith(
            "csi_evidence_preview_"
        ):
            await database.client.drop_database(preview_database)
        if settings.AUTH_REDIS_NAMESPACE == preview_database:
            redis = get_redis()
            async for key in redis.scan_iter(match=f"{preview_database}:*", count=100):
                await redis.delete(key)
        await close_redis()
        await close_elasticsearch()
        await close_mongodb()


app.router.lifespan_context = preview_lifespan


@app.get("/health/evidence-preview", include_in_schema=False)
async def preview_status():
    """让验收脚本确认正在操作本次临时库。"""
    return {"temporary": True, "database": preview_database}
