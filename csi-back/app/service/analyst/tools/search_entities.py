"""search_entities 业务工具：多关键词实体检索（仅 keyword 模式）。"""
from __future__ import annotations

import json
from datetime import datetime
from typing import Any

from loguru import logger

from app.schemas.constants import EntityType
from app.schemas.search import EntityKeywordSearchParams
from app.service.nanobot.agent.tools.base import Tool, tool_parameters

logger = logger.bind(name=__name__)


def _parse_datetime(value: Any) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value
    text = str(value).strip()
    if not text:
        return None
    return datetime.fromisoformat(text.replace("Z", "+00:00"))


def _tool_hit_to_dict(hit: Any) -> dict[str, Any]:
    return {
        "uuid": hit.uuid,
        "entityType": hit.entity_type,
        "title": hit.title,
        "snippets": hit.snippets,
        "keywordsHits": hit.keywords_hits,
    }


@tool_parameters({
    "type": "object",
    "properties": {
        "keywords": {
            "type": "array",
            "items": {"type": "string", "minLength": 1},
            "minItems": 1,
            "description": "关键词列表",
        },
        "keyword_match_mode": {
            "type": "string",
            "enum": ["and", "or"],
            "description": "多关键词匹配：and 须全部命中（默认），or 命中任意一个",
        },
        "platform": {"type": "string", "description": "平台过滤，精确匹配"},
        "entity_type": {
            "type": "array",
            "items": {
                "type": "string",
                "enum": [e.value for e in EntityType],
            },
            "description": "实体类型过滤",
        },
        "author": {"type": "string", "description": "作者名，精确匹配"},
        "aigc": {"type": "boolean", "description": "是否 AIGC"},
        "nsfw": {"type": "boolean", "description": "是否 NSFW"},
        "is_highlighted": {"type": "boolean", "description": "是否重点目标"},
        "start_at": {
            "type": "string",
            "description": "last_edit_at 起始时间 ISO8601",
        },
        "end_at": {
            "type": "string",
            "description": "last_edit_at 截止时间 ISO8601",
        },
        "sort_by": {
            "type": "string",
            "enum": ["crawled_at", "last_edit_at", "time", "publish_at", "relevance"],
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
    "required": ["keywords"],
    "additionalProperties": False,
})
class SearchEntitiesTool(Tool):
    @property
    def name(self) -> str:
        return "search_entities"

    @property
    def description(self) -> str:
        return (
            "按关键词在 Elasticsearch 中检索实体（仅关键词模式，非语义搜索）。"
            "返回 uuid、entityType、完整标题、正文高亮片段 snippets，不含全文。"
            "需要正文时请用 get_entity。"
        )

    @property
    def read_only(self) -> bool:
        return True

    async def execute(self, **kwargs: Any) -> str:
        from app.db.elasticsearch import get_es
        from app.service.search import search_entities_keyword

        raw_keywords = kwargs.get("keywords")
        if not isinstance(raw_keywords, list) or not raw_keywords:
            return "[错误] keywords 必须为非空字符串数组"

        mode = str(kwargs.get("keyword_match_mode") or "and").lower()
        if mode not in ("and", "or"):
            return "[错误] keyword_match_mode 必须为 and 或 or"

        try:
            params = EntityKeywordSearchParams(
                keywords=raw_keywords,
                keyword_match_mode=mode,  # type: ignore[arg-type]
                platform=kwargs.get("platform"),
                entity_type=kwargs.get("entity_type"),
                author=kwargs.get("author"),
                aigc=kwargs.get("aigc"),
                nsfw=kwargs.get("nsfw"),
                is_highlighted=kwargs.get("is_highlighted"),
                start_at=_parse_datetime(kwargs.get("start_at")),
                end_at=_parse_datetime(kwargs.get("end_at")),
                sort_by=kwargs.get("sort_by"),
                sort_order=kwargs.get("sort_order") or "desc",
                page=int(kwargs.get("page") or 1),
                page_size=int(kwargs.get("page_size") or 10),
            )
        except (ValueError, TypeError) as exc:
            return f"[错误] 参数无效: {exc}"

        es = get_es()
        if es is None:
            return "[错误] Elasticsearch 未初始化"

        try:
            result = await search_entities_keyword(es, params)
        except Exception as exc:
            logger.exception("search_entities 检索失败")
            return f"[错误] 实体搜索失败: {exc}"

        payload = {
            "total": result.total,
            "page": result.page,
            "pageSize": result.page_size,
            "items": [_tool_hit_to_dict(h) for h in result.items],
        }
        return json.dumps(payload, ensure_ascii=False)
