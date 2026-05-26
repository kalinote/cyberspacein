from __future__ import annotations

from enum import Enum

_ACTION_NODE_TYPE_LABELS = {
    "construct": "构造器",
    "crawler": "采集节点",
    "storage": "存储节点",
    "middleware": "中间件节点",
    "processor": "处理器节点",
    "logic": "基本逻辑节点",
    "simple_operation": "简单运算节点",
    "output": "输出节点",
    "input": "输入节点",
}


class ActionNodeTypeEnum(str, Enum):
    CONSTRUCTOR = "construct"
    CRAWLER = "crawler"
    STORAGE = "storage"
    MIDDLEWARE = "middleware"
    PROCESSOR = "processor"
    LOGIC = "logic"
    SIMPLE_OPERATION = "simple_operation"
    OUTPUT = "output"
    INPUT = "input"

    @property
    def label(self) -> str:
        return _ACTION_NODE_TYPE_LABELS.get(self.value, self.value)


class ActionFlowStatusEnum(str, Enum):
    """
    行动实例化流程状态枚举
    """
    UNKNOWN = "unknown"
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
    
    - unknown: 未知状态
    - pending: 等待中状态
    - unready: 未就绪状态
    - ready: 就绪状态
    - running: 运行中状态
    - completed: 完成状态
    - failed: 失败状态
    - cancelled: 取消状态
    - timeout: 超时状态
    - paused: 暂停状态
    """
    UNKNOWN = "unknown"
    PENDING = "pending"
    UNREADY = "unready"
    READY = "ready"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    TIMEOUT = "timeout"
    PAUSED = "paused"

ActionNodeFinishStatusList = [
    ActionInstanceNodeStatusEnum.COMPLETED,
    ActionInstanceNodeStatusEnum.FAILED,
    ActionInstanceNodeStatusEnum.CANCELLED,
    ActionInstanceNodeStatusEnum.TIMEOUT
]
    
class ActionConfigIOTypeEnum(str, Enum):
    """
    节点配置输入输出数据类型枚举
    """
    VALUE = "value"
    REFERENCE = "reference"
    
# es所有实体索引
ALL_INDEX = [
    "article",
    "forum"
]
    
class ActionNodeInputTypeEnum(str, Enum):
    """
    行动节点输入项类型枚举
    """
    INT = "int"
    STRING = "string"
    TEXTAREA = "textarea"
    SELECT = "select"
    CHECKBOX = "checkbox"
    CHECKBOX_GROUP = "checkbox-group"
    RADIO_GROUP = "radio-group"
    BOOLEAN = "boolean"
    DATETIME = "datetime"
    TAGS = "tags"
    CONDITIONS = "conditions"
    COMMENT = "comment"
    
class EntityType(str, Enum):
    ARTICLE = "article"
    FORUM = "forum"


class SearchModeEnum(str, Enum):
    KEYWORD = "keyword"
    VECTOR = "vector"
    HYBRID = "hybrid"


ENTITY_TYPE_NAMES = {
    EntityType.ARTICLE: "文章",
    EntityType.FORUM: "论坛"
}

ENTITY_TYPE_INDEX_MAP = {
    EntityType.ARTICLE: "article",
    EntityType.FORUM: "forum",
    
    # 值转换
    EntityType.ARTICLE.value: "article",
    EntityType.FORUM.value: "forum",
}

class AgentSSEStatusEnum(str, Enum):
    """
    Agent SSE状态枚举
    """
    APPROVAL_REQUIRED = "approval_required"
    STATUS = "status"


class AnnotationTypeEnum(str, Enum):
    """
    批注类型枚举
    """
    TEXT = "text"
    ENTITY_REF = "entity_ref"


class AnnotationStyleEnum(str, Enum):
    """
    批注样式枚举
    """
    UNDERLINE = "underline"
    HIGHLIGHT = "highlight"
    BOX = "box"
    BRACKET = "bracket"
    CIRCLE = "circle"
    STRIKE_THROUGH = "strike-through"


class ContentRegionEnum(str, Enum):
    """
    内容区域枚举
    """
    CLEAN = "clean"
    RENDERED = "rendered"
    TRANSLATE = "translate"


class AccountStatusEnum(str, Enum):
    """
    账号状态枚举
    """
    ACTIVE = "ACTIVE"
    RISK = "RISK"
    CAPTCHA = "CAPTCHA"
    INVALID_PWD = "INVALID_PWD"
    EXPIRED = "EXPIRED"
    BANNED = "BANNED"


class AccountAuthTypeEnum(str, Enum):
    """
    账号认证类型枚举
    """
    COOKIE = "cookie"
    HEADER = "header"
    API_KEY = "api_key"
    OAUTH = "oauth"


class RateLimitStrategyEnum(str, Enum):
    """
    频率限制策略枚举
    """
    MINUTELY = "minutely"
    HOURLY = "hourly"
    DAILY = "daily"
    NONE = "none"

class SandboxTypeEnum(str, Enum):
    """
    沙盒类型枚举
    """
    ALL_IN_ONE = "all-in-one"
    WINDOWS = "windows"


class SandboxStatusEnum(str, Enum):
    """
    沙盒业务状态枚举
    """
    CREATED = "created"
    DEPLOYED = "deployed"
    STOPPED = "stopped"
    DESTROYED = "destroyed"


# nanobot
class NanobotMessageRoleEnum(str, Enum):
    """
    nanobot消息角色枚举
    """
    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"
    TOOL = "tool"
    
NANOBOT_BUILTIN_WORKSPACE_ID = "__nanobot__"


class NanobotMemoryDocTypeEnum(str, Enum):
    """
    nanobot记忆类型枚举
    """
    MEMORY = "memory"
    SOUL = "soul"
    USER = "user"
    AGENT = "agent"


class NanobotAgentStatusEnum(str, Enum):
    """
    Agent运行时业务状态枚举
    """
    IDLE = "idle"
    RUNNING = "running"
    AWAITING_APPROVAL = "awaiting_approval"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"


class NanobotSessionStatusEnum(str, Enum):
    """单次分析会话（nanobot_sessions）的运行时状态。"""

    IDLE = "idle"
    RUNNING = "running"
    AWAITING_APPROVAL = "awaiting_approval"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class AgentStopReasonEnum(str, Enum):
    """Agent 推理循环结束原因（AgentRunner → SSE/DB `result.stop_reason`）。"""

    COMPLETED = "completed"
    TOOL_ERROR = "tool_error"
    ERROR = "error"
    EMPTY_FINAL_RESPONSE = "empty_final_response"
    MAX_ITERATIONS = "max_iterations"
    AWAITING_APPROVAL = "awaiting_approval"

    @classmethod
    def coerce(cls, value: str | AgentStopReasonEnum | None) -> AgentStopReasonEnum | None:
        if value is None:
            return None
        if isinstance(value, cls):
            return value
        try:
            return cls(str(value))
        except ValueError:
            return None

class NanobotLLMProviderEnum(str, Enum):
    """
    LLM提供商枚举
    """
    OPENAI_COMPAT = "openai"
    ANTHROPIC_COMPAT = "anthropic"


class ReasoningEffortEnum(str, Enum):
    """
    推理强度枚举（用于启用/调节模型思考模式）。

    - None（null）表示关闭推理/思考模式。
    """

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    XHIGH = "xhigh"
    MAX = "max"
    