import logging
from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase
from beanie import init_beanie
from app.core.config import settings

logger = logging.getLogger(__name__)

mongodb_client: AsyncIOMotorClient = None
mongodb_db: AsyncIOMotorDatabase = None


async def init_mongodb():
    """初始化MongoDB连接"""
    global mongodb_client, mongodb_db
    
    connection_kwargs = {
        "maxPoolSize": 50,
        "minPoolSize": 10,
        "serverSelectionTimeoutMS": 5000,
    }
    
    if settings.MONGODB_USERNAME and settings.MONGODB_PASSWORD:
        connection_kwargs["username"] = settings.MONGODB_USERNAME
        connection_kwargs["password"] = settings.MONGODB_PASSWORD
        logger.info(f"使用认证方式连接 MongoDB: {settings.MONGODB_USERNAME}")
    else:
        logger.info("使用无认证方式连接 MongoDB")
    
    mongodb_client = AsyncIOMotorClient(
        settings.MONGODB_URL,
        **connection_kwargs
    )
    
    mongodb_db = mongodb_client[settings.MONGODB_DB_NAME]
    
    await mongodb_client.admin.command('ping')
    logger.info(f"已连接到MongoDB数据库: {settings.MONGODB_DB_NAME}")
    
    from app.models import get_all_models
    await init_beanie(
        database=mongodb_db,
        document_models=get_all_models()
    )
    logger.info("Beanie ODM 初始化完成")


async def close_mongodb():
    """关闭MongoDB连接"""
    global mongodb_client
    if mongodb_client:
        mongodb_client.close()


def get_mongodb() -> AsyncIOMotorDatabase:
    """获取MongoDB数据库实例"""
    return mongodb_db
