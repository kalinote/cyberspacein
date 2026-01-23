import logging
from redis.asyncio import Redis, ConnectionPool
from app.core.config import settings

logger = logging.getLogger(__name__)

redis_client: Redis = None
redis_pool: ConnectionPool = None


async def init_redis():
    """初始化Redis连接"""
    global redis_client, redis_pool
    
    if not settings.REDIS_URL:
        logger.warning("REDIS_URL 未配置，Redis功能将不可用")
        return
    
    connection_kwargs = {
        "encoding": "utf-8",
        "decode_responses": True,
        "max_connections": 50,
    }
    
    if settings.REDIS_PASSWORD:
        connection_kwargs["password"] = settings.REDIS_PASSWORD
        logger.info("使用认证方式连接 Redis")
    else:
        logger.info("使用无认证方式连接 Redis")
    
    redis_pool = ConnectionPool.from_url(
        settings.REDIS_URL,
        **connection_kwargs
    )
    
    redis_client = Redis(connection_pool=redis_pool)
    
    try:
        await redis_client.ping()
        logger.info("已连接到Redis")
    except Exception as e:
        logger.error(f"Redis连接失败: {e}", exc_info=True)
        redis_client = None
        redis_pool = None


async def close_redis():
    """关闭Redis连接"""
    global redis_client, redis_pool
    if redis_client:
        await redis_client.close()
    if redis_pool:
        await redis_pool.disconnect()


def get_redis() -> Redis:
    """获取Redis客户端实例"""
    return redis_client
