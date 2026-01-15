import logging
import json
from csi_base_component_sdk.sync import BaseComponent
from analyzer.clean_content import CleanContentAnalyzer
from analyzer.safe_raw_content import SafeRawContentAnalyzer
from rabbitmq_client import RabbitMQClient

logger = logging.getLogger("html_analyze")

def main():
    component = BaseComponent()
    component.initialize()

    enable_clean_content = component.get_config("clean_content", False)
    enable_safe_raw_content = component.get_config("safe_raw_content", False)
    process_fields = component.get_config("process_fields", "raw_content")

    data_in = component.inputs.get("data_in")
    if not data_in.get("type") == "reference":
        component.fail("输入数据类型错误")
    queue_name = data_in.get("value")
    if not queue_name:
        component.fail("未找到输入数据")

    outputs = component.outputs.get("data_out")
    if not outputs.get("type") == "reference":
        component.fail("输出数据类型错误")
    output_queue_names = outputs.get("value")
    if not output_queue_names:
        component.fail("未找到输出数据")
    if isinstance(output_queue_names, str):
        output_queue_names = [output_queue_names]
    
    client = RabbitMQClient()
    if not client.connect():
        component.fail("无法连接到 RabbitMQ")
    
    processed_count = 0
    failed_count = 0
    
    try:
        logger.info(f"开始处理队列: {queue_name}")
        
        while True:
            message = client.get_message(queue_name)
            if not message:
                break
            
            try:
                data = json.loads(message['body'])
                
                if process_fields not in data:
                    logger.warning(f"消息中未找到字段 '{process_fields}'，跳过处理")
                    client.ack_message(message['delivery_tag'])
                    continue
                
                content = data[process_fields]
                
                if not isinstance(content, str):
                    logger.warning(f"字段 '{process_fields}' 不是字符串类型，跳过处理")
                    client.ack_message(message['delivery_tag'])
                    continue
                
                if enable_clean_content:
                    try:
                        data['clean_content'] = CleanContentAnalyzer.analyze(content)
                        logger.debug(f"clean_content 处理完成")
                    except Exception as e:
                        logger.error(f"clean_content 处理失败: {e}")
                        data['clean_content'] = ""
                
                if enable_safe_raw_content:
                    try:
                        data['safe_raw_content'] = SafeRawContentAnalyzer.analyze(content)
                        logger.debug(f"safe_raw_content 处理完成")
                    except Exception as e:
                        logger.error(f"safe_raw_content 处理失败: {e}")
                        data['safe_raw_content'] = ""
                
                success_count = client.send_messages_batch(output_queue_names, data)
                
                if success_count == len(output_queue_names):
                    client.ack_message(message['delivery_tag'])
                    processed_count += 1
                    if processed_count % 10 == 0:
                        logger.info(f"已处理 {processed_count} 条消息")
                else:
                    logger.error(f"发送消息失败，成功: {success_count}/{len(output_queue_names)}")
                    client.nack_message(message['delivery_tag'], requeue=True)
                    failed_count += 1
                    
            except json.JSONDecodeError as e:
                logger.error(f"消息解析失败: {e}")
                client.nack_message(message['delivery_tag'], requeue=False)
                failed_count += 1
            except Exception as e:
                logger.error(f"处理消息时发生错误: {e}")
                client.nack_message(message['delivery_tag'], requeue=True)
                failed_count += 1
        
        logger.info(f"处理完成，成功: {processed_count}，失败: {failed_count}")
        component.finish({
            "processed": processed_count,
            "failed": failed_count
        })
        
    except Exception as e:
        logger.error(f"处理队列时发生错误: {e}")
        component.fail(f"处理队列时发生错误: {str(e)}")
    finally:
        client.close()

if __name__ == "__main__":
    main()
