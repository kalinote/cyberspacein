import logging
import json
import os
from concurrent.futures import ThreadPoolExecutor, wait, FIRST_COMPLETED
from dotenv import load_dotenv

load_dotenv()

from csi_base_component_sdk import BaseComponent
from embedding import get_embedding

logger = logging.getLogger("content_embedding")

_DEFAULT_CONCURRENCY = 10


def _parse_concurrency() -> int:
    raw = os.getenv("EMBEDDING_CONCURRENCY", str(_DEFAULT_CONCURRENCY))
    try:
        n = int(raw)
        if n < 1:
            raise ValueError("必须为正整数")
        return n
    except (ValueError, TypeError):
        logger.warning("EMBEDDING_CONCURRENCY 非法，使用默认值 10")
        return _DEFAULT_CONCURRENCY


def process_single_data(data: dict, content_field: str, vector_field: str) -> dict:
    """处理单条数据，计算内容字段的嵌入
    
    Args:
        data: 输入数据字典
        content_field: 内容字段
        vector_field: 嵌入字段
        
    Returns:
        处理后的数据字典
        
    Raises:
        ValueError: 数据格式错误
        TypeError: 数据类型错误
    """
    processed_data = data.copy()
    if not processed_data.get(content_field):
        processed_data["vector_status"] = True
        return processed_data
    
    try:
        content = processed_data[content_field]
        if not isinstance(content, str):
            raise TypeError(f"内容字段 {content_field} 必须是字符串类型")
        
        embedding_vector = get_embedding(content)
        processed_data[vector_field] = embedding_vector
        processed_data["vector_status"] = True
    except Exception as e:
        logger.error(f"生成嵌入向量失败: {e}")
        processed_data["vector_status"] = False
        raise
    
    return processed_data


def process_data_only(message_body: str, content_field: str, vector_field: str) -> dict:
    """仅处理业务逻辑，不操作 RabbitMQ
    
    Args:
        message_body: 消息体（JSON 字符串）
        content_field: 内容字段
        vector_field: 嵌入字段
        
    Returns:
        处理结果字典：
        {
            "success": bool,
            "data": dict | None,
            "error": str | None,
            "should_requeue": bool
        }
    """
    try:
        data = json.loads(message_body)
    except json.JSONDecodeError as e:
        logger.error(f"消息解析失败: {e}")
        return {
            "success": False,
            "data": None,
            "error": str(e),
            "should_requeue": False
        }
    
    try:
        processed_data = process_single_data(data, content_field, vector_field)
        return {
            "success": True,
            "data": processed_data,
            "error": None,
            "should_requeue": False
        }
    except (ValueError, TypeError) as e:
        logger.warning(f"{e}，跳过处理")
        return {
            "success": False,
            "data": None,
            "error": str(e),
            "should_requeue": False
        }
    except Exception as e:
        logger.error(f"处理消息时发生错误: {e}")
        return {
            "success": False,
            "data": None,
            "error": str(e),
            "should_requeue": True
        }


def main():
    with BaseComponent(enable_rabbitmq=True) as component:
        queue_name = component.inputs.get("data_in", {}).get("value")
        dict_value = component.inputs.get("dict_in", {}).get("value")
        
        content_field = component.config.get("content_field")
        vector_field = component.config.get("vector_field")
        if not content_field or not vector_field:
            component.fail("内容字段或嵌入字段未配置")
        
        ml_base_url = os.getenv('ML_SERVICE_BASE_URL')
        if not ml_base_url:
            component.fail("未配置 ML_SERVICE_BASE_URL 环境变量")
        
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
                concurrency = _parse_concurrency()
                logger.info(f"开始处理队列: {queue_name}，并发数: {concurrency}")
                
                pending = {}
                total_processed = 0
                with ThreadPoolExecutor(max_workers=concurrency) as executor:
                    queue_exhausted = False
                    
                    while pending or not queue_exhausted:
                        while len(pending) < concurrency and not queue_exhausted:
                            message = component.rabbitmq.get_message(queue_name)
                            if not message:
                                queue_exhausted = True
                                break
                            future = executor.submit(
                                process_data_only,
                                message["body"],
                                content_field,
                                vector_field
                            )
                            pending[future] = message
                        
                        if pending:
                            done, _ = wait(
                                pending.keys(),
                                timeout=0.1,
                                return_when=FIRST_COMPLETED
                            )
                            for future in done:
                                message = pending.pop(future)
                                result = future.result()
                                
                                if result["success"]:
                                    success_count = component.rabbitmq.send_messages_batch(
                                        output_queue_names, result["data"]
                                    )
                                    if success_count == len(output_queue_names):
                                        component.rabbitmq.ack_message(message["delivery_tag"])
                                        processed_count += 1
                                    else:
                                        logger.error(f"发送消息失败，成功: {success_count}/{len(output_queue_names)}")
                                        component.rabbitmq.nack_message(
                                            message["delivery_tag"], requeue=True
                                        )
                                        failed_count += 1
                                elif result["should_requeue"]:
                                    component.rabbitmq.nack_message(
                                        message["delivery_tag"], requeue=True
                                    )
                                    failed_count += 1
                                else:
                                    component.rabbitmq.nack_message(
                                        message["delivery_tag"], requeue=False
                                    )
                                    failed_count += 1
                                
                                total_processed += 1
                                if total_processed % 10 == 0:
                                    logger.info(
                                        f"处理进度: 已完成 {total_processed} 条 "
                                        f"(成功: {processed_count}, 失败: {failed_count}, "
                                        f"进行中: {len(pending)})"
                                    )
                
                logger.info(f"队列处理完成，成功: {processed_count}，失败: {failed_count}")
            
            if has_dict_input:
                logger.info("开始处理字典输入")
                try:
                    handled_dict = process_single_data(dict_value, content_field, vector_field)
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
