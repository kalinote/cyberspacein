import logging
from typing import List, Dict, Any, Optional
from urllib.parse import quote_plus
from pymongo import MongoClient
from pymongo.errors import ConnectionFailure, OperationFailure
from bson import ObjectId

logger = logging.getLogger(__name__)


class MongoDBStorage:
    def __init__(self, host: str, port: int, username: str = "", password: str = "", database: str = ""):
        self.host = host
        self.port = port
        self.username = username
        self.password = password
        self.database_name = database
        self.client: Optional[MongoClient] = None
        self.db = None

    def _build_uri(self) -> str:
        if self.username and self.password:
            username_escaped = quote_plus(self.username)
            password_escaped = quote_plus(self.password)
            return f"mongodb://{username_escaped}:{password_escaped}@{self.host}:{self.port}/"
        else:
            return f"mongodb://{self.host}:{self.port}/"

    def connect(self):
        try:
            uri = self._build_uri()
            self.client = MongoClient(uri)
            self.db = self.client[self.database_name]
            self.client.admin.command('ping')
            logger.info(f"MongoDB连接成功: {self.database_name}")
        except ConnectionFailure as e:
            logger.error(f"MongoDB连接失败: {e}")
            raise
        except Exception as e:
            logger.error(f"MongoDB初始化失败: {e}")
            raise

    def close(self):
        if self.client:
            self.client.close()
        logger.info("MongoDB连接已关闭")

    def _prepare_document(self, document: Dict[str, Any]) -> Dict[str, Any]:
        doc_copy = document.copy()
        if '_id' in doc_copy:
            doc_id = doc_copy['_id']
            if isinstance(doc_id, str):
                try:
                    doc_copy['_id'] = ObjectId(doc_id)
                except Exception:
                    pass
        elif 'uuid' in doc_copy:
            uuid_value = doc_copy.pop('uuid')
            doc_copy['_id'] = uuid_value
        return doc_copy

    def insert_document(self, collection_name: str, document: Dict[str, Any]) -> Any:
        if self.db is None:
            self.connect()

        try:
            collection = self.db[collection_name]
            prepared_doc = self._prepare_document(document)
            result = collection.insert_one(prepared_doc)
            return result.inserted_id
        except OperationFailure as e:
            logger.error(f"MongoDB插入文档失败: {e}")
            raise
        except Exception as e:
            logger.error(f"MongoDB操作失败: {e}")
            raise

    def insert_documents(self, collection_name: str, documents: List[Dict[str, Any]]) -> List[Any]:
        if self.db is None:
            self.connect()

        try:
            collection = self.db[collection_name]
            processed_docs = [self._prepare_document(doc) for doc in documents]
            result = collection.insert_many(processed_docs)
            return result.inserted_ids
        except OperationFailure as e:
            logger.error(f"MongoDB批量插入文档失败: {e}")
            raise
        except Exception as e:
            logger.error(f"MongoDB批量操作失败: {e}")
            raise

    def query_documents(self, collection_name: str, query: Dict[str, Any], batch_size: int = 0) -> List[Dict[str, Any]]:
        if self.db is None:
            self.connect()

        try:
            collection = self.db[collection_name]
            cursor = collection.find(query)
            
            if batch_size > 0:
                cursor = cursor.limit(batch_size)
            
            documents = []
            for doc in cursor:
                doc_dict = dict(doc)
                if '_id' in doc_dict:
                    doc_dict['_id'] = str(doc_dict['_id'])
                documents.append(doc_dict)
            
            return documents
        except OperationFailure as e:
            logger.error(f"MongoDB查询文档失败: {e}")
            raise
        except Exception as e:
            logger.error(f"MongoDB查询操作失败: {e}")
            raise

