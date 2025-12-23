import json
import logging
import os
import sys
from typing import List, Dict, Any
from dotenv import load_dotenv

from csi_base_component_sdk.sync import BaseComponent
from rabbitmq import RabbitMQReader, RabbitMQWriter
from mongodb import MongoDBStorage
from elasticsearch_storage import ElasticsearchStorage
from redis_storage import RedisStorage
from file_storage import FileStorage

logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] [%(levelname)s] %(message)s',
    datefmt='%H:%M:%S'
)
logger = logging.getLogger(__name__)

load_dotenv()

BATCH_SIZE = 100


def get_rabbitmq_config():
    return {
        'host': os.getenv('RABBITMQ_HOST', 'localhost'),
        'port': int(os.getenv('RABBITMQ_PORT', '5672')),
        'username': os.getenv('RABBITMQ_USERNAME', 'guest'),
        'password': os.getenv('RABBITMQ_PASSWORD', 'guest'),
        'vhost': os.getenv('RABBITMQ_VHOST', '/')
    }


def get_mongodb_config():
    return {
        'host': os.getenv('MONGODB_HOST', 'localhost'),
        'port': int(os.getenv('MONGODB_PORT', '27017')),
        'username': os.getenv('MONGODB_USERNAME', ''),
        'password': os.getenv('MONGODB_PASSWORD', ''),
        'database': os.getenv('MONGODB_DATABASE', 'default_db')
    }


def get_elasticsearch_config():
    return {
        'hosts': os.getenv('ELASTICSEARCH_HOSTS', 'http://localhost:9200'),
        'username': os.getenv('ELASTICSEARCH_USERNAME', ''),
        'password': os.getenv('ELASTICSEARCH_PASSWORD', '')
    }


def get_redis_config():
    return {
        'host': os.getenv('REDIS_HOST', 'localhost'),
        'port': int(os.getenv('REDIS_PORT', '6379')),
        'password': os.getenv('REDIS_PASSWORD', ''),
        'db': int(os.getenv('REDIS_DB', '0'))
    }


def get_input_queues(inputs: Dict[str, Any]) -> List[str]:
    data_in = inputs.get('data_in', {})
    if isinstance(data_in, dict) and data_in.get('type') == 'reference':
        value = data_in.get('value', [])
        if isinstance(value, list):
            return value
        elif isinstance(value, str):
            return [value]
    return []


def get_output_queues(outputs: Dict[str, Any]) -> List[str]:
    direct_out = outputs.get('direct_out', {})
    if isinstance(direct_out, dict) and direct_out.get('type') == 'reference':
        value = direct_out.get('value', [])
        if isinstance(value, list):
            return value
        elif isinstance(value, str):
            return [value]
    return []


def get_data_output_queues(outputs: Dict[str, Any]) -> List[str]:
    data_out = outputs.get('data_out', {})
    if isinstance(data_out, dict) and data_out.get('type') == 'reference':
        value = data_out.get('value', [])
        if isinstance(value, list):
            return value
        elif isinstance(value, str):
            return [value]
    return []


def build_elasticsearch_query(conditions: List[Dict[str, Any]]) -> Dict[str, Any]:
    if not conditions:
        return {"match_all": {}}
    
    must_clauses = []
    must_not_clauses = []
    
    for condition in conditions:
        field = condition.get('field', '')
        operator = condition.get('operator', '')
        value = condition.get('value')
        
        if not field or operator not in ['eq', 'ne', 'gt', 'lt', 'gte', 'lte', 'in', 'contains']:
            continue
        
        if operator == 'eq':
            must_clauses.append({"term": {field: value}})
        elif operator == 'ne':
            must_not_clauses.append({"term": {field: value}})
        elif operator == 'gt':
            must_clauses.append({"range": {field: {"gt": value}}})
        elif operator == 'lt':
            must_clauses.append({"range": {field: {"lt": value}}})
        elif operator == 'gte':
            must_clauses.append({"range": {field: {"gte": value}}})
        elif operator == 'lte':
            must_clauses.append({"range": {field: {"lte": value}}})
        elif operator == 'in':
            if isinstance(value, list):
                must_clauses.append({"terms": {field: value}})
            else:
                must_clauses.append({"term": {field: value}})
        elif operator == 'contains':
            must_clauses.append({"match": {field: value}})
    
    query = {}
    if must_clauses or must_not_clauses:
        bool_query = {}
        if must_clauses:
            bool_query["must"] = must_clauses
        if must_not_clauses:
            bool_query["must_not"] = must_not_clauses
        query = {"bool": bool_query}
    else:
        query = {"match_all": {}}
    
    return query


