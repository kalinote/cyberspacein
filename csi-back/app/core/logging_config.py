import logging
import sys
from loguru import logger

from app.core.config import settings


class InterceptHandler(logging.Handler):
    """将标准库 logging 的记录转发到 loguru。"""

    def emit(self, record: logging.LogRecord) -> None:
        try:
            level = logger.level(record.levelname).name
        except ValueError:
            level = record.levelno

        frame, depth = logging.currentframe(), 2
        while frame and frame.f_code.co_filename == logging.__file__:
            frame = frame.f_back
            depth += 1

        logger.bind(name=record.name).opt(
            depth=depth,
            exception=record.exc_info,
        ).log(level, record.getMessage())


def _ensure_extra_name(record: dict) -> bool:
    record["extra"].setdefault("name", str(record["name"]))
    return True


# 需要接管的命名 logger（uvicorn / FastAPI / Starlette 体系）
_INTERCEPTED_LOGGERS = (
    "uvicorn",
    "uvicorn.error",
    "uvicorn.access",
    "uvicorn.asgi",
    "fastapi",
    "starlette",
    "asyncio",
    "watchfiles",
    "watchfiles.main",
)

# 需要降噪的第三方 logger
_NOISY_LOGGERS = {
    "pymongo": logging.WARNING,
    "httpx": logging.INFO,
    "httpcore": logging.WARNING,
    "urllib3": logging.WARNING,
    "botocore": logging.WARNING,
    "boto3": logging.WARNING,
    "aiobotocore": logging.WARNING,
    "docker": logging.INFO,
    "multipart": logging.WARNING,
}


def setup_logging() -> None:
    log_level = "DEBUG" if settings.DEBUG else "INFO"

    logger.remove()
    logger.add(
        sys.stderr,
        level=log_level,
        colorize=True,
        backtrace=True,
        diagnose=settings.DEBUG,
        format=(
            "<green>{time:YYYY-MM-DD HH:mm:ss}</green> | "
            "<level>{level: <8}</level> | "
            "<cyan>{extra[name]}</cyan> | "
            "<level>{message}</level>"
        ),
        filter=_ensure_extra_name,
    )

    intercept_handler = InterceptHandler()

    # 接管 root logger，所有未单独配置 handler 的记录都会走到这里
    logging.root.handlers = [intercept_handler]
    logging.root.setLevel(logging.DEBUG if settings.DEBUG else logging.INFO)

    # 接管 uvicorn / FastAPI / Starlette 等命名 logger，避免它们绕过 loguru
    for name in _INTERCEPTED_LOGGERS:
        std_logger = logging.getLogger(name)
        std_logger.handlers = [intercept_handler]
        std_logger.propagate = False

    # 降噪第三方库
    for name, level in _NOISY_LOGGERS.items():
        logging.getLogger(name).setLevel(level)
