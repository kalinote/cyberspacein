import json
import logging
import os
from typing import List, Dict, Any, Optional
import pika
from pika.exceptions import AMQPConnectionError, AMQPChannelError

logger = logging.getLogger(__name__)


class RabbitMQReader:
    def __init__(self, host: str, port: int, username: str, password: str, vhost: str = "/"):
        self.host = host
        self.port = port
        self.username = username
        self.password = password
        self.vhost = vhost
        self.connection: Optional[pika.BlockingConnection] = None
        self.channel: Optional[pika.channel.Channel] = None

    def connect(self):
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
            logger.info(f"RabbitMQ连接成功: {self.host}:{self.port}")
        except Exception as e:
            logger.error(f"RabbitMQ连接失败: {e}")
            raise

    def close(self):
        if self.channel and not self.channel.is_closed:
            self.channel.close()
        if self.connection and not self.connection.is_closed:
            self.connection.close()
        logger.info("RabbitMQ连接已关闭")

    def read_messages(self, queue_name: str, batch_size: int = 100) -> List[Dict[str, Any]]:
        if not self.channel or self.channel.is_closed:
            self.connect()

        messages = []
        message_count = 0

        try:
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
            raise

    def acknowledge_messages(self, delivery_tags: List[int]):
        if not self.channel or self.channel.is_closed:
            return
        
        try:
            for tag in delivery_tags:
                self.channel.basic_ack(delivery_tag=tag, multiple=False)
        except Exception as e:
            logger.error(f"确认消息失败: {e}")
            raise


class RabbitMQWriter:
    def __init__(self, host: str, port: int, username: str, password: str, vhost: str = "/"):
        self.host = host
        self.port = port
        self.username = username
        self.password = password
        self.vhost = vhost
        self.connection: Optional[pika.BlockingConnection] = None
        self.channel: Optional[pika.channel.Channel] = None

    def connect(self):
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
            logger.info(f"RabbitMQ连接成功: {self.host}:{self.port}")
        except Exception as e:
            logger.error(f"RabbitMQ连接失败: {e}")
            raise

    def close(self):
        if self.channel and not self.channel.is_closed:
            self.channel.close()
        if self.connection and not self.connection.is_closed:
            self.connection.close()
        logger.info("RabbitMQ连接已关闭")

    def publish_message(self, queue_name: str, message: Dict[str, Any]):
        if not self.channel or self.channel.is_closed:
            self.connect()

        try:
            self.channel.queue_declare(queue=queue_name, durable=True)
            message_body = json.dumps(message, ensure_ascii=False)
            self.channel.basic_publish(
                exchange='',
                routing_key=queue_name,
                body=message_body,
                properties=pika.BasicProperties(
                    delivery_mode=2,
                )
            )
        except Exception as e:
            logger.error(f"发布消息失败: {e}")
            raise

    def publish_messages(self, queue_name: str, messages: List[Dict[str, Any]]):
        if not self.channel or self.channel.is_closed:
            self.connect()

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
        except Exception as e:
            logger.error(f"批量发布消息失败: {e}")
            raise