def build_mongodb_query(conditions: List[Dict[str, Any]]) -> Dict[str, Any]:
    if not conditions:
        return {}
    
    query = {}
    
    for condition in conditions:
        field = condition.get('field', '')
        operator = condition.get('operator', '')
        value = condition.get('value')
        
        if not field or operator not in ['eq', 'ne', 'gt', 'lt', 'gte', 'lte', 'in', 'contains']:
            continue
        
        if operator == 'eq':
            query[field] = value
        elif operator == 'ne':
            query[field] = {"$ne": value}
        elif operator == 'gt':
            if field not in query:
                query[field] = {}
            query[field]["$gt"] = value
        elif operator == 'lt':
            if field not in query:
                query[field] = {}
            query[field]["$lt"] = value
        elif operator == 'gte':
            if field not in query:
                query[field] = {}
            query[field]["$gte"] = value
        elif operator == 'lte':
            if field not in query:
                query[field] = {}
            query[field]["$lte"] = value
        elif operator == 'in':
            if isinstance(value, list):
                query[field] = {"$in": value}
            else:
                query[field] = value
        elif operator == 'contains':
            query[field] = {"$regex": str(value), "$options": "i"}
    
    return query


def build_redis_filter(conditions: List[Dict[str, Any]]):
    if not conditions:
        return None
    
    def filter_func(doc: Dict[str, Any]) -> bool:
        for condition in conditions:
            field = condition.get('field', '')
            operator = condition.get('operator', '')
            value = condition.get('value')
            
            if not field or operator not in ['eq', 'ne', 'gt', 'lt', 'gte', 'lte', 'in', 'contains']:
                continue
            
            doc_value = doc.get(field)
            
            if operator == 'eq':
                if doc_value != value:
                    return False
            elif operator == 'ne':
                if doc_value == value:
                    return False
            elif operator == 'gt':
                if not (isinstance(doc_value, (int, float)) and isinstance(value, (int, float)) and doc_value > value):
                    return False
            elif operator == 'lt':
                if not (isinstance(doc_value, (int, float)) and isinstance(value, (int, float)) and doc_value < value):
                    return False
            elif operator == 'gte':
                if not (isinstance(doc_value, (int, float)) and isinstance(value, (int, float)) and doc_value >= value):
                    return False
            elif operator == 'lte':
                if not (isinstance(doc_value, (int, float)) and isinstance(value, (int, float)) and doc_value <= value):
                    return False
            elif operator == 'in':
                if isinstance(value, list):
                    if doc_value not in value:
                        return False
                else:
                    if doc_value != value:
                        return False
            elif operator == 'contains':
                if not (isinstance(doc_value, str) and isinstance(value, str) and value in doc_value):
                    return False
        
        return True
    
    return filter_func


def build_file_filter(conditions: List[Dict[str, Any]]):
    return build_redis_filter(conditions)


