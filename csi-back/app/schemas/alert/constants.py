from enum import Enum


class AlertSeverityEnum(str, Enum):
    """告警等级。"""

    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


ALERT_SEVERITY_ORDER = {
    AlertSeverityEnum.INFO: 1,
    AlertSeverityEnum.WARNING: 2,
    AlertSeverityEnum.ERROR: 3,
    AlertSeverityEnum.CRITICAL: 4,
}


class AlertStatusEnum(str, Enum):
    """告警实例状态。"""

    FIRING = "firing"
    ACKNOWLEDGED = "acknowledged"
    RESOLVED = "resolved"


class AlertResolutionTypeEnum(str, Enum):
    """告警解决方式。"""

    AUTO = "auto"
    MANUAL = "manual"


class AlertEventTypeEnum(str, Enum):
    """永久告警事件类型。"""

    TRIGGERED = "triggered"
    ACKNOWLEDGED = "acknowledged"
    SEVERITY_CHANGED = "severity_changed"
    AUTO_RESOLVED = "auto_resolved"
    MANUAL_RESOLVED = "manual_resolved"
    RULE_ATTACHED = "rule_attached"
    RULE_DETACHED = "rule_detached"


class AlertEvaluationModeEnum(str, Enum):
    """告警检测方式。"""

    REALTIME = "realtime"
    INTERVAL = "interval"
    HYBRID = "hybrid"


class AlertInitialEvaluationPolicyEnum(str, Enum):
    """规则首次启用时的历史资源检测策略。"""

    FROM_ACTIVATION = "from_activation"
    INCLUDE_EXISTING = "include_existing"


class AlertValueTypeEnum(str, Enum):
    """告警字段值类型。"""

    ENUM = "enum"
    STRING = "string"
    NUMBER = "number"
    PERCENTAGE = "percentage"
    DURATION = "duration"
    DATETIME = "datetime"
    BOOLEAN = "boolean"


class AlertOperatorEnum(str, Enum):
    """条件比较运算符。"""

    EQ = "eq"
    NE = "ne"
    LT = "lt"
    LTE = "lte"
    GT = "gt"
    GTE = "gte"
    IN = "in"
    NOT_IN = "not_in"


class AlertRuleValidationStatusEnum(str, Enum):
    """告警规则校验状态。"""

    VALID = "valid"
    INVALID = "invalid"


class AlertRuleStateEnum(str, Enum):
    """单条规则对单个资源的检测状态。"""

    NORMAL = "normal"
    ACTIVE = "active"


class AlertInboxStatusEnum(str, Enum):
    """实时观测收件箱状态。"""

    PENDING = "pending"
    PROCESSING = "processing"
    PROCESSED = "processed"
    FAILED = "failed"


class AlertOutboxStatusEnum(str, Enum):
    """SSE Outbox 状态。"""

    PENDING = "pending"
    PUBLISHING = "publishing"
    PUBLISHED = "published"
    FAILED = "failed"
