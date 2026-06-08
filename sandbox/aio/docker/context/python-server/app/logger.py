from __future__ import annotations

import logging
import sys


def setup_logging(level: str = 'INFO') -> None:
    """Configure application logging to stdout with millisecond timestamps."""
    log_format = '[%(asctime)s.%(msecs)03d:%(levelname)s] %(message)s'
    date_format = '%m%d/%H%M%S'
    formatter = logging.Formatter(log_format, datefmt=date_format)

    root_logger = logging.getLogger()
    root_logger.setLevel(level.upper())

    if root_logger.hasHandlers():
        root_logger.handlers.clear()

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(formatter)
    root_logger.addHandler(handler)

    for name in ('uvicorn', 'uvicorn.error', 'uvicorn.access'):
        uv_logger = logging.getLogger(name)
        uv_logger.handlers.clear()
        uv_logger.propagate = True
