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
    data_out = outputs.get('data_out', {})
    if isinstance(data_out, dict) and data_out.get('type') == 'reference':
        value = data_out.get('value', [])
        if isinstance(value, list):
            return value
        elif isinstance(value, str):
            return [value]
    return []


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


def main():
    try:
        base_component = BaseComponent()
        base_component.initialize()
        
        config = base_component.config
        inputs = base_component.inputs
        outputs = base_component.outputs
        
        target = config.get('target', '')
        target_name = config.get('target_name', '')
        
        if not target or not target_name:
            base_component.fail("配置缺少target或target_name")
            return
        
        input_queues = get_input_queues(inputs)
        if not input_queues:
            base_component.fail("未找到输入队列配置")
            return
        
        output_queues = get_output_queues(outputs)
        
        logger.info(f"目标类型: {target}, 目标名称: {target_name}")
        logger.info(f"输入队列: {input_queues}")
        if output_queues:
            logger.info(f"输出队列: {output_queues}")
        
        rabbitmq_config = get_rabbitmq_config()
        reader = RabbitMQReader(**rabbitmq_config)
        
        try:
            reader.connect()
            
            total_processed = 0
            total_success = 0
            total_errors = 0
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
                        output_queues
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
            
            logger.info(f"处理完成: 总计 {total_processed} 条，成功 {total_success} 条，失败 {total_errors} 条")
            
            base_component.finish({
                "total_processed": total_processed,
                "total_success": total_success,
                "total_errors": total_errors
            })
        
        finally:
            reader.close()
    
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

