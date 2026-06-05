"""wiki_list 业务工具。"""
from __future__ import annotations

import json
from typing import Any

from loguru import logger

from app.schemas.constants import WikiPageStatusEnum
from app.service.wiki.exceptions import WikiError
from app.service.wiki.wiki_page_service import WikiPageService
from app.service.nanobot.agent.tools.base import Tool, tool_parameters

logger = logger.bind(name=__name__)


@tool_parameters({
    "type": "object",
    "properties": {
        "q": {"type": "string", "description": "搜索关键词"},
        "category": {"type": "string", "description": "分类标签筛选"},
        "status": {
            "type": "string",
            "enum": [e.value for e in WikiPageStatusEnum],
            "description": "页面状态",
        },
        "sort_by": {
            "type": "string",
            "enum": ["updated_at", "created_at", "title"],
            "description": "排序字段",
        },
        "sort_order": {
            "type": "string",
            "enum": ["asc", "desc"],
            "description": "排序方向",
        },
        "page": {"type": "integer", "minimum": 1, "description": "页码"},
        "page_size": {
            "type": "integer",
            "minimum": 1,
            "maximum": 100,
            "description": "每页条数",
        },
    },
    "additionalProperties": False,
})
class WikiListTool(Tool):
    @property
    def name(self) -> str:
        return "wiki_list"

    @property
    def description(self) -> str:
        return "分页列出或搜索 Wiki 专题页，返回 id、标题、状态、修订号等摘要。"

    @property
    def read_only(self) -> bool:
        return True

    async def execute(self, **kwargs: Any) -> str:
        status_raw = kwargs.get("status")
        status = WikiPageStatusEnum(status_raw) if status_raw else None
        try:
            result = await WikiPageService.list_pages(
                q=kwargs.get("q"),
                category=kwargs.get("category"),
                status=status,
                sort_by=kwargs.get("sort_by") or "updated_at",
                sort_order=kwargs.get("sort_order") or "desc",
                page=int(kwargs.get("page") or 1),
                page_size=int(kwargs.get("page_size") or 10),
            )
        except WikiError as exc:
            return f"[错误] Wiki 列表查询失败: {exc.message}"
        except Exception as exc:
            logger.exception("wiki_list 失败")
            return f"[错误] Wiki 列表查询失败: {exc}"

        items = [
            {
                "id": item.id,
                "title": item.title,
                "status": item.status.value if hasattr(item.status, "value") else item.status,
                "categories": item.categories,
                "revision": item.revision,
                "lastModified": item.last_modified.isoformat(),
            }
            for item in result.items
        ]
        return json.dumps(
            {"total": result.total, "page": result.page, "pageSize": result.page_size, "items": items},
            ensure_ascii=False,
        )
