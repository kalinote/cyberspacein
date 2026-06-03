"""Wiki 写操作：审批通过后调用 WikiPageService。"""
from __future__ import annotations

import re
from typing import Any

from loguru import logger

from app.schemas.constants import EntityType, WikiPageStatusEnum
from app.schemas.wiki import WikiInfoboxSchema
from app.service.wiki.exceptions import WikiError, WikiRevisionConflictError
from app.service.wiki.wiki_page_service import WikiPageService

logger = logger.bind(name=__name__)

WIKI_EDIT_OPERATIONS = frozenset({
    "patch_meta",
    "patch_main",
    "add_section",
    "patch_section",
    "move_section",
    "put_footnotes",
    "put_references",
})

_FOOTNOTE_ID_RE = re.compile(r"^[a-z]+$")
_REFERENCE_ID_RE = re.compile(r"^[0-9]+$")
_ENTITY_UUID_RE = re.compile(r"^[a-f0-9]{32}$")
_ALLOWED_ENTITY_TYPES = frozenset(e.value for e in EntityType)


def _format_revision_conflict(exc: WikiRevisionConflictError) -> str:
    return (
        f"[错误] 修订号冲突（241003）：{exc.message}。"
        "请使用 wiki_read 获取最新 revision 后重新发起编辑。"
    )


def _operator_label(agent_id: str | None) -> str | None:
    if not agent_id:
        return None
    return f"agent:{agent_id}"


def _validate_footnote_items(items: list[Any]) -> str | None:
    seen: set[str] = set()
    for i, raw in enumerate(items):
        if not isinstance(raw, dict):
            return f"[错误] put_footnotes items[{i}] 须为对象"
        if "key" in raw or "content" in raw:
            return "[错误] put_footnotes 使用 id、text 字段，勿用 key/content"
        fid = str(raw.get("id") or "").strip()
        text = str(raw.get("text") or "").strip()
        if not fid or not text:
            return f"[错误] put_footnotes items[{i}] 缺少 id 或 text"
        if not _FOOTNOTE_ID_RE.match(fid):
            return (
                f"[错误] put_footnotes items[{i}] id={fid!r} 须为小写字母 "
                "（a、b、c…aa、ab），勿用数字"
            )
        if fid in seen:
            return f"[错误] put_footnotes 重复 id: {fid}"
        seen.add(fid)
    return None


def _validate_reference_items(items: list[Any]) -> str | None:
    seen: set[str] = set()
    for i, raw in enumerate(items):
        if not isinstance(raw, dict):
            return f"[错误] put_references items[{i}] 须为对象"
        if "key" in raw or "content" in raw:
            return "[错误] put_references 使用 id、text 字段，勿用 key/content"
        rid = str(raw.get("id") or "").strip()
        text = str(raw.get("text") or "").strip()
        entity_type = str(
            raw.get("entity_type") or raw.get("entityType") or ""
        ).strip()
        entity_uuid = str(
            raw.get("entity_uuid") or raw.get("entityUuid") or ""
        ).strip()
        url = str(raw.get("url") or "").strip()
        if not rid or not text:
            return f"[错误] put_references items[{i}] 缺少 id 或 text"
        if not _REFERENCE_ID_RE.match(rid):
            return (
                f"[错误] put_references items[{i}] id={rid!r} 须为数字字符串 "
                "（1、2、3…），勿用字母"
            )
        if rid in seen:
            return f"[错误] put_references 重复 id: {rid}"
        seen.add(rid)
        if entity_type not in _ALLOWED_ENTITY_TYPES:
            return (
                f"[错误] put_references items[{i}] entityType 须为 "
                f"{sorted(_ALLOWED_ENTITY_TYPES)} 之一"
            )
        if not _ENTITY_UUID_RE.match(entity_uuid):
            return f"[错误] put_references items[{i}] entityUuid 须为 32 位 hex"
        expected_url = f"/details/{entity_type}/{entity_uuid}"
        if url != expected_url:
            return (
                f"[错误] put_references items[{i}] url 须为 {expected_url!r}"
            )
    return None


