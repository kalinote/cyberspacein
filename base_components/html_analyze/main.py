import logging
import json
from csi_base_component_sdk.sync import BaseComponent
from analyzer.clean_content import CleanContentAnalyzer
from analyzer.safe_raw_content import SafeRawContentAnalyzer
from rabbitmq_client import RabbitMQClient

logger = logging.getLogger("html_analyze")

def process_single_data(data, process_fields, enable_clean_content, enable_safe_raw_content):
    if process_fields not in data:
        raise ValueError(f"数据中未找到字段 '{process_fields}'")
    
    content = data[process_fields]
    
    if not isinstance(content, str):
        raise TypeError(f"字段 '{process_fields}' 不是字符串类型")
    
    if enable_clean_content:
        try:
            data['clean_content'] = CleanContentAnalyzer.analyze(content)
            logger.debug(f"clean_content 处理完成")
        except Exception as e:
            logger.error(f"clean_content 处理失败: {e}")
            data['clean_content'] = None
    
    if enable_safe_raw_content:
        try:
            data['safe_raw_content'] = SafeRawContentAnalyzer.analyze(content)
            logger.debug(f"safe_raw_content 处理完成")
        except Exception as e:
            logger.error(f"safe_raw_content 处理失败: {e}")
            data['safe_raw_content'] = None
    
    return data

def main():
    component = BaseComponent()
    component.initialize()

    enable_clean_content = component.get_config("clean_content", False)
    enable_safe_raw_content = component.get_config("safe_raw_content", False)
    process_fields = component.get_config("process_fields", "raw_content")

    queue_name = component.inputs.get("data_in", {}).get("value")
    dict_value = component.inputs.get("dict_in", {}).get("value")
    
    has_queue_input = bool(queue_name)
    has_dict_input = bool(dict_value)
    
    processed_count = 0
    failed_count = 0
    handled_dict = None
    dict_error = None
    
    client = None
    
    try:
        if has_queue_input:
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
            
            logger.info(f"开始处理队列: {queue_name}")
            
            while True:
                message = client.get_message(queue_name)
                if not message:
                    break
                
                try:
                    data = json.loads(message['body'])
                    
                    try:
                        data = process_single_data(data, process_fields, enable_clean_content, enable_safe_raw_content)
                    except (ValueError, TypeError) as e:
                        logger.warning(f"{e}，跳过处理")
                        client.ack_message(message['delivery_tag'])
                        continue
                    
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
            
            logger.info(f"队列处理完成，成功: {processed_count}，失败: {failed_count}")
        
        if has_dict_input:
            logger.info("开始处理字典输入")
            try:
                handled_dict = process_single_data(dict_value, process_fields, enable_clean_content, enable_safe_raw_content)
                logger.info("字典处理完成")
            except Exception as e:
                logger.error(f"字典处理失败: {e}")
                dict_error = str(e)
        
        if has_queue_input and has_dict_input:
            if processed_count == 0 and dict_error:
                component.fail(f"处理失败: 队列成功0条，字典处理失败: {dict_error}")
            else:
                result = {
                    "processed": processed_count,
                    "failed": failed_count
                }
                if handled_dict is not None:
                    result["dict_out"] = handled_dict
                component.finish(result)
        elif has_queue_input:
            if processed_count == 0:
                component.fail(f"队列处理失败: 成功0条，失败{failed_count}条")
            else:
                component.finish({
                    "processed": processed_count,
                    "failed": failed_count
                })
        elif has_dict_input:
            if dict_error:
                component.fail(f"字典处理失败: {dict_error}")
            else:
                component.finish({
                    "dict_out": handled_dict
                })
        else:
            component.fail("未提供任何输入数据")
            
    except Exception as e:
        logger.error(f"处理过程发生错误: {e}")
        component.fail(f"处理过程发生错误: {str(e)}")
    finally:
        if client:
            client.close()
        

if __name__ == "__main__":
    main()

