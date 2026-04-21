import logging
import sys
from loguru import logger

from app.core.config import settings


class InterceptHandler(logging.Handler):
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


def setup_logging() -> None:
    log_level = "DEBUG" if settings.DEBUG else "INFO"

    logger.remove()
    logger.add(
        sys.stderr,
        level=log_level,
        format="{time:YYYY-MM-DD HH:mm:ss} - {extra[name]} - {level} - {message}",
        filter=_ensure_extra_name,
    )

    logging.root.handlers = [InterceptHandler()]
    logging.root.setLevel(logging.DEBUG if settings.DEBUG else logging.INFO)

    logging.getLogger("pymongo").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.DEBUG)
