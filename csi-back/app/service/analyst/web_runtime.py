"""联网搜索/抓取运行期配置（非 Tool，供 web_search、web_fetch 使用）。"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(slots=True)
class AnalystWebSearchConfig:
    provider: str = "duckduckgo"
    api_key: str = ""
    base_url: str = ""
    max_results: int = 5
    timeout: int = 30


@dataclass(slots=True)
class AnalystWebToolsRuntime:
    enable: bool = True
    proxy: str | None = None
    search: AnalystWebSearchConfig = field(default_factory=AnalystWebSearchConfig)
    ssrf_whitelist: list[str] = field(default_factory=list)


WEB_RUNTIME = AnalystWebToolsRuntime()
