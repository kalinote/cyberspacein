"""app.db.rabbitmq 行为测试。"""

import pytest

import app.db.rabbitmq as rabbit_mod
from app.db.rabbitmq import delete_queue


@pytest.mark.asyncio
async def test_delete_queue_noop_when_not_connected():
    # 未建立连接时删除队列应直接返回且不抛异常
    rabbit_mod.rabbitmq_connection = None
    await delete_queue("test-queue-nonexist")


@pytest.mark.asyncio
async def test_close_rabbitmq_when_none():
    # 连接对象为 None 时关闭应可重复调用
    rabbit_mod.rabbitmq_connection = None
    await rabbit_mod.close_rabbitmq()
