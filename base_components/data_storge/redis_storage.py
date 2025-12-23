import json
import logging
from typing import List, Dict, Any, Optional
import redis
from redis.exceptions import ConnectionError, RedisError

logger = logging.getLogger(__name__)


class RedisStorage:
    def __init__(self, host: str, port: int, password: str = "", db: int = 0):
        self.host = host
        self.port = port
        self.password = password
        self.db = db
        self.client: Optional[redis.Redis] = None

    def connect(self):
        try:
            self.client = redis.Redis(
                host=self.host,
                port=self.port,
                password=self.password if self.password else None,
                db=self.db,
                decode_responses=False
            )
            self.client.ping()
            logger.info(f"Redis连接成功: {self.host}:{self.port}")
        except ConnectionError as e:
            logger.error(f"Redis连接失败: {e}")
            raise
        except Exception as e:
            logger.error(f"Redis初始化失败: {e}")
            raise

    def close(self):
        if self.client:
            self.client.close()
        logger.info("Redis连接已关闭")

    def _build_key(self, key_prefix: str, document: Dict[str, Any]) -> str:
        if '_id' in document:
            doc_id = document['_id']
            return f"{key_prefix}:{doc_id}"
        elif 'uuid' in document:
            uuid_value = document['uuid']
            return f"{key_prefix}:{uuid_value}"
        else:
            import uuid
            return f"{key_prefix}:{uuid.uuid4().hex}"

    def _serialize_value(self, document: Dict[str, Any]) -> bytes:
        return json.dumps(document, ensure_ascii=False).encode('utf-8')

    def set_document(self, key_prefix: str, document: Dict[str, Any]):
        if self.client is None:
            self.connect()

        try:
            key = self._build_key(key_prefix, document)
            value = self._serialize_value(document)
            self.client.set(key, value)
            return key
        except RedisError as e:
            logger.error(f"Redis设置文档失败: {e}")
            raise
        except Exception as e:
            logger.error(f"Redis操作失败: {e}")
            raise

    def set_documents(self, key_prefix: str, documents: List[Dict[str, Any]]):
        if self.client is None:
            self.connect()

        try:
            pipe = self.client.pipeline()
            keys = []
            
            for doc in documents:
                key = self._build_key(key_prefix, doc)
                value = self._serialize_value(doc)
                pipe.set(key, value)
                keys.append(key)
            
            pipe.execute()
            return keys
        except RedisError as e:
            logger.error(f"Redis批量设置文档失败: {e}")
            raise
        except Exception as e:
            logger.error(f"Redis批量操作失败: {e}")
            raise

    def query_documents(self, key_prefix: str, filter_func=None, batch_size: int = 0) -> List[Dict[str, Any]]:
        if self.client is None:
            self.connect()

        try:
            pattern = f"{key_prefix}:*"
            documents = []
            
            cursor = 0
            while True:
                cursor, keys = self.client.scan(cursor, match=pattern, count=100)
                
                for key in keys:
                    value = self.client.get(key)
                    if value:
                        try:
                            doc = json.loads(value.decode('utf-8'))
                            if filter_func is None or filter_func(doc):
                                documents.append(doc)
                        except (json.JSONDecodeError, UnicodeDecodeError) as e:
                            logger.warning(f"Redis键 {key} 的值解析失败: {e}")
                            continue
                
                if cursor == 0:
                    break
            
            if batch_size > 0 and len(documents) > batch_size:
                documents = documents[:batch_size]
            
            return documents
        except RedisError as e:
            logger.error(f"Redis查询文档失败: {e}")
            raise
        except Exception as e:
            logger.error(f"Redis查询操作失败: {e}")
            raise

