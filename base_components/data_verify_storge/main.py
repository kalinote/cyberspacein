# 验证数据格式，并存入对应elasticsearch index

import json
import logging
from typing import Dict, Any
from dotenv import load_dotenv
from csi_base_component_sdk.sync import BaseComponent
from es_client import ElasticsearchClient
from rabbitmq_client import RabbitMQClient
from validator import validate_and_transform

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)

logger = logging.getLogger(__name__)

DATA_INDEX_MAP = {
    "forum": "forum",
    "article": "article"
}

def main():
    """主函数：从 RabbitMQ 消费数据并存入 Elasticsearch"""
    component = BaseComponent()
    component.initialize()
    
    # 1. 获取队列名称
    queue_names = component.inputs.get("data_in", {}).get("value", [])
    if not queue_names:
        component.fail("未找到数据输入队列名称")
    if isinstance(queue_names, str):
        queue_names = [queue_names]
        

    # 2. 初始化客户端
    es_client = ElasticsearchClient()
    if not es_client.test_connection():
        component.fail("无法连接到 Elasticsearch")

    rabbitmq_client = RabbitMQClient()
    if not rabbitmq_client.connect():
        component.fail("无法连接到 RabbitMQ")

    # 3. 定义消息处理回调 (批量)
    def process_batch(messages: list) -> bool:
        if not messages:
            return True
            
        # 按索引分组数据
        batch_data: Dict[str, list] = {}
        
        for body, properties in messages:
            try:
                data = json.loads(body)
            except json.JSONDecodeError:
                logger.error("无法解析 JSON 数据")
                continue # 格式错误忽略，不中断批次
            
            # 验证并转换数据
            validated_data = validate_and_transform(data)
            if not validated_data:
                continue
                
            entity_type = validated_data.get("entity_type")
            index_name = DATA_INDEX_MAP.get(entity_type)
            
            if not index_name:
                logger.error(f"未找到对应的 index: {entity_type}")
                continue
                
            if index_name not in batch_data:
                batch_data[index_name] = []
            
            batch_data[index_name].append(validated_data)
            
        # 批量写入 ES
        all_success = True
        for index_name, documents in batch_data.items():
            if not documents:
                continue
                
            if not es_client.bulk_store(index_name, documents, id_field="uuid"):
                all_success = False
                # 注意：这里如果一个索引失败，可能会导致整个批次重试
                # 实际生产中可能需要更精细的错误处理，比如记录失败的 ID
        
        return all_success

    # 4. 消费队列
    try:
        total_processed = 0
        batch_size = 500  # 设置批量大小
        
        for queue_name in queue_names:
            logger.info(f"开始消费队列: {queue_name} (批量大小: {batch_size})")
            count = rabbitmq_client.consume_all(queue_name, process_batch, batch_size=batch_size)
            total_processed += count
            logger.info(f"队列 {queue_name} 消费完成，共处理 {count} 条消息")
        
        # 5. 完成任务
        rabbitmq_client.close()
        component.finish({
            "total_processed": total_processed
        })
        
    except Exception as e:
        logger.error(f"处理过程中发生未捕获异常: {e}")
        component.fail(f"处理失败: {str(e)}")

if __name__ == '__main__':
    main()
