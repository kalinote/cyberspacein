import os
import logging
import json
from typing import Optional, List
from dotenv import load_dotenv
import pika
from pika.exceptions import AMQPConnectionError

load_dotenv()

logger = logging.getLogger(__name__)


class RabbitMQClient:
    """RabbitMQ 客户端封装类"""
    
    def __init__(self):
        """初始化 RabbitMQ 客户端"""
        self.host = os.getenv('RABBITMQ_HOST', 'localhost')
        self.port = int(os.getenv('RABBITMQ_PORT', '5672'))
        self.username = os.getenv('RABBITMQ_USERNAME', 'guest')
        self.password = os.getenv('RABBITMQ_PASSWORD', 'guest')
        self.vhost = os.getenv('RABBITMQ_VHOST', '/')
        
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
    
    def get_message(self, queue_name: str) -> Optional[dict]:
        """从队列获取单条消息
        
        Args:
            queue_name: 队列名称
            
        Returns:
            消息字典，包含 body 和 delivery_tag，如果没有消息返回 None
        """
        if not self.connection or self.connection.is_closed:
            if not self.connect():
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
        if not self.connection or self.connection.is_closed:
            if not self.connect():
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
    
    def process_data_events(self) -> None:
        """处理连接事件（心跳等），需要在长时间操作期间定期调用"""
        try:
            if self.connection and not self.connection.is_closed:
                self.connection.process_data_events()
        except Exception as e:
            logger.warning(f"处理连接事件时发生错误: {e}")
    
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
