"""Tests for DuckDuckGo web search (Analyst external tools)."""

from __future__ import annotations

import threading

import pytest

from app.service.analyst.tools import WebSearchTool


def test_duckduckgo_search_is_exclusive():
    tool = WebSearchTool()
    assert tool.exclusive is True
    assert tool.concurrency_safe is False


@pytest.mark.asyncio
async def test_duckduckgo_search(monkeypatch):
    class MockDDGS:
        def __init__(self, **kw):
            pass

        def text(self, query, max_results=5):
            return [{"title": "DDG Result", "href": "https://ddg.example", "body": "From DuckDuckGo"}]

    monkeypatch.setattr("ddgs.DDGS", MockDDGS)
    tool = WebSearchTool()
    result = await tool.execute(query="hello")
    assert "DDG Result" in result
    assert "https://ddg.example" in result


@pytest.mark.asyncio
async def test_duckduckgo_no_results(monkeypatch):
    class MockDDGS:
        def __init__(self, **kw):
            pass

        def text(self, query, max_results=5):
            return []

    monkeypatch.setattr("ddgs.DDGS", MockDDGS)
    tool = WebSearchTool()
    result = await tool.execute(query="empty")
    assert "没有搜索结果" in result


@pytest.mark.asyncio
async def test_duckduckgo_timeout_returns_error(monkeypatch):
    gate = threading.Event()

    class HangingDDGS:
        def __init__(self, **kw):
            pass

        def text(self, query, max_results=5):
            gate.wait(timeout=10)
            return []

    monkeypatch.setattr("ddgs.DDGS", HangingDDGS)
    tool = WebSearchTool()
    tool.DEFAULT_TIMEOUT = 0.2
    result = await tool.execute(query="test")
    gate.set()
    assert "错误" in result
