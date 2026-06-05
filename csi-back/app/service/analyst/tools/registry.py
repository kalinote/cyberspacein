"""业务工具注册表与按白名单实例化。"""

from __future__ import annotations

from loguru import logger

from app.service.analyst.tools.get_current_time import GetCurrentTimeTool
from app.service.analyst.tools.get_entity import GetEntityTool
from app.service.analyst.tools.search_entities import SearchEntitiesTool
from app.service.analyst.tools.modify_entity import ModifyEntityTool
from app.service.analyst.tools.notify_user import NotifyUserTool
from app.service.analyst.tools.web_fetch import WebFetchTool
from app.service.analyst.web_runtime import WEB_RUNTIME
from app.service.analyst.tools.web_search import WebSearchTool
from app.service.analyst.tools.wiki import (
    WikiCreateTool,
    WikiEditTool,
    WikiListTool,
    WikiReadTool,
)
from app.service.analyst.tools.use_skill import UseSkillTool
from app.service.analyst.tools.write_todos import WriteTodosTool
from app.service.nanobot.agent.tools.base import Tool

logger = logger.bind(name=__name__)

BUSINESS_TOOL_CLASSES: dict[str, type[Tool]] = {
    "get_current_time": GetCurrentTimeTool,
    "get_entity": GetEntityTool,
    "search_entities": SearchEntitiesTool,
    "modify_entity": ModifyEntityTool,
    "notify_user": NotifyUserTool,
    "write_todos": WriteTodosTool,
    "web_search": WebSearchTool,
    "web_fetch": WebFetchTool,
    "wiki_list": WikiListTool,
    "wiki_read": WikiReadTool,
    "wiki_create": WikiCreateTool,
    "wiki_edit": WikiEditTool,
    "use_skill": UseSkillTool,
}


def build_business_tools(enabled_names: list[str]) -> list[Tool]:
    """按名称白名单实例化业务工具。未识别的名字静默忽略并打 warn 日志。"""
    tools: list[Tool] = []
    for name in enabled_names or []:
        cls = BUSINESS_TOOL_CLASSES.get(name)
        if cls is None:
            logger.warning(f"未知业务工具名，已忽略: {name}")
            continue
        if name == "web_search":
            tools.append(cls(config=WEB_RUNTIME.search, proxy=WEB_RUNTIME.proxy))
            continue
        if name == "web_fetch":
            tools.append(cls(proxy=WEB_RUNTIME.proxy))
            continue
        tools.append(cls())
    return tools
