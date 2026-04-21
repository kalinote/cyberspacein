from unittest.mock import AsyncMock, patch

import httpx
import pytest

from app.utils.network import get_local_ip, log_http_error_response, log_http_error_response_async


def test_get_local_ip_returns_non_empty_string():
    """get_local_ip 返回非空字符串。"""
    ip = get_local_ip()
    assert isinstance(ip, str)
    assert len(ip) > 0


def test_log_http_error_response_skips_success():
    """2xx 响应不调用 logger.error。"""
    req = httpx.Request("GET", "https://example.com/")
    resp = httpx.Response(200, request=req)
    with patch("app.utils.network.logger") as mock_logger:
        log_http_error_response(resp)
        mock_logger.error.assert_not_called()


def test_log_http_error_response_logs_on_client_error():
    """4xx 响应记录 error 日志。"""
    req = httpx.Request("GET", "https://example.com/x")
    resp = httpx.Response(404, request=req, content=b"not found")
    with patch("app.utils.network.logger") as mock_logger:
        log_http_error_response(resp)
        mock_logger.error.assert_called_once()


@pytest.mark.asyncio
async def test_log_http_error_response_async_logs_on_error():
    """异步：5xx 响应记录 error 日志。"""
    req = httpx.Request("GET", "https://example.com/y")
    resp = httpx.Response(500, request=req, content=b"err")
    resp.aread = AsyncMock()
    with patch("app.utils.network.logger") as mock_logger:
        await log_http_error_response_async(resp)
        mock_logger.error.assert_called_once()


@pytest.mark.asyncio
async def test_log_http_error_response_async_skips_success():
    """异步：2xx 不调用 logger.error。"""
    req = httpx.Request("GET", "https://example.com/z")
    resp = httpx.Response(200, request=req)
    with patch("app.utils.network.logger") as mock_logger:
        await log_http_error_response_async(resp)
        mock_logger.error.assert_not_called()