def process_messages(
    base_component: BaseComponent,
    messages: List[Dict[str, Any]],
    target: str,
    target_name: str,
    output_queues: List[str]
):
    rabbitmq_config = get_rabbitmq_config()
    mongodb_config = get_mongodb_config()
    elasticsearch_config = get_elasticsearch_config()
    redis_config = get_redis_config()
    
    success_count = 0
    error_count = 0
    message_bodies = [msg_data['body'] for msg_data in messages]
    
    try:
        if target == 'rabbitmq':
            writer = RabbitMQWriter(**rabbitmq_config)
            try:
                writer.connect()
                writer.publish_messages(target_name, message_bodies)
                success_count = len(message_bodies)
            finally:
                writer.close()
        
        elif target == 'mongodb':
            storage = MongoDBStorage(**mongodb_config)
            try:
                storage.connect()
                storage.insert_documents(target_name, message_bodies)
                success_count = len(message_bodies)
            finally:
                storage.close()
        
        elif target == 'elasticsearch':
            storage = ElasticsearchStorage(**elasticsearch_config)
            try:
                storage.connect()
                storage.index_documents(target_name, message_bodies)
                success_count = len(message_bodies)
            finally:
                storage.close()
        
        elif target == 'redis':
            storage = RedisStorage(**redis_config)
            try:
                storage.connect()
                storage.set_documents(target_name, message_bodies)
                success_count = len(message_bodies)
            finally:
                storage.close()
        
        elif target == 'file':
            storage = FileStorage()
            storage.append_documents(target_name, message_bodies)
            success_count = len(message_bodies)
        
        else:
            logger.warning(f"未知的目标类型: {target}")
            error_count = len(message_bodies)
            return success_count, error_count
        
        if output_queues:
            writer = RabbitMQWriter(**rabbitmq_config)
            try:
                writer.connect()
                for queue_name in output_queues:
                    writer.publish_messages(queue_name, message_bodies)
            finally:
                writer.close()
    
    except Exception as e:
        logger.error(f"批量处理消息失败: {e}")
        for msg_data in messages:
            try:
                message_body = msg_data['body']
                
                if target == 'rabbitmq':
                    writer = RabbitMQWriter(**rabbitmq_config)
                    try:
                        writer.connect()
                        writer.publish_message(target_name, message_body)
                        success_count += 1
                    finally:
                        writer.close()
                
                elif target == 'mongodb':
                    storage = MongoDBStorage(**mongodb_config)
                    try:
                        storage.connect()
                        storage.insert_document(target_name, message_body)
                        success_count += 1
                    finally:
                        storage.close()
                
                elif target == 'elasticsearch':
                    storage = ElasticsearchStorage(**elasticsearch_config)
                    try:
                        storage.connect()
                        storage.index_document(target_name, message_body)
                        success_count += 1
                    finally:
                        storage.close()
                
                elif target == 'redis':
                    storage = RedisStorage(**redis_config)
                    try:
                        storage.connect()
                        storage.set_document(target_name, message_body)
                        success_count += 1
                    finally:
                        storage.close()
                
                elif target == 'file':
                    storage = FileStorage()
                    storage.append_documents(target_name, [message_body])
                    success_count += 1
                
                if output_queues:
                    writer = RabbitMQWriter(**rabbitmq_config)
                    try:
                        writer.connect()
                        for queue_name in output_queues:
                            writer.publish_message(queue_name, message_body)
                    finally:
                        writer.close()
            
            except Exception as e2:
                logger.error(f"处理单条消息失败: {e2}")
                error_count += 1
                continue
    
    return success_count, error_count


def read_from_storage(
    target: str,
    target_name: str,
    conditions: List[Dict[str, Any]] = None,
    batch_size: int = 0
) -> List[Dict[str, Any]]:
    rabbitmq_config = get_rabbitmq_config()
    mongodb_config = get_mongodb_config()
    elasticsearch_config = get_elasticsearch_config()
    redis_config = get_redis_config()
    
    if conditions is None:
        conditions = []
    
    documents = []
    
    try:
        if target == 'rabbitmq':
            reader = RabbitMQReader(**rabbitmq_config)
            try:
                reader.connect()
                all_messages = []
                while True:
                    messages = reader.read_messages(target_name, BATCH_SIZE)
                    if not messages:
                        break
                    all_messages.extend([msg['body'] for msg in messages])
                    delivery_tags = [msg['delivery_tag'] for msg in messages]
                    reader.acknowledge_messages(delivery_tags)
                documents = all_messages
            finally:
                reader.close()
        
        elif target == 'mongodb':
            storage = MongoDBStorage(**mongodb_config)
            try:
                storage.connect()
                query = build_mongodb_query(conditions) if conditions else {}
                documents = storage.query_documents(target_name, query, batch_size)
            finally:
                storage.close()
        
        elif target == 'elasticsearch':
            storage = ElasticsearchStorage(**elasticsearch_config)
            try:
                storage.connect()
                query = build_elasticsearch_query(conditions) if conditions else build_elasticsearch_query([])
                documents = storage.query_documents(target_name, query, batch_size)
            finally:
                storage.close()
        
        elif target == 'redis':
            storage = RedisStorage(**redis_config)
            try:
                storage.connect()
                filter_func = build_redis_filter(conditions) if conditions else None
                documents = storage.query_documents(target_name, filter_func, batch_size)
            finally:
                storage.close()
        
        elif target == 'file':
            storage = FileStorage()
            filter_func = None
            actual_batch_size = 0
            documents = storage.query_documents(target_name, filter_func, actual_batch_size)
        
        else:
            logger.warning(f"未知的目标类型: {target}")
            return []
    
    except Exception as e:
        logger.error(f"从存储读取数据失败: {e}")
        raise
    
    return documents


