import os
from typing import Callable, Optional
from dotenv import load_dotenv
import pika
from pika.exceptions import AMQPConnectionError, AMQPChannelError

load_dotenv()


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
            print(f"RabbitMQ 连接成功: {self.host}:{self.port}")
            return True
        except AMQPConnectionError as e:
            print(f"RabbitMQ 连接失败: {e}")
            return False
        except Exception as e:
            print(f"RabbitMQ 连接异常: {e}")
            return False
    
    def test_connection(self) -> bool:
        """测试 RabbitMQ 连接"""
        try:
            if not self.connection or self.connection.is_closed:
                return self.connect()
            return True
        except Exception as e:
            print(f"连接测试失败: {e}")
            return False
    
    def consume_all(self, queue_name: str, callback: Callable[[str, dict], bool]) -> int:
        """一次性消费队列中所有消息
        
        Args:
            queue_name: 队列名称
            callback: 消息处理回调函数，接收 (body: str, properties: dict) 参数，返回 bool 表示处理是否成功
            
        Returns:
            处理的消息总数
        """
        if not self.connection or self.connection.is_closed:
            if not self.connect():
                print("无法连接到 RabbitMQ")
                return 0
        
        if not self.channel:
            print("RabbitMQ 通道未创建")
            return 0
        
        processed_count = 0
        
        try:
            self.channel.queue_declare(queue=queue_name, durable=True)
            
            while True:
                method_frame, header_frame, body = self.channel.basic_get(queue=queue_name, auto_ack=False)
                
                if method_frame is None:
                    break
                
                try:
                    body_str = body.decode('utf-8')
                    props_dict = {
                        'delivery_tag': method_frame.delivery_tag,
                        'exchange': method_frame.exchange,
                        'routing_key': method_frame.routing_key,
                        'redelivered': method_frame.redelivered
                    }
                    
                    success = callback(body_str, props_dict)
                    
                    if success:
                        self.channel.basic_ack(delivery_tag=method_frame.delivery_tag)
                        processed_count += 1
                    else:
                        self.channel.basic_nack(delivery_tag=method_frame.delivery_tag, requeue=True)
                except Exception as e:
                    print(f"处理消息时发生错误: {e}")
                    self.channel.basic_nack(delivery_tag=method_frame.delivery_tag, requeue=True)
            
            return processed_count
            
        except AMQPChannelError as e:
            print(f"消费消息失败: {e}")
            return processed_count
        except Exception as e:
            print(f"消费消息异常: {e}")
            return processed_count
    
    def close(self) -> None:
        """关闭 RabbitMQ 连接"""
        try:
            if self.channel and not self.channel.is_closed:
                self.channel.close()
            if self.connection and not self.connection.is_closed:
                self.connection.close()
            print("RabbitMQ 连接已关闭")
        except Exception as e:
            print(f"关闭连接时发生错误: {e}")
