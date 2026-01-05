import logging
import aio_pika
from urllib.parse import quote
from app.core.config import settings

logger = logging.getLogger(__name__)

rabbitmq_connection: aio_pika.Connection = None


async def init_rabbitmq():
    """初始化RabbitMQ连接"""
    global rabbitmq_connection
    
    try:
        username = quote(settings.RABBITMQ_USERNAME, safe="")
        password = quote(settings.RABBITMQ_PASSWORD, safe="")
        vhost = quote(settings.RABBITMQ_VHOST, safe="")
        url = f"amqp://{username}:{password}@{settings.RABBITMQ_HOST}:{settings.RABBITMQ_PORT}/{vhost}"
        rabbitmq_connection = await aio_pika.connect_robust(url)
        logger.info("已连接到RabbitMQ")
    except Exception as e:
        logger.error(f"RabbitMQ连接失败: {str(e)}")
        raise


async def close_rabbitmq():
    """关闭RabbitMQ连接"""
    global rabbitmq_connection
    if rabbitmq_connection:
        await rabbitmq_connection.close()
        logger.info("已关闭RabbitMQ连接")


async def delete_queue(queue_name: str):
    """删除指定名称的队列"""
    global rabbitmq_connection
    if not rabbitmq_connection:
        logger.warning("RabbitMQ连接未初始化，无法删除队列")
        return
    
    try:
        channel = await rabbitmq_connection.channel()
        await channel.queue_delete(queue_name)
        await channel.close()
        logger.info(f"已删除队列: {queue_name}")
    except Exception as e:
        logger.error(f"删除队列失败 {queue_name}: {str(e)}")

