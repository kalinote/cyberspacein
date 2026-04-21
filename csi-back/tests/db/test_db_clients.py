"""app.db 各客户端 getter 与模块全局状态一致性的测试。"""

import app.db.elasticsearch as es_mod
import app.db.mongodb as mongo_mod
import app.db.redis as redis_mod
from app.db.elasticsearch import get_es
from app.db.mongodb import get_mongodb
from app.db.redis import get_redis


def test_get_redis_matches_module_global():
    # get_redis 应返回模块级 redis_client 引用
    assert get_redis() is redis_mod.redis_client


def test_get_mongodb_matches_module_global():
    # get_mongodb 应返回模块级 mongodb_db 引用
    assert get_mongodb() is mongo_mod.mongodb_db


def test_get_es_matches_module_global():
    # get_es 应返回模块级 es_client 引用
    assert get_es() is es_mod.es_client
