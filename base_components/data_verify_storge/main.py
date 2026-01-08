# 验证数据格式，并存入对应elasticsearch index

import json
import logging
from typing import Dict, Any
from dotenv import load_dotenv
from csi_base_component_sdk.sync import BaseComponent
from es_client import ElasticsearchClient
from rabbitmq_client import RabbitMQClient

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)

logger = logging.getLogger(__name__)

DATA_INDEX_MAP = {
    "forums": "forums"
}

def main():
    """主函数：从 RabbitMQ 消费数据并存入 Elasticsearch"""
    component = BaseComponent()
    component.initialize()
    
    queue_names = component.inputs.get("data_in", {}).get("value", [])
    if not queue_names:
        logger.error("没有配置队列名称")
        component.fail("未找到数据输入队列名称")
    
    es_client = ElasticsearchClient()
    
    if not es_client.test_connection():
        logger.error("无法连接到 Elasticsearch，请检查配置")
        return
    
    logger.info("Elasticsearch 连接成功")
    
    index_name = 'test_index'
    
    mappings = {
        'properties': {
            'timestamp': {'type': 'date'},
            'message': {'type': 'text'},
            'level': {'type': 'keyword'}
        }
    }
    
    es_client.create_index(index_name, mappings)
    
    rabbitmq_client = RabbitMQClient()
    
    if not rabbitmq_client.test_connection():
        logger.error("无法连接到 RabbitMQ，请检查配置")
        return
    
    def handle_message(body: str, properties: Dict[str, Any]) -> bool:
        """处理 RabbitMQ 消息的回调函数"""
        try:
            data = json.loads(body)
            
            if es_client.store_data(index_name, data):
                return True
            else:
                logger.warning(f"消息存储失败: {properties.get('routing_key', 'N/A')}")
                return False
        except json.JSONDecodeError as e:
            logger.error(f"JSON 解析失败: {e}, 消息内容: {body[:100]}")
            return False
        except Exception as e:
            logger.error(f"处理消息时发生错误: {e}")
            return False
    
    queue_name = 'tmp_data'
    logger.info(f"开始消费队列: {queue_name}")
    
    try:
        processed_count = rabbitmq_client.consume_all(queue_name, handle_message)
        logger.info(f"消费完成，共处理 {processed_count} 条消息")
    finally:
        rabbitmq_client.close()


if __name__ == '__main__':
    main()