import argparse
from datetime import datetime
import json
import sys
import logging
import os
from typing import Optional, Dict, Any, TYPE_CHECKING
from crawlab import save_item
import requests

if TYPE_CHECKING:
    from .rabbitmq import RabbitMQClient

logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] [%(levelname)s] [%(name)s] %(message)s',
    datefmt='%H:%M:%S'
)
logger = logging.getLogger("CSI_SDK")

class BaseComponent:
    def __init__(self, action_node_id: str = None, api_base_url: str = None, 
                 manual_config: str = None, enable_rabbitmq: bool = False):
        """
        初始化 Node 对象，解析参数。
        注意：构造函数中不进行网络请求，网络请求在 __enter__ 或 initialize 中进行。
        
        Args:
            action_node_id: 行动节点ID
            api_base_url: API基础URL
            manual_config: 本地调试配置文件路径
            enable_rabbitmq: 是否启用 RabbitMQ 自动管理
        """
        self.args = self._parse_args()
        
        self.action_node_id = action_node_id or self.args.action_node_id
        self.api_base_url = (api_base_url or self.args.api_base_url)
        if self.api_base_url:
            self.api_base_url = self.api_base_url.rstrip('/')
            
        self.manual_config_path = manual_config or self.args.local_config
        
        self.config: Dict[str, Any] = {}
        self.inputs: Dict[str, Any] = {}
        self.outputs: Dict[str, Any] = {}
        self.session: Optional[requests.Session] = None
        
        self.is_remote = bool(self.action_node_id and self.api_base_url)
        
        self.created_at = datetime.now()
        
        self._enable_rabbitmq = enable_rabbitmq
        self.rabbitmq: Optional["RabbitMQClient"] = None

    def _parse_args(self):
        parser = argparse.ArgumentParser(description="CSI Base Components SDK (Sync)")
        parser.add_argument('--action-node-id', type=str, help='行动节点ID', default=os.getenv('ACTION_NODE_ID'))
        parser.add_argument('--api-base-url', type=str, help='API基础URL', default=os.getenv('API_BASE_URL'))
        parser.add_argument('--local-config', type=str, help='本地调试配置文件路径', default=None)
        args, _ = parser.parse_known_args()
        return args

    def __enter__(self):
        """
        Context Manager 入口：调用 initialize 完成所有初始化
        """
        self.initialize()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """
        Context Manager 出口：调用 close 关闭所有连接
        """
        self.close()
        
        if exc_type:
            logger.error(f"节点执行异常退出: {exc_val}")

    def initialize(self):
        """
        核心初始化逻辑：建立 Session、拉取配置、初始化 RabbitMQ（如启用）
        """
        if self.session is None:
            self.session = requests.Session()
        
        if self.is_remote:
            logger.info(f"正在从远程拉取上下文: {self.action_node_id}")
            try:
                url = f"{self.api_base_url}/action/sdk/{self.action_node_id}/init"
                resp = self.session.get(url, timeout=10)
                resp.raise_for_status()
                data = resp.json()
                if data.get('code') != 0:
                    logger.error(f"远程配置拉取失败: {data.get('message')}")
                    sys.exit(1)
                data = data.get('data')
                self.config = data.get('config', {})
                self.inputs = data.get('inputs', {})
                self.outputs = data.get('outputs', {})
                logger.info("配置加载成功")
            except Exception as e:
                logger.error(f"远程配置拉取失败: {e}")
                sys.exit(1)
        
        elif self.manual_config_path:
            logger.info(f"正在加载本地配置: {self.manual_config_path}")
            try:
                with open(self.manual_config_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    self.config = data.get('config', {})
                    self.inputs = data.get('inputs', {})
                    self.outputs = data.get('outputs', {})
            except Exception as e:
                logger.error(f"本地配置加载失败: {e}")
                sys.exit(1)
        else:
            logger.warning("未检测到行动节点ID或本地配置，以空模式启动")
        
        if self._enable_rabbitmq and self.rabbitmq is None:
            from .rabbitmq import RabbitMQClient
            self.rabbitmq = RabbitMQClient()
            if not self.rabbitmq.connect():
                raise RuntimeError(
                    f"无法连接到 RabbitMQ: {self.rabbitmq.host}:{self.rabbitmq.port} "
                    f"(vhost={self.rabbitmq.vhost}, user={self.rabbitmq.username})"
                )

    def close(self):
        """
        关闭 RabbitMQ 和 Session
        """
        if self.rabbitmq:
            self.rabbitmq.close()
        if self.session:
            self.session.close()

    def get_config(self, key: str, default: Any = None) -> Any:
        """
        获取输入数据，自动处理 Value/Reference 结构
        """
        val = self.config.get(key)
        if val is None:
            return default
        
        if isinstance(val, dict) and 'type' in val:
            return val.get('uri') if val['type'] == 'reference' else val.get('content')
        return val

    def report_progress(self, percentage: int, message: str = ""):
        """
        上报进度（非阻塞）
        """
        if not self.is_remote:
            logger.info(f"[独立模式] {percentage}% - {message}")
            return

        try:
            url = f"{self.api_base_url}/action/sdk/{self.action_node_id}/heartbeat"
            payload = {"progress": percentage, "message": message}
            resp = self.session.post(url, json=payload, timeout=5)
            if resp.status_code == 200:
                data = resp.json()
                if data.get('action') == 'stop':
                    logger.warning("收到后端停止指令，正在退出...")
                    sys.exit(0)
        except Exception as e:
            logger.warning(f"心跳上报失败 (不影响主流程): {e}")

    def finish(self, outputs: Dict[str, Any]):
        """
        提交最终结果
        """
        save_item({
            'action_node_id': self.action_node_id,
            'status': 'success',
            'message': '运行成功',
            'outputs': json.dumps(outputs, ensure_ascii=False),
            'created_at': self.created_at.strftime('%Y-%m-%d %H:%M:%S'),
            'finished_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        })
        if self.is_remote:
            try:
                url = f"{self.api_base_url}/action/sdk/{self.action_node_id}/result"
                payload = {"status": "success", "outputs": outputs}
                resp = self.session.post(url, json=payload)
                resp.raise_for_status()
                logger.info("结果提交成功")
            except Exception as e:
                logger.error(f"结果提交失败: {e}")
                raise e
        else:
            logger.info("\n[SDK Local Output] =============")
            logger.info(json.dumps(outputs, indent=2, ensure_ascii=False))
            logger.info("==================================")

    def fail(self, error_msg: str):
        """
        主动上报任务失败
        """
        save_item({
            'action_node_id': self.action_node_id,
            'status': 'failed',
            'message': error_msg,
            'created_at': self.created_at.strftime('%Y-%m-%d %H:%M:%S'),
            'finished_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        })
        if self.is_remote:
            try:
                url = f"{self.api_base_url}/action/sdk/{self.action_node_id}/result"
                payload = {"status": "failed", "error": error_msg}
                resp = self.session.post(url, json=payload)
                logger.error(f"已上报失败状态: {error_msg}")
            except Exception as e:
                logger.error(f"上报失败状态时发生网络错误: {e}")
        else:
            logger.error(f"[本地模拟失败] {error_msg}")
        sys.exit(1)
