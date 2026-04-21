"""app.core.logging_config 日志初始化与拦截处理器测试。"""

import logging

import pytest

from app.core.logging_config import InterceptHandler, setup_logging
import app.core.logging_config as logging_config


def test_intercept_handler_emit_does_not_raise():
    # InterceptHandler 将标准 logging 转发到 loguru，不应在常规日志上抛错
    log = logging.getLogger("test_intercept_handler")
    log.handlers.clear()
    log.propagate = False
    log.addHandler(InterceptHandler())
    log.setLevel(logging.INFO)
    try:
        log.info("测试日志转发")
    finally:
        log.handlers.clear()


def test_setup_logging_debug_sets_levels(monkeypatch: pytest.MonkeyPatch) -> None:
    # DEBUG=True 时根 logger 与 httpx 为 DEBUG，pymongo 仍为 WARNING
    monkeypatch.setattr(logging_config.settings, "DEBUG", True)
    setup_logging()
    assert logging.getLogger("pymongo").level == logging.WARNING
    assert logging.getLogger("httpx").level == logging.DEBUG
    assert logging.root.level == logging.DEBUG


def test_setup_logging_info_sets_root_info(monkeypatch: pytest.MonkeyPatch) -> None:
    # DEBUG=False 时根 logger 为 INFO
    monkeypatch.setattr(logging_config.settings, "DEBUG", False)
    setup_logging()
    assert logging.root.level == logging.INFO
