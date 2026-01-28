import json
import logging
from typing import Dict
from dotenv import load_dotenv
from csi_base_component_sdk import BaseComponent
from es_client import ElasticsearchClient
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
    with BaseComponent(enable_rabbitmq=True) as component:
        queue_names = component.inputs.get("data_in", {}).get("value", [])
        if not queue_names:
            component.fail("未找到数据输入队列名称")
        if isinstance(queue_names, str):
            queue_names = [queue_names]

        es_client = ElasticsearchClient()
        if not es_client.test_connection():
            component.fail("无法连接到 Elasticsearch")

        def process_batch(messages: list) -> bool:
            if not messages:
                return True
                
            batch_data: Dict[str, list] = {}
            
            for body, properties in messages:
                try:
                    data = json.loads(body)
                except json.JSONDecodeError:
                    logger.error("无法解析 JSON 数据")
                    continue
                
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
                
            all_success = True
            for index_name, documents in batch_data.items():
                if not documents:
                    continue
                    
                if not es_client.bulk_store(index_name, documents, id_field="uuid"):
                    all_success = False
            
            return all_success

        try:
            total_processed = 0
            batch_size = 500
            
            for queue_name in queue_names:
                logger.info(f"开始消费队列: {queue_name} (批量大小: {batch_size})")
                count = component.rabbitmq.consume_all(queue_name, process_batch, batch_size=batch_size)
                total_processed += count
                logger.info(f"队列 {queue_name} 消费完成，共处理 {count} 条消息")
            
            component.finish({
                "total_processed": total_processed
            })
            
        except Exception as e:
            logger.error(f"处理过程中发生未捕获异常: {e}")
            component.fail(f"处理失败: {str(e)}")

if __name__ == '__main__':
    main()
