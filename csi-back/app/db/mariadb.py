import logging
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import declarative_base
from sqlalchemy import text
from typing import AsyncGenerator
from app.core.config import settings

logger = logging.getLogger(__name__)

Base = declarative_base()

engine = None
async_session_maker = None


async def create_database_if_not_exists():
    """如果数据库不存在则创建"""
    from urllib.parse import urlparse, urlunparse
    
    parsed = urlparse(settings.MARIADB_URL)
    db_name = parsed.path.lstrip('/')
    
    server_url = urlunparse((
        parsed.scheme,
        parsed.netloc,
        '',
        parsed.params,
        parsed.query,
        parsed.fragment
    ))
    
    temp_engine = create_async_engine(server_url, echo=False)
    try:
        async with temp_engine.connect() as conn:
            async with conn.begin():
                await conn.execute(text(
                    f"CREATE DATABASE IF NOT EXISTS {db_name} "
                    f"CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci"
                ))
            logger.info(f"数据库 {db_name} 已确保存在")
    finally:
        await temp_engine.dispose()


async def init_mariadb():
    """初始化MariaDB连接"""
    global engine, async_session_maker
    
    await create_database_if_not_exists()
    
    engine = create_async_engine(
        settings.MARIADB_URL,
        echo=settings.DEBUG,
        pool_pre_ping=True,
        pool_size=10,
        max_overflow=20,
    )
    
    async_session_maker = async_sessionmaker(
        engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )
    
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    logger.info("MariaDB 初始化完成")


async def close_mariadb():
    """关闭MariaDB连接"""
    global engine
    if engine:
        await engine.dispose()


async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    """获取数据库会话"""
    async with async_session_maker() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()
