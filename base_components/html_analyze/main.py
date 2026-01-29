import logging
import json
from typing import Callable, TYPE_CHECKING
from dotenv import load_dotenv

load_dotenv()

from csi_base_component_sdk import BaseComponent
from analyzer import ml_client
from analyzer.media_localizer import MediaLocalizer

if TYPE_CHECKING:
    from csi_base_component_sdk import RabbitMQClient

logger = logging.getLogger("html_analyze")


def create_heartbeat_callback(rabbitmq: "RabbitMQClient | None") -> Callable[[], None] | None:
    if rabbitmq is None:
        return None
    
    def heartbeat_callback():
        rabbitmq.process_data_events()
    
    return heartbeat_callback

def _parse_size_limit(size_str: str) -> int | None:
    """解析大小限制字符串，支持 M、MB、K、KB、G、GB 等单位，默认单位为字节"""
    if not size_str or not isinstance(size_str, str):
        return None
    
    size_str = size_str.strip().upper()
    if not size_str:
        return None
    
    try:
        if size_str.endswith('GB'):
            return int(float(size_str[:-2]) * 1024 * 1024 * 1024)
        elif size_str.endswith('G'):
            return int(float(size_str[:-1]) * 1024 * 1024 * 1024)
        elif size_str.endswith('MB'):
            return int(float(size_str[:-2]) * 1024 * 1024)
        elif size_str.endswith('M'):
            return int(float(size_str[:-1]) * 1024 * 1024)
        elif size_str.endswith('KB'):
            return int(float(size_str[:-2]) * 1024)
        elif size_str.endswith('K'):
            return int(float(size_str[:-1]) * 1024)
        else:
            return int(float(size_str))
    except (ValueError, TypeError):
        logger.warning(f"无法解析下载大小限制: {size_str}，将使用默认值")
        return None

def process_single_data(data, process_fields, enable_clean_content, enable_safe_raw_content, 
                        enable_media_localization, base_url_field, download_size_limit,
                        heartbeat_callback: Callable[[], None] | None = None):
    if process_fields not in data:
        raise ValueError(f"数据中未找到字段 '{process_fields}'")
    
    content = data[process_fields]
    
    if not isinstance(content, str):
        raise TypeError(f"字段 '{process_fields}' 不是字符串类型")
    
    base_url = None
    if base_url_field and base_url_field in data:
        base_url = data[base_url_field]
        if base_url and not isinstance(base_url, str):
            logger.warning(f"base_url字段 '{base_url_field}' 的值不是字符串类型，忽略")
            base_url = None
    
    request_uuid = "0"
    datas = [{"uuid": request_uuid, "html": content}]

    if enable_clean_content:
        try:
            text_list = ml_client.extract_text_batch(datas)
            item = next((x for x in text_list if x.get("uuid") == request_uuid), None)
            data["clean_content"] = item.get("text") if item else None
            if item is not None:
                logger.debug("clean_content 处理完成")
            else:
                logger.warning("clean_content 接口未返回对应 uuid 结果")
        except Exception as e:
            logger.error(f"clean_content 处理失败: {e}")
            data["clean_content"] = None

    if enable_safe_raw_content:
        try:
            clean_list = ml_client.clean_batch(datas)
            clean_item = next((x for x in clean_list if x.get("uuid") == request_uuid), None)
            cleaned_html = clean_item.get("html") if clean_item else None
            if cleaned_html is None:
                logger.warning("clean_batch 接口未返回对应 uuid 结果")
                data["safe_raw_content"] = None
            elif enable_media_localization:
                links_list = ml_client.extract_links_batch(datas)
                links_item = next((x for x in links_list if x.get("uuid") == request_uuid), None)
                links = links_item.get("links", []) if links_item and isinstance(links_item.get("links"), list) else []
                localizer = MediaLocalizer(base_url=base_url, download_size_limit=download_size_limit)
                data["safe_raw_content"] = localizer.localize(
                    cleaned_html, links, heartbeat_callback=heartbeat_callback
                )
                logger.debug("safe_raw_content 处理完成")
            else:
                data["safe_raw_content"] = cleaned_html
                logger.debug("safe_raw_content 处理完成")
        except Exception as e:
            logger.error(f"safe_raw_content 处理失败: {e}")
            data["safe_raw_content"] = None

    return data

def main():
    with BaseComponent(enable_rabbitmq=True) as component:
        enable_clean_content = component.get_config("clean_content", False)
        enable_safe_raw_content = component.get_config("safe_raw_content", False)
        enable_media_localization = component.get_config("media_localization", False)
        process_fields = component.get_config("process_fields", "raw_content")
        base_url_field = component.get_config("base_url_field", None)
        
        download_size_limit_str = component.get_config("download_size_limit", "50M")
        download_size_limit = _parse_size_limit(download_size_limit_str)

        queue_name = component.inputs.get("data_in", {}).get("value")
        dict_value = component.inputs.get("dict_in", {}).get("value")
        
        has_queue_input = bool(queue_name)
        has_dict_input = bool(dict_value)
        
        processed_count = 0
        failed_count = 0
        handled_dict = None
        dict_error = None
        
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
                
                heartbeat_callback = create_heartbeat_callback(component.rabbitmq)
                
                logger.info(f"开始处理队列: {queue_name}")
                
                while True:
                    message = component.rabbitmq.get_message(queue_name)
                    if not message:
                        break
                    
                    try:
                        data = json.loads(message['body'])
                        
                        try:
                            data = process_single_data(data, process_fields, enable_clean_content, enable_safe_raw_content,
                                                      enable_media_localization, base_url_field, download_size_limit,
                                                      heartbeat_callback=heartbeat_callback)
                        except (ValueError, TypeError) as e:
                            logger.warning(f"{e}，跳过处理")
                            component.rabbitmq.ack_message(message['delivery_tag'])
                            continue
                        
                        success_count = component.rabbitmq.send_messages_batch(output_queue_names, data)
                        
                        if success_count == len(output_queue_names):
                            component.rabbitmq.ack_message(message['delivery_tag'])
                            processed_count += 1
                            if processed_count % 10 == 0:
                                logger.info(f"已处理 {processed_count} 条消息")
                        else:
                            logger.error(f"发送消息失败，成功: {success_count}/{len(output_queue_names)}")
                            component.rabbitmq.nack_message(message['delivery_tag'], requeue=True)
                            failed_count += 1
                            
                    except json.JSONDecodeError as e:
                        logger.error(f"消息解析失败: {e}")
                        component.rabbitmq.nack_message(message['delivery_tag'], requeue=False)
                        failed_count += 1
                    except Exception as e:
                        logger.error(f"处理消息时发生错误: {e}")
                        component.rabbitmq.nack_message(message['delivery_tag'], requeue=True)
                        failed_count += 1
                
                logger.info(f"队列处理完成，成功: {processed_count}，失败: {failed_count}")
            
            if has_dict_input:
                logger.info("开始处理字典输入")
                try:
                    handled_dict = process_single_data(dict_value, process_fields, enable_clean_content, enable_safe_raw_content,
                                                       enable_media_localization, base_url_field, download_size_limit)
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


if __name__ == "__main__":
    main()
