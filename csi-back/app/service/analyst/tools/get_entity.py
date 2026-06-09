"""get_entity 业务工具。"""

from __future__ import annotations

import json
from typing import Any

from loguru import logger

from app.schemas.constants import ENTITY_TYPE_INDEX_MAP, EntityType
from app.service.nanobot.agent.tools.base import Tool, tool_parameters
from app.service.nanobot.config.schema import AgentDefaults

logger = logger.bind(name=__name__)

_MAX_RESULT_CHARS: int = AgentDefaults().max_tool_result_chars


def _field_content_length(value: Any) -> int:
    if isinstance(value, str):
        return len(value)
    return len(json.dumps(value, ensure_ascii=False))


def _slice_string(value: str, spec: dict[str, Any] | None) -> str:
    if not spec or not isinstance(spec, dict):
        return value
    offset = spec.get("offset", 0)
    limit = spec.get("limit")
    if not isinstance(offset, int) or isinstance(offset, bool):
        offset = 0
    offset = max(0, offset)
    if limit is None:
        return value[offset:]
    if not isinstance(limit, int) or isinstance(limit, bool):
        return value[offset:]
    limit = max(0, limit)
    return value[offset : offset + limit]


def _apply_field_limits(
    source: dict[str, Any],
    limits: dict[str, Any] | None,
) -> dict[str, Any]:
    if not limits or not isinstance(limits, dict):
        return dict(source)
    result = dict(source)
    for field, spec in limits.items():
        if field not in result:
            continue
        value = result[field]
        if not isinstance(value, str):
            continue
        result[field] = _slice_string(value, spec if isinstance(spec, dict) else None)
    return result


def _compute_field_length_report(
    source: dict[str, Any],
    limits: dict[str, Any] | None,
) -> dict[str, dict[str, int]]:
    report: dict[str, dict[str, int]] = {}
    limit_specs = limits if isinstance(limits, dict) else {}
    for field, value in source.items():
        entry: dict[str, int] = {"original": _field_content_length(value)}
        spec = limit_specs.get(field)
        if spec is not None and isinstance(value, str):
            limited_value = _slice_string(value, spec if isinstance(spec, dict) else None)
            entry["limited"] = _field_content_length(limited_value)
        report[field] = entry
    return report


def _format_oversize_error(
    total_chars: int,
    max_chars: int,
    field_report: dict[str, dict[str, int]],
) -> str:
    parts: list[str] = []
    for field, lengths in field_report.items():
        original = lengths.get("original", 0)
        if "limited" in lengths:
            parts.append(f"{field}: 原 {original}，截取后 {lengths['limited']}")
        else:
            parts.append(f"{field}: 原 {original}")
    field_detail = "；".join(parts)
    return (
        f"[错误] 返回内容超过工具结果上限（上限 {max_chars} 字符，当前 {total_chars} 字符）。\n"
        f"字段长度：{field_detail}。\n"
        f"建议使用 limits 参数对大字段设置 offset/limit 后重试。"
    )


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
        "limits": {
            "type": "object",
            "additionalProperties": {
                "type": "object",
                "properties": {
                    "offset": {"type": "integer", "minimum": 0},
                    "limit": {"type": "integer", "minimum": 0},
                },
                "additionalProperties": False,
            },
            "description": (
                "可选。对大字段分段读取：键为顶层字段名，值为 offset/limit。"
                "未列出的字段返回完整内容；limits 中多出的键忽略。"
                "仅在触发内容长度上限导致读取失败时推荐使用。"
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
            "以控制体积，避免无关字段占用上下文。"
            "若返回内容超过工具结果长度上限，将失败并提示各字段长度；"
            "此时可用 `limits` 对大字段按 offset/limit 分段读取。"
        )

    @property
    def read_only(self) -> bool:
        return True

    async def execute(self, **kwargs: Any) -> str:
        from app.db.elasticsearch import get_es

        entity_type = kwargs.get("entity_type")
        entity_uuid = kwargs.get("entity_uuid")
        raw_fields = kwargs.get("fields")
        raw_limits = kwargs.get("limits")
        limits = raw_limits if isinstance(raw_limits, dict) else None
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
        limited_source = _apply_field_limits(source, limits)
        payload = json.dumps(limited_source, ensure_ascii=False)
        if len(payload) > _MAX_RESULT_CHARS:
            field_report = _compute_field_length_report(source, limits)
            return _format_oversize_error(len(payload), _MAX_RESULT_CHARS, field_report)
        return payload
