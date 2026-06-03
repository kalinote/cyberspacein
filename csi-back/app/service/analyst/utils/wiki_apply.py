"""Wiki 写操作：审批通过后调用 WikiPageService。"""
from __future__ import annotations

from typing import Any

from loguru import logger

from app.schemas.constants import WikiPageStatusEnum
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


def _format_revision_conflict(exc: WikiRevisionConflictError) -> str:
    return (
        f"[错误] 修订号冲突（241003）：{exc.message}。"
        "请使用 wiki_read 获取最新 revision 后重新发起编辑。"
    )


def _operator_label(agent_id: str | None) -> str | None:
    if not agent_id:
        return None
    return f"agent:{agent_id}"


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
            items = params.get("items")
            if not isinstance(items, list):
                return None, "[错误] put_footnotes 需要 items 数组"
            detail = await WikiPageService.put_footnotes(
                wiki_id,
                expected_revision=expected_revision,
                items=items,
                change_summary=change_summary,
                operator=operator,
            )
            return {"ok": True, "wikiId": detail.id, "revision": detail.revision}, None

        if operation == "put_references":
            items = params.get("items")
            if not isinstance(items, list):
                return None, "[错误] put_references 需要 items 数组"
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