def main():
    try:
        base_component = BaseComponent()
        base_component.initialize()
        
        config = base_component.config
        inputs = base_component.inputs if hasattr(base_component, 'inputs') else {}
        outputs = base_component.outputs if hasattr(base_component, 'outputs') else {}
        
        target = config.get('target', '')
        target_name = config.get('target_name', '')
        
        if not target or not target_name:
            base_component.fail("配置缺少target或target_name")
            return
        
        input_queues = get_input_queues(inputs)
        direct_output_queues = get_output_queues(outputs)
        data_output_queues = get_data_output_queues(outputs)
        
        logger.info(f"目标类型: {target}, 目标名称: {target_name}")
        if input_queues:
            logger.info(f"输入队列: {input_queues}")
        if direct_output_queues:
            logger.info(f"直接输出队列: {direct_output_queues}")
        if data_output_queues:
            logger.info(f"数据输出队列: {data_output_queues}")
        
        total_processed = 0
        total_success = 0
        total_errors = 0
        
        if input_queues:
            rabbitmq_config = get_rabbitmq_config()
            reader = RabbitMQReader(**rabbitmq_config)
            
            try:
                reader.connect()
                
                batch_number = 0
                
                for queue_name in input_queues:
                    logger.info(f"开始处理队列: {queue_name}")
                    
                    while True:
                        messages = reader.read_messages(queue_name, BATCH_SIZE)
                        
                        if not messages:
                            logger.info(f"队列 {queue_name} 处理完成")
                            break
                        
                        batch_number += 1
                        logger.info(f"批次 {batch_number}: 读取到 {len(messages)} 条消息")
                        
                        success_count, error_count = process_messages(
                            base_component,
                            messages,
                            target,
                            target_name,
                            direct_output_queues
                        )
                        
                        delivery_tags = [msg['delivery_tag'] for msg in messages]
                        reader.acknowledge_messages(delivery_tags)
                        
                        total_processed += len(messages)
                        total_success += success_count
                        total_errors += error_count
                        
                        progress = min(90, batch_number * 10)
                        base_component.report_progress(
                            progress,
                            f"已处理 {total_processed} 条消息，成功 {total_success} 条，失败 {total_errors} 条"
                        )
            
            finally:
                reader.close()
        
        if data_output_queues:
            logger.info("开始从存储读取数据")
            
            ## TODO: 条件后续使用handle输入，以便于构建复杂条件
            conditions = config.get('conditions', [])
            batch_size = config.get('batch_size', 0)
            
            if target in ['rabbitmq', 'file']:
                logger.info(f"目标类型 {target} 不支持条件查询和数量限制，将读取全部数据")
                conditions = []
                batch_size = 0
            
            try:
                documents = read_from_storage(
                    target,
                    target_name,
                    conditions if conditions else None,
                    batch_size if batch_size > 0 else 0
                )
                
                logger.info(f"从存储读取到 {len(documents)} 条数据")
                
                if documents:
                    rabbitmq_config = get_rabbitmq_config()
                    writer = RabbitMQWriter(**rabbitmq_config)
                    try:
                        writer.connect()
                        for queue_name in data_output_queues:
                            writer.publish_messages(queue_name, documents)
                            logger.info(f"已将 {len(documents)} 条数据输出到队列: {queue_name}")
                    finally:
                        writer.close()
                
                total_processed += len(documents)
                total_success += len(documents)
            
            except Exception as e:
                logger.error(f"从存储读取数据失败: {e}")
                total_errors += 1
                raise
        
        if not input_queues and not data_output_queues:
            base_component.fail("未配置输入队列或数据输出队列")
            return
        
        logger.info(f"处理完成: 总计 {total_processed} 条，成功 {total_success} 条，失败 {total_errors} 条")
        
        base_component.finish({
            "total_processed": total_processed,
            "total_success": total_success,
            "total_errors": total_errors
        })
    
    except KeyboardInterrupt:
        logger.info("收到中断信号，正在退出...")
        sys.exit(0)
    except Exception as e:
        logger.error(f"程序执行失败: {e}", exc_info=True)
        if 'base_component' in locals():
            base_component.fail(str(e))
        sys.exit(1)


if __name__ == '__main__':
    main()

