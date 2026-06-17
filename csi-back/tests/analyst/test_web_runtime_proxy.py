"""web_fetch 出站代理解析（与 async_fetch 一致）。"""

from __future__ import annotations

from app.service.analyst.tools import WebFetchTool
from app.service.analyst.web_runtime import resolve_outbound_proxy


def test_resolve_outbound_proxy_disabled_by_default(monkeypatch):
    monkeypatch.setattr("app.service.analyst.web_runtime.settings.USE_PROXY", False)
    monkeypatch.setattr(
        "app.service.analyst.web_runtime.settings.OUT_SERVICE_PROXY",
        "http://proxy.example:8080",
    )
    assert resolve_outbound_proxy() is None


def test_resolve_outbound_proxy_uses_out_service_proxy_when_enabled(monkeypatch):
    monkeypatch.setattr("app.service.analyst.web_runtime.settings.USE_PROXY", True)
    monkeypatch.setattr(
        "app.service.analyst.web_runtime.settings.OUT_SERVICE_PROXY",
        "http://proxy.example:8080",
    )
    assert resolve_outbound_proxy() == "http://proxy.example:8080"


def test_resolve_outbound_proxy_explicit_use_proxy_overrides_settings(monkeypatch):
    monkeypatch.setattr("app.service.analyst.web_runtime.settings.USE_PROXY", True)
    monkeypatch.setattr(
        "app.service.analyst.web_runtime.settings.OUT_SERVICE_PROXY",
        "http://proxy.example:8080",
    )
    assert resolve_outbound_proxy(use_proxy=False) is None
    assert resolve_outbound_proxy(use_proxy=True) == "http://proxy.example:8080"


def test_web_fetch_tool_proxy_property(monkeypatch):
    monkeypatch.setattr("app.service.analyst.web_runtime.settings.USE_PROXY", True)
    monkeypatch.setattr(
        "app.service.analyst.web_runtime.settings.OUT_SERVICE_PROXY",
        "http://proxy.example:8080",
    )
    tool = WebFetchTool()
    assert tool.proxy == "http://proxy.example:8080"
