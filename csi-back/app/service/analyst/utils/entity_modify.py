"""实体字段修改：在内存中应用 modifications，并写回 Elasticsearch。"""
from __future__ import annotations

import copy
from datetime import datetime
from typing import Any

from elasticsearch.exceptions import NotFoundError
from loguru import logger

from app.db.elasticsearch import get_es
from app.schemas.constants import ENTITY_TYPE_INDEX_MAP

logger = logger.bind(name=__name__)


def _path_parts(field: str) -> list[str]:
    return [p for p in str(field or "").strip().split(".") if p]


def _get_by_path(doc: dict[str, Any], parts: list[str]) -> Any:
    cur: Any = doc
    for part in parts:
        if not isinstance(cur, dict):
            return None
        cur = cur.get(part)
    return cur


def _set_by_path(doc: dict[str, Any], parts: list[str], value: Any) -> None:
    cur = doc
    for part in parts[:-1]:
        nxt = cur.get(part)
        if not isinstance(nxt, dict):
            nxt = {}
            cur[part] = nxt
        cur = nxt
    cur[parts[-1]] = value


def _del_by_path(doc: dict[str, Any], parts: list[str]) -> None:
    cur: Any = doc
    for part in parts[:-1]:
        if not isinstance(cur, dict):
            return
        cur = cur.get(part)
    if isinstance(cur, dict) and parts:
        cur.pop(parts[-1], None)


def apply_modifications_to_source(
    source: dict[str, Any],
    modifications: list[dict[str, Any]],
) -> dict[str, Any]:
    """在 source 副本上应用修改列表，返回用于 ES `doc` 的部分字段。"""
    working = copy.deepcopy(source)
    touched_roots: set[str] = set()

    for item in modifications:
        field = str(item.get("field") or "").strip()
        action = str(item.get("action") or "").strip()
        parts = _path_parts(field)
        if not parts:
            raise ValueError("modifications 中存在空的 field")
        touched_roots.add(parts[0])
        value = item.get("value")

        if action == "set":
            _set_by_path(working, parts, value)
        elif action == "append":
            current = _get_by_path(working, parts)
            if current is None:
                current = []
            if not isinstance(current, list):
                raise ValueError(f"字段 {field} 不是数组，无法 append")
            _set_by_path(working, parts, [*current, value])
        elif action == "remove":
            if value is None:
                _del_by_path(working, parts)
            else:
                current = _get_by_path(working, parts)
                if isinstance(current, list):
                    new_list = [x for x in current if x != value]
                    _set_by_path(working, parts, new_list)
                else:
                    _del_by_path(working, parts)
        else:
            raise ValueError(f"不支持的 action: {action}")

    doc: dict[str, Any] = {k: working[k] for k in touched_roots if k in working}
    doc["update_at"] = datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
    return doc


async def apply_entity_modifications_to_es(
    entity_type: str,
    entity_uuid: str,
    modifications: list[dict[str, Any]],
) -> str | None:
    """审批通过后写回 ES。成功返回 None，失败返回错误说明。"""
    index = ENTITY_TYPE_INDEX_MAP.get(entity_type)
    if index is None:
        return f"不支持的实体类型: {entity_type}"

    es = get_es()
    if es is None:
        return "Elasticsearch 未初始化"

    try:
        resp = await es.get(index=index, id=entity_uuid)
    except NotFoundError:
        return f"实体不存在: {entity_type}:{entity_uuid}"
    except Exception as exc:
        logger.exception(f"读取实体失败: {entity_type}:{entity_uuid}")
        return f"读取实体失败: {exc}"

    source = resp.get("_source") or {}
    if not isinstance(source, dict):
        return "实体数据格式异常"

    try:
        doc = apply_modifications_to_source(source, modifications)
    except ValueError as exc:
        return str(exc)

    try:
        await es.update(index=index, id=entity_uuid, body={"doc": doc})
    except NotFoundError:
        return f"实体不存在: {entity_type}:{entity_uuid}"
    except Exception as exc:
        logger.exception(f"写入实体失败: {entity_type}:{entity_uuid}")
        return f"写入实体失败: {exc}"

    return None
