import logging
import sys
from typing import Callable, List, Optional, Dict, Any


THIRD_PARTY_LOGGERS = frozenset([
    'pika',
    'requests',
    'urllib3',
    'httpx',
    'httpcore',
    'scrapy',
    'twisted',
    'filelock',
    'asyncio',
    'concurrent',
    'charset_normalizer',
    'PIL',
    'parso',
])

APP_LOGGER_PREFIXES = (
    'CSI_SDK',
    'csi_',
    'content_embedding',
    'html_analyze',
    'data_storage',
    'data_verify',
    'str_list',
    'conditions',
    'LAUNCHER'
)


class AppLogFilter(logging.Filter):
    """应用日志过滤器，只保留应用日志，过滤第三方库日志"""
    
    def filter(self, record: logging.LogRecord) -> bool:
        logger_name = record.name
        
        if logger_name == 'root' or not logger_name:
            return True
        
        for prefix in APP_LOGGER_PREFIXES:
            if logger_name.startswith(prefix):
                return True
        
        top_level = logger_name.split('.')[0]
        if top_level in THIRD_PARTY_LOGGERS:
            return False
        
        return True


class SDKLogHandler(logging.StreamHandler):
    """SDK 自定义日志 Handler，支持回调函数"""
    
    def __init__(self, stream=None, callbacks: Optional[List[Callable]] = None):
        super().__init__(stream)
        self._callbacks: List[Callable[[Dict[str, Any]], None]] = callbacks or []
    
    def emit(self, record: logging.LogRecord) -> None:
        super().emit(record)
        
        if self._callbacks:
            log_entry = {
                'timestamp': self.formatter.formatTime(record) if self.formatter else str(record.created),
                'level': record.levelname,
                'name': record.name,
                'message': record.getMessage(),
                'pathname': record.pathname,
                'lineno': record.lineno,
            }
            for callback in self._callbacks:
                try:
                    callback(log_entry)
                except Exception:
                    pass
    
    def add_callback(self, callback: Callable[[Dict[str, Any]], None]) -> None:
        """添加日志回调函数"""
        if callback not in self._callbacks:
            self._callbacks.append(callback)
    
    def remove_callback(self, callback: Callable[[Dict[str, Any]], None]) -> None:
        """移除日志回调函数"""
        if callback in self._callbacks:
            self._callbacks.remove(callback)


class SDKLogManager:
    """SDK 日志管理器（单例模式）"""
    
    _instance: Optional['SDKLogManager'] = None
    _initialized: bool = False
    
    def __new__(cls) -> 'SDKLogManager':
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self):
        if SDKLogManager._initialized:
            return
        
        self._handler: Optional[SDKLogHandler] = None
        self._filter: Optional[AppLogFilter] = None
        self._log_format = '[%(asctime)s] [%(levelname)s] [%(name)s] %(message)s'
        self._date_format = '%H:%M:%S'
        SDKLogManager._initialized = True
    
    def setup(self) -> None:
        """配置日志系统"""
        root_logger = logging.getLogger()
        
        root_logger.handlers.clear()
        
        self._handler = SDKLogHandler(sys.stderr)
        formatter = logging.Formatter(self._log_format, self._date_format)
        self._handler.setFormatter(formatter)
        
        self._filter = AppLogFilter()
        self._handler.addFilter(self._filter)
        
        root_logger.addHandler(self._handler)
        root_logger.setLevel(logging.INFO)
        
        self._suppress_third_party_loggers()
    
    def _suppress_third_party_loggers(self) -> None:
        """抑制第三方库的日志输出"""
        for name in THIRD_PARTY_LOGGERS:
            third_party_logger = logging.getLogger(name)
            third_party_logger.setLevel(logging.WARNING)
    
    def register_callback(self, callback: Callable[[Dict[str, Any]], None]) -> None:
        """注册日志回调函数（用于 WebSocket 等外部推送）"""
        if self._handler:
            self._handler.add_callback(callback)
    
    def unregister_callback(self, callback: Callable[[Dict[str, Any]], None]) -> None:
        """取消注册日志回调函数"""
        if self._handler:
            self._handler.remove_callback(callback)
    
    def set_level(self, level: int) -> None:
        """设置日志级别"""
        root_logger = logging.getLogger()
        root_logger.setLevel(level)
    
    @property
    def handler(self) -> Optional[SDKLogHandler]:
        """获取当前的日志 Handler"""
        return self._handler


_log_manager: Optional[SDKLogManager] = None


def setup_logging() -> SDKLogManager:
    """初始化 SDK 日志系统"""
    global _log_manager
    if _log_manager is None:
        _log_manager = SDKLogManager()
        _log_manager.setup()
    return _log_manager


def get_log_manager() -> Optional[SDKLogManager]:
    """获取日志管理器实例"""
    return _log_manager


class WebSocketLogClient:
    """WebSocket 日志提交客户端（静默容错）"""
    
    def __init__(self, ws_url: str):
        self._ws_url = ws_url
        self._ws = None
        self._connected = False
        self._callback = None
        self._logger = logging.getLogger("CSI_SDK")
    
    def connect(self) -> bool:
        """连接 WebSocket 服务器，失败时仅输出警告"""
        try:
            import websocket
            # TODO: 实现 WebSocket 连接逻辑，等待后端接口实现后完善
            self._ws = websocket.create_connection(self._ws_url, timeout=5)
            self._connected = True
            
            self._callback = self._on_log
            manager = get_log_manager()
            if manager:
                manager.register_callback(self._callback)
            
            return True
        except Exception as e:
            self._logger.warning(f"WebSocket 日志服务连接失败，日志将不会上报: {e}")
            self._connected = False
            return False
    
    def _build_log_packet(self, log_entry: Dict[str, Any]) -> str:
        """构建日志数据包"""
        # TODO: 根据后端接口设计日志包格式
        import json
        packet = {
            "timestamp": log_entry.get("timestamp"),
            "level": log_entry.get("level"),
            "logger": log_entry.get("name"),
            "message": log_entry.get("message"),
        }
        return json.dumps(packet, ensure_ascii=False)
    
    def _on_log(self, log_entry: Dict[str, Any]) -> None:
        """日志回调，发送到 WebSocket，失败时静默处理"""
        if not self._connected or not self._ws:
            return
        try:
            packet = self._build_log_packet(log_entry)
            # TODO: 等待后端接口实现后完善发送逻辑
            self._ws.send(packet)
        except Exception:
            pass
    
    def close(self) -> None:
        """关闭连接并取消回调注册"""
        if self._callback:
            manager = get_log_manager()
            if manager:
                manager.unregister_callback(self._callback)
            self._callback = None
        
        if self._ws:
            try:
                self._ws.close()
            except Exception:
                pass
            self._ws = None
        
        self._connected = False
