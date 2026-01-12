import os
import logging
from typing import Dict, Any, Optional
from dotenv import load_dotenv
from elasticsearch import Elasticsearch
from elasticsearch.exceptions import RequestError

load_dotenv()

logger = logging.getLogger(__name__)


class ElasticsearchClient:
    """Elasticsearch 客户端封装类"""
    
    def __init__(self):
        """初始化 Elasticsearch 客户端"""
        self.host = os.getenv('ELASTICSEARCH_HOST', 'localhost')
        self.port = int(os.getenv('ELASTICSEARCH_PORT', '9200'))
        self.username = os.getenv('ELASTICSEARCH_USERNAME', '')
        self.password = os.getenv('ELASTICSEARCH_PASSWORD', '')
        self.use_ssl = os.getenv('ELASTICSEARCH_USE_SSL', 'false').lower() == 'true'
        self.verify_certs = os.getenv('ELASTICSEARCH_VERIFY_CERTS', 'true').lower() == 'true'
        self.ca_certs = os.getenv('ELASTICSEARCH_CA_CERTS', '')
        
        self.client = self._create_client()
    
    def _create_client(self) -> Elasticsearch:
        """创建 Elasticsearch 客户端连接"""
        http_auth = None
        if self.username and self.password:
            http_auth = (self.username, self.password)
        
        client_config = {
            'hosts': [f"{'https' if self.use_ssl else 'http'}://{self.host}:{self.port}"],
            'verify_certs': self.verify_certs,
        }
        
        if http_auth:
            client_config['http_auth'] = http_auth
        
        if self.ca_certs:
            client_config['ca_certs'] = self.ca_certs
        
        return Elasticsearch(**client_config)
    
    def test_connection(self) -> bool:
        """测试 Elasticsearch 连接"""
        try:
            return self.client.ping()
        except Exception as e:
            logger.error(f"连接测试失败: {e}")
            return False
    
    def create_index(self, index_name: str, mappings: Optional[Dict[str, Any]] = None) -> bool:
        """创建索引"""
        try:
            if not self.client.indices.exists(index=index_name):
                body = {}
                if mappings:
                    body['mappings'] = mappings
                self.client.indices.create(index=index_name, body=body)
                logger.info(f"索引 {index_name} 创建成功")
                return True
            else:
                logger.info(f"索引 {index_name} 已存在")
                return True
        except RequestError as e:
            logger.error(f"创建索引失败: {e}")
            return False
    
    def store_data(self, index_name: str, document: Dict[str, Any], doc_id: Optional[str] = None) -> bool:
        """存储数据到 Elasticsearch"""
        try:
            if doc_id:
                response = self.client.index(index=index_name, id=doc_id, document=document)
            else:
                response = self.client.index(index=index_name, document=document)
            
            if response.get('result') in ['created', 'updated']:
                # logger.info(f"数据存储成功: {response.get('_id')}")
                return True
            else:
                logger.warning(f"数据存储失败: {response}")
                return False
        except RequestError as e:
            logger.error(f"存储数据失败: {e}")
            return False
    
    def bulk_store(self, index_name: str, documents: list[Dict[str, Any]], id_field: str = "uuid") -> bool:
        """批量存储数据"""
        try:
            from elasticsearch.helpers import bulk
            
            actions = []
            for doc in documents:
                action = {
                    '_index': index_name,
                    '_source': doc
                }
                if id_field and id_field in doc:
                    action['_id'] = doc[id_field]
                actions.append(action)
            
            success, failed = bulk(self.client, actions, raise_on_error=False)
            if failed:
                logger.warning(f"批量存储部分失败: {len(failed)} 条")
                
            logger.info(f"批量存储完成: 成功 {success} 条")
            return len(failed) == 0
        except Exception as e:
            logger.error(f"批量存储失败: {e}")
            return False
