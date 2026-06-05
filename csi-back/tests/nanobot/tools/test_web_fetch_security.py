"""Tests for web_fetch SSRF protection and untrusted content marking (Analyst)."""

from __future__ import annotations

import json
import socket
from unittest.mock import patch

import pytest

from app.service.analyst.tools import WebFetchTool


def _fake_resolve_private(hostname, port, family=0, type_=0):
    return [(socket.AF_INET, socket.SOCK_STREAM, 0, "", ("169.254.169.254", 0))]


def _fake_resolve_public(hostname, port, family=0, type_=0):
    return [(socket.AF_INET, socket.SOCK_STREAM, 0, "", ("93.184.216.34", 0))]


@pytest.mark.asyncio
async def test_web_fetch_blocks_private_ip():
    tool = WebFetchTool()
    with patch("app.service.analyst.network_security.socket.getaddrinfo", _fake_resolve_private):
        result = await tool.execute(url="http://169.254.169.254/computeMetadata/v1/")
    data = json.loads(result)
    assert "error" in data
    err = data["error"].lower()
    assert "内网" in data["error"] or "阻止" in data["error"] or "private" in err or "blocked" in err


@pytest.mark.asyncio
async def test_web_fetch_blocks_localhost():
    tool = WebFetchTool()

    def _resolve_localhost(hostname, port, family=0, type_=0):
        return [(socket.AF_INET, socket.SOCK_STREAM, 0, "", ("127.0.0.1", 0))]

    with patch("app.service.analyst.network_security.socket.getaddrinfo", _resolve_localhost):
        result = await tool.execute(url="http://localhost/admin")
    data = json.loads(result)
    assert "error" in data


@pytest.mark.asyncio
async def test_web_fetch_result_contains_untrusted_flag():
    tool = WebFetchTool()

    fake_html = "<html><head><title>Test</title></head><body><p>Hello world</p></body></html>"

    import httpx

    class FakeResponse:
        status_code = 200
        url = "https://example.com/page"
        text = fake_html
        headers = {"content-type": "text/html"}

        def raise_for_status(self):
            return None

        def json(self):
            return {}

    async def _fake_get(self, url, **kwargs):
        return FakeResponse()

    with patch("app.service.analyst.network_security.socket.getaddrinfo", _fake_resolve_public), patch(
        "httpx.AsyncClient.get", _fake_get
    ):
        result = await tool.execute(url="https://example.com/page")

    data = json.loads(result)
    assert data.get("untrusted") is True
    assert "外部内容" in data.get("text", "")


@pytest.mark.asyncio
async def test_web_fetch_blocks_private_redirect_before_returning_image(monkeypatch):
    tool = WebFetchTool()

    class FakeStreamResponse:
        headers = {"content-type": "image/png"}
        url = "http://127.0.0.1/secret.png"
        content = b"\x89PNG\r\n\x1a\n"

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def aread(self):
            return self.content

        def raise_for_status(self):
            return None

    class FakeClient:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        def stream(self, method, url, headers=None):
            return FakeStreamResponse()

    monkeypatch.setattr("app.service.analyst.tools.web_fetch.httpx.AsyncClient", FakeClient)

    with patch("app.service.analyst.network_security.socket.getaddrinfo", _fake_resolve_public):
        result = await tool.execute(url="https://example.com/image.png")

    data = json.loads(result)
    assert "error" in data
    assert "重定向" in data["error"] or "redirect" in data["error"].lower()
