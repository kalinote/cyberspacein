"""联网抓取运行期配置（非 Tool，供 web_fetch 使用）。"""

from __future__ import annotations

from dataclasses import dataclass, field

from app.core.config import settings


@dataclass(slots=True)
class AnalystWebToolsRuntime:
    ssrf_whitelist: list[str] = field(default_factory=list)


WEB_RUNTIME = AnalystWebToolsRuntime()


def resolve_outbound_proxy(use_proxy: bool | None = None) -> str | None:
    """USE_PROXY 开启时使用 OUT_SERVICE_PROXY。"""
    should_use_proxy = use_proxy if use_proxy is not None else settings.USE_PROXY
    return settings.OUT_SERVICE_PROXY if should_use_proxy else None
