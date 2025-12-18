import logging
from elasticsearch import AsyncElasticsearch
from app.core.config import settings

logger = logging.getLogger(__name__)

es_client: AsyncElasticsearch = None


async def init_elasticsearch():
    """初始化Elasticsearch连接"""
    global es_client
    
    es_client = AsyncElasticsearch(
        hosts=[settings.ELASTICSEARCH_URL],
        basic_auth=(settings.ELASTICSEARCH_USER, settings.ELASTICSEARCH_PASSWORD) if settings.ELASTICSEARCH_USER else None,
        verify_certs=False,
        ssl_show_warn=False,
        max_retries=3,
        retry_on_timeout=True
    )
    
    info = await es_client.info()
    logger.info(f"已连接到Elasticsearch: {info['version']['number']}")


async def close_elasticsearch():
    """关闭Elasticsearch连接"""
    global es_client
    if es_client:
        await es_client.close()


def get_es() -> AsyncElasticsearch:
    """获取Elasticsearch客户端实例"""
    return es_client
