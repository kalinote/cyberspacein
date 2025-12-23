import logging
from typing import List, Dict, Any, Optional
from elasticsearch import Elasticsearch
from elasticsearch.exceptions import ConnectionError, RequestError

logger = logging.getLogger(__name__)


class ElasticsearchStorage:
    def __init__(self, hosts: str, username: str = "", password: str = ""):
        self.hosts = hosts.split(',') if isinstance(hosts, str) else hosts
        self.username = username
        self.password = password
        self.client: Optional[Elasticsearch] = None

    def connect(self):
        try:
            if self.username and self.password:
                self.client = Elasticsearch(
                    hosts=self.hosts,
                    basic_auth=(self.username, self.password)
                )
            else:
                self.client = Elasticsearch(hosts=self.hosts)
            
            if not self.client.ping():
                raise ConnectionError("无法连接到Elasticsearch")
            
            logger.info(f"Elasticsearch连接成功: {self.hosts}")
        except ConnectionError as e:
            logger.error(f"Elasticsearch连接失败: {e}")
            raise
        except Exception as e:
            logger.error(f"Elasticsearch初始化失败: {e}")
            raise

    def close(self):
        if self.client:
            self.client.close()
        logger.info("Elasticsearch连接已关闭")

    def _extract_id(self, document: Dict[str, Any]) -> Optional[str]:
        if '_id' in document:
            doc_id = document.pop('_id')
            return str(doc_id) if doc_id is not None else None
        elif 'uuid' in document:
            uuid_value = document.pop('uuid')
            return str(uuid_value) if uuid_value is not None else None
        return None

    def index_document(self, index_name: str, document: Dict[str, Any]) -> Dict[str, Any]:
        if not self.client:
            self.connect()

        try:
            doc_copy = document.copy()
            doc_id = self._extract_id(doc_copy)
            
            if doc_id:
                result = self.client.index(index=index_name, id=doc_id, document=doc_copy)
            else:
                result = self.client.index(index=index_name, document=doc_copy)
            
            return result
        except RequestError as e:
            logger.error(f"Elasticsearch索引文档失败: {e}")
            raise
        except Exception as e:
            logger.error(f"Elasticsearch操作失败: {e}")
            raise

    def index_documents(self, index_name: str, documents: List[Dict[str, Any]]) -> Dict[str, Any]:
        if not self.client:
            self.connect()

        try:
            from elasticsearch.helpers import bulk
            
            actions = []
            for doc in documents:
                doc_copy = doc.copy()
                doc_id = self._extract_id(doc_copy)
                
                action = {
                    '_index': index_name,
                    '_source': doc_copy
                }
                
                if doc_id:
                    action['_id'] = doc_id
                
                actions.append(action)
            
            result = bulk(self.client, actions)
            return result
        except RequestError as e:
            logger.error(f"Elasticsearch批量索引文档失败: {e}")
            raise
        except Exception as e:
            logger.error(f"Elasticsearch批量操作失败: {e}")
            raise