def normalize_reference_items(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Agent 常用 camelCase，转为 WikiReferenceModel 字段名。"""
    out: list[dict[str, Any]] = []
    for raw in items:
        out.append(
            {
                "id": str(raw.get("id") or "").strip(),
                "text": str(raw.get("text") or "").strip(),
                "url": str(raw.get("url") or "").strip(),
                "entity_type": str(
                    raw.get("entity_type") or raw.get("entityType") or ""
                ).strip(),
                "entity_uuid": str(
                    raw.get("entity_uuid") or raw.get("entityUuid") or ""
                ).strip(),
            }
        )
    return out


def validate_wiki_edit_params(operation: str, params: dict[str, Any]) -> str | None:
    """校验 operation 与 params 组合；通过返回 None，否则返回错误文案。"""
    if operation == "add_section" and str(params.get("section_id") or "").strip():
        return (
            "[错误] add_section 勿传 section_id，新章节 ID 由服务端生成，"
            "请使用响应中的 newSectionId 或 wiki_read 的 contentTree.section"
        )
    if operation == "put_footnotes":
        items = params.get("items")
        if not isinstance(items, list):
            return "[错误] put_footnotes 需要 items 数组"
        return _validate_footnote_items(items)
    if operation == "put_references":
        items = params.get("items")
        if not isinstance(items, list):
            return "[错误] put_references 需要 items 数组"
        return _validate_reference_items(items)
    return None


async def apply_wiki_create(
    payload: dict[str, Any],
    *,
    agent_id: str | None = None,
) -> tuple[dict[str, Any] | None, str | None]:
    title = str(payload.get("title") or "").strip()
    if not title:
        return None, "[错误] 标题不能为空"
    try:
        detail = await WikiPageService.create_page(
            title=title,
            source_note=payload.get("source_note"),
            categories=payload.get("categories") or [],
            operator=_operator_label(agent_id),
        )
    except WikiError as exc:
        return None, f"[错误] 创建 Wiki 页失败: {exc.message}"
    except Exception as exc:
        logger.exception("apply_wiki_create 失败")
        return None, f"[错误] 创建 Wiki 页失败: {exc}"

    return {
        "ok": True,
        "wikiId": detail.id,
        "revision": detail.revision,
        "title": detail.title,
    }, None


async def apply_wiki_edit(
    payload: dict[str, Any],
    *,
    agent_id: str | None = None,
) -> tuple[dict[str, Any] | None, str | None]:
    wiki_id = str(payload.get("wiki_id") or "").strip()
    operation = str(payload.get("operation") or "").strip()
    expected_revision = payload.get("expected_revision")
    change_summary = str(payload.get("change_summary") or "")
    params = payload.get("params") or {}

    if not wiki_id:
        return None, "[错误] wiki_id 不能为空"
    if operation not in WIKI_EDIT_OPERATIONS:
        return None, f"[错误] 不支持的 operation: {operation}"
    if not isinstance(expected_revision, int) or expected_revision < 1:
        return None, "[错误] expected_revision 必须为 >= 1 的整数"

    operator = _operator_label(agent_id)

    try:
        if operation == "patch_meta":
            status_raw = params.get("status")
            status = (
                WikiPageStatusEnum(status_raw) if status_raw is not None else None
            )
            detail = await WikiPageService.patch_meta(
                wiki_id,
                expected_revision=expected_revision,
                change_summary=change_summary,
                title=params.get("title"),
                source_note=params.get("source_note"),
                categories=params.get("categories"),
                status=status,
                operator=operator,
            )
            return {"ok": True, "wikiId": detail.id, "revision": detail.revision}, None

        if operation == "patch_main":
            infobox_set = bool(params.get("infobox_set"))
            infobox = params.get("infobox")
            infobox_obj = WikiInfoboxSchema.model_validate(infobox) if infobox_set and infobox else None
            detail = await WikiPageService.patch_main(
                wiki_id,
                expected_revision=expected_revision,
                change_summary=change_summary,
                content=params.get("content"),
                infobox=infobox_obj,
                infobox_set=infobox_set,
                operator=operator,
            )
            return {"ok": True, "wikiId": detail.id, "revision": detail.revision}, None

        if operation == "add_section":
            param_err = validate_wiki_edit_params(operation, params)
            if param_err:
                return None, param_err
            title = str(params.get("title") or "").strip()
            parent_section = str(params.get("parent_section") or "").strip()
            if not title or not parent_section:
                return None, "[错误] add_section 需要 title 与 parent_section"
            detail, section_id = await WikiPageService.add_section(
                wiki_id,
                expected_revision=expected_revision,
                parent_section=parent_section,
                title=title,
                after_section=params.get("after_section"),
                change_summary=change_summary,
                operator=operator,
            )
            content = str(params.get("content") or "").strip()
            if content:
                detail = await WikiPageService.patch_section(
                    wiki_id,
                    section_id,
                    expected_revision=detail.revision,
                    content=content,
                    change_summary=change_summary,
                    operator=operator,
                )
            return {
                "ok": True,
                "wikiId": detail.id,
                "revision": detail.revision,
                "newSectionId": section_id,
            }, None

        if operation == "patch_section":
            section_id = str(params.get("section_id") or "").strip()
            if not section_id:
                return None, "[错误] patch_section 需要 section_id"
            infobox_set = bool(params.get("infobox_set"))
            infobox = params.get("infobox")
            infobox_obj = WikiInfoboxSchema.model_validate(infobox) if infobox_set and infobox else None
            detail = await WikiPageService.patch_section(
                wiki_id,
                section_id,
                expected_revision=expected_revision,
                change_summary=change_summary,
                title=params.get("title"),
                content=params.get("content"),
                infobox=infobox_obj,
                infobox_set=infobox_set,
                operator=operator,
            )
            return {"ok": True, "wikiId": detail.id, "revision": detail.revision}, None

        if operation == "move_section":
            section_id = str(params.get("section_id") or "").strip()
            parent_section = str(params.get("parent_section") or "").strip()
            if not section_id or not parent_section:
                return None, "[错误] move_section 需要 section_id 与 parent_section"
            detail = await WikiPageService.move_section(
                wiki_id,
                section_id,
                expected_revision=expected_revision,
                parent_section=parent_section,
                after_section=params.get("after_section"),
                change_summary=change_summary,
                operator=operator,
            )
            return {"ok": True, "wikiId": detail.id, "revision": detail.revision}, None

        if operation == "put_footnotes":
            param_err = validate_wiki_edit_params(operation, params)
            if param_err:
                return None, param_err
            items = params.get("items")
            detail = await WikiPageService.put_footnotes(
                wiki_id,
                expected_revision=expected_revision,
                items=items,
                change_summary=change_summary,
                operator=operator,
            )
            return {"ok": True, "wikiId": detail.id, "revision": detail.revision}, None

        if operation == "put_references":
            param_err = validate_wiki_edit_params(operation, params)
            if param_err:
                return None, param_err
            items = normalize_reference_items(params.get("items") or [])
            detail = await WikiPageService.put_references(
                wiki_id,
                expected_revision=expected_revision,
                items=items,
                change_summary=change_summary,
                operator=operator,
            )
            return {"ok": True, "wikiId": detail.id, "revision": detail.revision}, None

    except WikiRevisionConflictError as exc:
        return None, _format_revision_conflict(exc)
    except WikiError as exc:
        return None, f"[错误] Wiki 编辑失败: {exc.message}"
    except Exception as exc:
        logger.exception(f"apply_wiki_edit 失败: operation={operation} wiki_id={wiki_id}")
        return None, f"[错误] Wiki 编辑失败: {exc}"

    return None, f"[错误] 未处理的 operation: {operation}"
