from enum import Enum

class ActionNodeTypeEnum(str, Enum):
    """
    行动节点类型枚举
    """
    CONSTRUCTOR = "construct"
    CRAWLER = "crawler"
    STORAGE = "storage"
    MIDDLEWARE = "middleware"
    PROCESSOR = "processor"
    LOGIC = "logic"
    SIMPLE_OPERATION = "simple_operation"
    OUTPUT = "output"
    INPUT = "input"
    
class ActionFlowStatusEnum(str, Enum):
    """
    行动实例化流程状态枚举
    """
    UNREADY = "unready"
    READY = "ready"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    TIMEOUT = "timeout"
    PAUSED = "paused"
    
class ActionInstanceNodeStatusEnum(str, Enum):
    """
    行动实例节点状态枚举
    """
    UNREADY = "unready"
    READY = "ready"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    TIMEOUT = "timeout"
    PAUSED = "paused"