import os
import json
import logging
from typing import Optional, List, Dict, Any, Callable
import pika
from pika.exceptions import AMQPConnectionError, AMQPChannelError

logger = logging.getLogger("CSI_SDK")


class RabbitMQClient:
    """SDK 内置 RabbitMQ 客户端，支持从环境变量自动读取配置"""
    
    def __init__(self, 
                 host: str = None, 
                 port: int = None, 
                 username: str = None,
                 password: str = None, 
                 vhost: str = None):
        self.host = host or os.getenv('RABBITMQ_HOST', 'localhost')
        self.port = port or int(os.getenv('RABBITMQ_PORT', '5672'))
        self.username = username or os.getenv('RABBITMQ_USERNAME', 'guest')
        self.password = password or os.getenv('RABBITMQ_PASSWORD', 'guest')
        self.vhost = vhost or os.getenv('RABBITMQ_VHOST', '/')
        
        self.connection: Optional[pika.BlockingConnection] = None
        self.channel: Optional[pika.channel.Channel] = None
    
    def connect(self) -> bool:
        """建立 RabbitMQ 连接和通道"""
        try:
            credentials = pika.PlainCredentials(self.username, self.password)
            parameters = pika.ConnectionParameters(
                host=self.host,
                port=self.port,
                virtual_host=self.vhost,
                credentials=credentials
            )
            
            self.connection = pika.BlockingConnection(parameters)
            self.channel = self.connection.channel()
            logger.info(f"RabbitMQ 连接成功: {self.host}:{self.port}")
            return True
        except AMQPConnectionError as e:
            logger.error(f"RabbitMQ 连接失败: {e}")
            return False
        except Exception as e:
            logger.error(f"RabbitMQ 连接异常: {e}")
            return False
    
    def _ensure_connection(self) -> bool:
        """确保连接可用，如果断开则重连"""
        if not self.connection or self.connection.is_closed:
            return self.connect()
        return True
    
    def close(self) -> None:
        """关闭 RabbitMQ 连接"""
        try:
            if self.channel and not self.channel.is_closed:
                self.channel.close()
            if self.connection and not self.connection.is_closed:
                self.connection.close()
            logger.info("RabbitMQ 连接已关闭")
        except Exception as e:
            logger.error(f"关闭连接时发生错误: {e}")
    
    def get_message(self, queue_name: str) -> Optional[Dict[str, Any]]:
        """从队列获取单条消息
        
        Args:
            queue_name: 队列名称
            
        Returns:
            消息字典，包含 body 和 delivery_tag，如果没有消息返回 None
        """
        if not self._ensure_connection():
            logger.error("无法连接到 RabbitMQ")
            return None
        
        if not self.channel:
            logger.error("RabbitMQ 通道未创建")
            return None
        
        try:
            self.channel.queue_declare(queue=queue_name, durable=True)
            method_frame, header_frame, body = self.channel.basic_get(queue=queue_name, auto_ack=False)
            
            if method_frame is None:
                return None
            
            return {
                'body': body.decode('utf-8'),
                'delivery_tag': method_frame.delivery_tag
            }
        except Exception as e:
            logger.error(f"获取消息失败: {e}")
            return None
    
    def ack_message(self, delivery_tag: int) -> bool:
        """确认消息
        
        Args:
            delivery_tag: 消息标签
            
        Returns:
            是否成功
        """
        try:
            if self.channel and not self.channel.is_closed:
                self.channel.basic_ack(delivery_tag=delivery_tag)
                return True
            return False
        except Exception as e:
            logger.error(f"确认消息失败: {e}")
            return False
    
    def nack_message(self, delivery_tag: int, requeue: bool = True) -> bool:
        """拒绝消息
        
        Args:
            delivery_tag: 消息标签
            requeue: 是否重新入队
            
        Returns:
            是否成功
        """
        try:
            if self.channel and not self.channel.is_closed:
                self.channel.basic_nack(delivery_tag=delivery_tag, requeue=requeue)
                return True
            return False
        except Exception as e:
            logger.error(f"拒绝消息失败: {e}")
            return False
    
    def send_message(self, queue_name: str, message: dict) -> bool:
        """发送消息到队列
        
        Args:
            queue_name: 队列名称
            message: 消息字典
            
        Returns:
            是否成功
        """
        if not self._ensure_connection():
            logger.error("无法连接到 RabbitMQ")
            return False
        
        if not self.channel:
            logger.error("RabbitMQ 通道未创建")
            return False
        
        try:
            self.channel.queue_declare(queue=queue_name, durable=True)
            self.channel.basic_publish(
                exchange='',
                routing_key=queue_name,
                body=json.dumps(message, ensure_ascii=False),
                properties=pika.BasicProperties(
                    delivery_mode=2,
                )
            )
            return True
        except Exception as e:
            logger.error(f"发送消息失败: {e}")
            return False
    
    def send_messages_batch(self, queue_names: List[str], message: dict) -> int:
        """批量发送消息到多个队列
        
        Args:
            queue_names: 队列名称列表
            message: 消息字典
            
        Returns:
            成功发送的队列数量
        """
        success_count = 0
        for queue_name in queue_names:
            if self.send_message(queue_name, message):
                success_count += 1
        return success_count
    
    def consume_all(self, queue_name: str, callback: Callable[[list], bool], batch_size: int = 100) -> int:
        """一次性消费队列中所有消息（批量处理）
        
        Args:
            queue_name: 队列名称
            callback: 消息处理回调函数，接收 list[(body, properties)] 参数，返回 bool 表示处理是否成功
            batch_size: 每次处理的批量大小
            
        Returns:
            处理的消息总数
        """
        if not self._ensure_connection():
            logger.error("无法连接到 RabbitMQ")
            return 0
        
        if not self.channel:
            logger.error("RabbitMQ 通道未创建")
            return 0
        
        processed_count = 0
        
        try:
            self.channel.queue_declare(queue=queue_name, durable=True)
            
            while True:
                batch_messages = []
                last_delivery_tag = None
                
                for _ in range(batch_size):
                    method_frame, header_frame, body = self.channel.basic_get(queue=queue_name, auto_ack=False)
                    
                    if method_frame is None:
                        break
                        
                    last_delivery_tag = method_frame.delivery_tag
                    
                    try:
                        body_str = body.decode('utf-8')
                        props_dict = {
                            'delivery_tag': method_frame.delivery_tag,
                            'exchange': method_frame.exchange,
                            'routing_key': method_frame.routing_key,
                            'redelivered': method_frame.redelivered
                        }
                        batch_messages.append((body_str, props_dict))
                    except Exception as e:
                        logger.error(f"解码消息失败: {e}")
                
                if not batch_messages:
                    break
                
                try:
                    success = callback(batch_messages)
                    
                    if success:
                        self.channel.basic_ack(delivery_tag=last_delivery_tag, multiple=True)
                        processed_count += len(batch_messages)
                    else:
                        self.channel.basic_nack(delivery_tag=last_delivery_tag, multiple=True, requeue=True)
                except Exception as e:
                    logger.error(f"批量处理消息时发生错误: {e}")
                    self.channel.basic_nack(delivery_tag=last_delivery_tag, multiple=True, requeue=True)
            
            return processed_count
            
        except AMQPChannelError as e:
            logger.error(f"消费消息失败: {e}")
            return processed_count
        except Exception as e:
            logger.error(f"消费消息异常: {e}")
            return processed_count
    
    def read_messages(self, queue_name: str, batch_size: int = 100) -> List[Dict[str, Any]]:
        """批量读取消息（不自动确认）
        
        Args:
            queue_name: 队列名称
            batch_size: 批量大小
            
        Returns:
            消息列表，每个消息包含 body 和 delivery_tag
        """
        if not self._ensure_connection():
            logger.error("无法连接到 RabbitMQ")
            return []
        
        if not self.channel:
            logger.error("RabbitMQ 通道未创建")
            return []
        
        messages = []
        message_count = 0
        
        try:
            self.channel.queue_declare(queue=queue_name, durable=True)
            method_frame, header_frame, body = self.channel.basic_get(queue=queue_name, auto_ack=False)
            
            while method_frame and message_count < batch_size:
                try:
                    message_body = json.loads(body.decode('utf-8'))
                    messages.append({
                        'body': message_body,
                        'delivery_tag': method_frame.delivery_tag
                    })
                    message_count += 1
                    
                    if message_count < batch_size:
                        method_frame, header_frame, body = self.channel.basic_get(queue=queue_name, auto_ack=False)
                    else:
                        break
                except json.JSONDecodeError as e:
                    logger.error(f"消息JSON解析失败: {e}, 跳过该消息")
                    self.channel.basic_ack(delivery_tag=method_frame.delivery_tag)
                    method_frame, header_frame, body = self.channel.basic_get(queue=queue_name, auto_ack=False)
                    continue
            
            return messages
        except Exception as e:
            logger.error(f"读取消息失败: {e}")
            return []
    
    def ack_all_message(self, delivery_tags: List[int]) -> bool:
        """批量确认消息
        
        Args:
            delivery_tags: 消息标签列表
            
        Returns:
            是否成功
        """
        if not self.channel or self.channel.is_closed:
            return False
        
        try:
            for tag in delivery_tags:
                self.channel.basic_ack(delivery_tag=tag, multiple=False)
            return True
        except Exception as e:
            logger.error(f"确认消息失败: {e}")
            return False
    
    def publish_messages(self, queue_name: str, messages: List[Dict[str, Any]]) -> bool:
        """批量发布消息到同一个队列
        
        Args:
            queue_name: 队列名称
            messages: 消息列表
            
        Returns:
            是否成功
        """
        if not self._ensure_connection():
            logger.error("无法连接到 RabbitMQ")
            return False
        
        if not self.channel:
            logger.error("RabbitMQ 通道未创建")
            return False
        
        try:
            self.channel.queue_declare(queue=queue_name, durable=True)
            for message in messages:
                message_body = json.dumps(message, ensure_ascii=False)
                self.channel.basic_publish(
                    exchange='',
                    routing_key=queue_name,
                    body=message_body,
                    properties=pika.BasicProperties(
                        delivery_mode=2,
                    )
                )
            return True
        except Exception as e:
            logger.error(f"批量发布消息失败: {e}")
            return False
    
    def process_data_events(self) -> None:
        """处理连接事件（心跳等），需要在长时间操作期间定期调用"""
        try:
            if self.connection and not self.connection.is_closed:
                self.connection.process_data_events()
        except Exception as e:
            logger.warning(f"处理连接事件时发生错误: {e}")
