"""app.db 各 close_* 在未初始化或已清空时的幂等性测试。"""

import pytest

import app.db.elasticsearch as es_mod
import app.db.mariadb as mariadb_mod
import app.db.mongodb as mongo_mod
import app.db.redis as redis_mod


@pytest.mark.asyncio
async def test_close_redis_when_client_none():
    redis_mod.redis_client = None
    redis_mod.redis_pool = None
    await redis_mod.close_redis()


@pytest.mark.asyncio
async def test_close_mongodb_when_client_none():
    mongo_mod.mongodb_client = None
    await mongo_mod.close_mongodb()


@pytest.mark.asyncio
async def test_close_elasticsearch_when_client_none():
    es_mod.es_client = None
    await es_mod.close_elasticsearch()


@pytest.mark.asyncio
async def test_close_mariadb_when_engine_none():
    mariadb_mod.engine = None
    await mariadb_mod.close_mariadb()
