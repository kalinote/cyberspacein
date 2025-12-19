import argparse
import asyncio
import json
import sys
import logging
import os
from typing import Optional, Dict, Any
import aiohttp

logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] [%(levelname)s] [CSI_SDK] %(message)s',
    datefmt='%H:%M:%S'
)
logger = logging.getLogger("CSI_SDK")

class AsyncBaseComponent:
    def __init__(self, action_node_id: str = None, api_base_url: str = None, manual_config: str = None):
        """
        初始化 Node 对象，解析参数。
        注意：构造函数中不进行网络请求，网络请求在 __aenter__ 或 initialize 中进行。
        """
        self.args = self._parse_args()
        
        # 优先使用传入参数，其次使用命令行参数
        self.action_node_id = action_node_id or self.args.action_node_id
        self.api_base_url = (api_base_url or self.args.api_base_url)
        if self.api_base_url:
            self.api_base_url = self.api_base_url.rstrip('/')
            
        self.manual_config_path = manual_config or self.args.local_config
        
        # 数据容器
        self.inputs: Dict[str, Any] = {}
        self.config: Dict[str, Any] = {}
        self.session: Optional[aiohttp.ClientSession] = None
        
        # 运行模式标记
        self.is_remote = bool(self.action_node_id and self.api_base_url)

    def _parse_args(self):
        parser = argparse.ArgumentParser(description="CSI Base Components SDK (Async)")
        parser.add_argument('--action-node-id', type=str, help='行动节点ID', default=os.getenv('ACTION_NODE_ID'))
        parser.add_argument('--api-base-url', type=str, help='API基础URL', default=os.getenv('API_BASE_URL'))
        parser.add_argument('--local-config', type=str, help='本地调试配置文件路径', default=None)
        # 允许接收其他未知参数
        args, _ = parser.parse_known_args()
        return args

    async def __aenter__(self):
        """
        Async Context Manager 入口：建立 Session 并拉取配置
        """
        self.session = aiohttp.ClientSession()
        await self.initialize()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """
        Async Context Manager 出口：关闭 Session
        """
        if self.session:
            await self.session.close()
        
        if exc_type:
            logger.error(f"节点执行异常退出: {exc_val}")

    async def initialize(self):
        """
        核心初始化逻辑：拉取配置
        """
        if self.is_remote:
            logger.info(f"正在从远程拉取上下文: {self.action_node_id}")
            try:
                url = f"{self.api_base_url}/node/{self.action_node_id}/init"
                async with self.session.get(url, timeout=10) as resp:
                    resp.raise_for_status()
                    data = await resp.json()
                    self.inputs = data.get('inputs', {})
                    self.config = data.get('config', {})
                    logger.info("配置加载成功")
            except Exception as e:
                logger.error(f"远程配置拉取失败: {e}")
                sys.exit(1)
        
        elif self.manual_config_path:
            logger.info(f"正在加载本地配置: {self.manual_config_path}")
            try:
                with open(self.manual_config_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    self.inputs = data.get('inputs', {})
                    self.config = data.get('config', {})
            except Exception as e:
                logger.error(f"本地配置加载失败: {e}")
                sys.exit(1)
        else:
            logger.warning("未检测到行动节点ID或本地配置，以空模式启动")

    def get_input(self, key: str, default: Any = None) -> Any:
        """
        获取输入数据，自动处理 Value/Reference 结构
        """
        val = self.inputs.get(key)
        if val is None:
            return default
        
        if isinstance(val, dict) and 'type' in val:
            # 如果是引用类型，返回 URI；如果是值，返回 content
            return val.get('uri') if val['type'] == 'reference' else val.get('content')
        return val

    async def report_progress(self, percentage: int, message: str = ""):
        """
        上报进度（非阻塞）
        """
        if not self.is_remote:
            logger.info(f"[本地模拟进度] {percentage}% - {message}")
            return

        try:
            url = f"{self.api_base_url}/node/{self.action_node_id}/heartbeat"
            payload = {"progress": percentage, "message": message}
            async with self.session.post(url, json=payload, timeout=5) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    if data.get('action') == 'stop':
                        logger.warning("收到后端停止指令，正在退出...")
                        sys.exit(0)
        except Exception as e:
            logger.warning(f"心跳上报失败 (不影响主流程): {e}")

    async def finish(self, outputs: Dict[str, Any]):
        """
        提交最终结果
        """
        if self.is_remote:
            try:
                url = f"{self.api_base_url}/node/{self.action_node_id}/result"
                payload = {"status": "success", "outputs": outputs}
                async with self.session.post(url, json=payload) as resp:
                    resp.raise_for_status()
                    logger.info("结果提交成功")
            except Exception as e:
                logger.error(f"结果提交失败: {e}")
                raise e
        else:
            logger.info("\n[SDK Local Output] =============")
            logger.info(json.dumps(outputs, indent=2, ensure_ascii=False))
            logger.info("==================================")

    async def fail(self, error_msg: str):
        """
        主动上报任务失败
        """
        if self.is_remote:
            try:
                url = f"{self.api_base_url}/node/{self.action_node_id}/result"
                payload = {"status": "failed", "error": error_msg}
                async with self.session.post(url, json=payload) as resp:
                    logger.error(f"已上报失败状态: {error_msg}")
            except Exception as e:
                logger.error(f"上报失败状态时发生网络错误: {e}")
        else:
            logger.error(f"[本地模拟失败] {error_msg}")
        sys.exit(1)

