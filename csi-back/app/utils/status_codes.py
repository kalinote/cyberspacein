from enum import IntEnum


class StatusCodeSource(IntEnum):
    INTERNAL = 1
    HTTP_STANDARD = 2


class StatusCodeCategory(IntEnum):
    BAD_REQUEST = 400
    UNAUTHORIZED = 401
    FORBIDDEN = 403
    NOT_FOUND = 404
    CONFLICT = 409
    UNPROCESSABLE_ENTITY = 422
    INTERNAL_SERVER_ERROR = 500
    BAD_GATEWAY = 502
    SERVICE_UNAVAILABLE = 503


def build_status_code(
    source: StatusCodeSource | int,
    category: StatusCodeCategory | int,
    sub_category: int = 0,
) -> int:
    src = int(source)
    cat = int(category)
    sub = int(sub_category)
    if src not in (1, 2):
        raise ValueError("source 只能是 1 或 2")
    if not 0 <= cat <= 999:
        raise ValueError("category 必须在 0~999")
    if not 0 <= sub <= 99:
        raise ValueError("sub_category 必须在 0~99")
    return int(f"{src}{cat:03d}{sub:02d}")


# 通用
SUCCESS = 0
INTERNAL_ERROR = build_status_code(StatusCodeSource.HTTP_STANDARD, StatusCodeCategory.INTERNAL_SERVER_ERROR)
VALIDATION_ERROR = build_status_code(StatusCodeSource.HTTP_STANDARD, StatusCodeCategory.UNPROCESSABLE_ENTITY, 1)

# 参数类
INVALID_ARGUMENT = build_status_code(StatusCodeSource.HTTP_STANDARD, StatusCodeCategory.BAD_REQUEST, 1)
UNSUPPORTED_ARGUMENT = build_status_code(StatusCodeSource.HTTP_STANDARD, StatusCodeCategory.BAD_REQUEST, 2)
MISSING_REQUIRED_CONFIG = build_status_code(StatusCodeSource.HTTP_STANDARD, StatusCodeCategory.BAD_REQUEST, 4)

# 鉴权类
UNAUTHORIZED = build_status_code(StatusCodeSource.HTTP_STANDARD, StatusCodeCategory.UNAUTHORIZED)
FORBIDDEN = build_status_code(StatusCodeSource.HTTP_STANDARD, StatusCodeCategory.FORBIDDEN)

# 不存在类
NOT_FOUND = build_status_code(StatusCodeSource.HTTP_STANDARD, StatusCodeCategory.NOT_FOUND)
NOT_FOUND_TEMPLATE = build_status_code(StatusCodeSource.HTTP_STANDARD, StatusCodeCategory.NOT_FOUND, 1)
NOT_FOUND_AGENT = build_status_code(StatusCodeSource.HTTP_STANDARD, StatusCodeCategory.NOT_FOUND, 2)
NOT_FOUND_ENTITY = build_status_code(StatusCodeSource.HTTP_STANDARD, StatusCodeCategory.NOT_FOUND, 3)
NOT_FOUND_SESSION = build_status_code(StatusCodeSource.HTTP_STANDARD, StatusCodeCategory.NOT_FOUND, 5)
NOT_FOUND_MODEL_CONFIG = build_status_code(StatusCodeSource.HTTP_STANDARD, StatusCodeCategory.NOT_FOUND, 6)
NOT_FOUND_PLATFORM = build_status_code(StatusCodeSource.HTTP_STANDARD, StatusCodeCategory.NOT_FOUND, 7)
NOT_FOUND_ACCOUNT = build_status_code(StatusCodeSource.HTTP_STANDARD, StatusCodeCategory.NOT_FOUND, 8)

# 冲突类
CONFLICT_EXISTS = build_status_code(StatusCodeSource.HTTP_STANDARD, StatusCodeCategory.CONFLICT, 1)
CONFLICT_NAME = build_status_code(StatusCodeSource.HTTP_STANDARD, StatusCodeCategory.CONFLICT, 2)
CONFLICT_STATE = build_status_code(StatusCodeSource.HTTP_STANDARD, StatusCodeCategory.CONFLICT, 3)

# 外部依赖/网关类
DEPENDENCY_NOT_READY = build_status_code(StatusCodeSource.HTTP_STANDARD, StatusCodeCategory.INTERNAL_SERVER_ERROR, 1)
QUERY_FAILED = build_status_code(StatusCodeSource.HTTP_STANDARD, StatusCodeCategory.INTERNAL_SERVER_ERROR, 2)
OPERATION_FAILED = build_status_code(StatusCodeSource.HTTP_STANDARD, StatusCodeCategory.INTERNAL_SERVER_ERROR, 4)
SANDBOX_OPERATION_FAILED = build_status_code(StatusCodeSource.HTTP_STANDARD, StatusCodeCategory.INTERNAL_SERVER_ERROR, 5)
EMBEDDING_CALL_FAILED = build_status_code(StatusCodeSource.HTTP_STANDARD, StatusCodeCategory.BAD_GATEWAY, 3)
EMBEDDING_NOT_READY = build_status_code(StatusCodeSource.HTTP_STANDARD, StatusCodeCategory.SERVICE_UNAVAILABLE, 1)
