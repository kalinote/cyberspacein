"""wiki_read 业务工具。"""
from __future__ import annotations

import json
from typing import Any

from loguru import logger

from app.service.analyst.tools.wiki._fields import pick_fields
from app.service.wiki.exceptions import WikiError
from app.service.wiki.wiki_page_service import WikiPageService
from app.service.nanobot.agent.tools.base import Tool, tool_parameters

logger = logger.bind(name=__name__)


@tool_parameters({
    "type": "object",
    "properties": {
        "wiki_id": {
            "type": "string",
            "description": "Wiki 页 ID（32 位 hex）",
            "minLength": 1,
        },
        "fields": {
            "type": "array",
            "items": {"type": "string", "minLength": 1},
            "description": (
                "可选。仅返回顶层字段白名单（camelCase），"
                "如 id、title、revision、contentTree、footnotes、references、citationHealth"
            ),
        },
    },
    "required": ["wiki_id"],
    "additionalProperties": False,
})
class WikiReadTool(Tool):
    @property
    def name(self) -> str:
        return "wiki_read"

    @property
    def description(self) -> str:
        return (
            "读取 Wiki 页完整详情（含 contentTree、footnotes、references）。"
            "footnotes/references 每项为 {id, text, ...}，编辑时须沿用相同字段名。"
            "若只需部分字段，请传入 fields 以减小返回体积。"
        )

    @property
    def read_only(self) -> bool:
        return True

    async def execute(self, **kwargs: Any) -> str:
        wiki_id = str(kwargs.get("wiki_id") or "").strip()
        if not wiki_id:
            return "[错误] wiki_id 不能为空"
        raw_fields = kwargs.get("fields")
        fields = raw_fields if isinstance(raw_fields, list) else None

        try:
            detail = await WikiPageService.get_page(wiki_id)
        except WikiError as exc:
            return f"[错误] {exc.message}"
        except Exception as exc:
            logger.exception(f"wiki_read 失败: wiki_id={wiki_id}")
            return f"[错误] 读取 Wiki 失败: {exc}"

        data = detail.model_dump(by_alias=True, mode="json")
        if fields:
            data = pick_fields(data, fields)
        return json.dumps(data, ensure_ascii=False)
