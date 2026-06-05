"""get_entity 业务工具。"""

from __future__ import annotations

import json
from typing import Any

from loguru import logger

from app.schemas.constants import ENTITY_TYPE_INDEX_MAP, EntityType
from app.service.nanobot.agent.tools.base import Tool, tool_parameters

logger = logger.bind(name=__name__)


@tool_parameters({
    "type": "object",
    "properties": {
        "entity_type": {
            "type": "string",
            "enum": [e.value for e in EntityType],
            "description": "实体类型",
        },
        "entity_uuid": {
            "type": "string",
            "description": "实体的唯一标识（ES 文档 _id）",
            "minLength": 1,
        },
        "fields": {
            "type": "array",
            "items": {"type": "string", "minLength": 1},
            "description": (
                "可选。仅拉取 `_source` 中列出的字段（Elasticsearch `_source_includes`）。"
                "善用该字段可显著减小返回体积，"
                "避免整篇文档触发工具结果落盘后仅保留短预览而无法看到所需字段内容"
            ),
        },
    },
    "required": ["entity_type", "entity_uuid"],
    "additionalProperties": False,
})
class GetEntityTool(Tool):
    """按 (entity_type, entity_uuid) 从 Elasticsearch 拉实体详情。"""

    @property
    def name(self) -> str:
        return "get_entity"

    @property
    def description(self) -> str:
        return (
            "根据实体类型和 UUID 从 Elasticsearch 获取 `_source`。"
            "默认返回全部字段的 JSON；若只需正文或少数键，务必传入 `fields`"
            "以控制体积，避免无关字段占用上下文"
        )

    @property
    def read_only(self) -> bool:
        return True

    async def execute(self, **kwargs: Any) -> str:
        from app.db.elasticsearch import get_es

        entity_type = kwargs.get("entity_type")
        entity_uuid = kwargs.get("entity_uuid")
        raw_fields = kwargs.get("fields")
        index = ENTITY_TYPE_INDEX_MAP.get(entity_type)
        if index is None:
            return f"[错误] 不支持的实体类型: {entity_type}"
        es = get_es()
        if es is None:
            return "[错误] Elasticsearch 未初始化"
        get_kw: dict[str, Any] = {"index": index, "id": entity_uuid}
        if isinstance(raw_fields, list) and raw_fields:
            cleaned = [str(f).strip() for f in raw_fields if str(f).strip()]
            if cleaned:
                get_kw["_source_includes"] = cleaned
        try:
            resp = await es.get(**get_kw)
        except Exception as exc:
            logger.exception(
                f"get_entity 查询失败: type={entity_type} uuid={entity_uuid}"
            )
            return f"[错误] 查询实体失败: {exc}"
        source = resp.get("_source") or {}
        return json.dumps(source, ensure_ascii=False)
