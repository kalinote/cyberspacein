from __future__ import annotations

import difflib

from app.models.wiki import (
    WikiContentNodeModel,
    WikiFootnoteModel,
    WikiInfoboxModel,
    WikiPageSnapshotModel,
    WikiReferenceModel,
)
from app.schemas.wiki import (
    WikiCategoriesDiffSchema,
    WikiFootnoteDiffSchema,
    WikiFootnoteSchema,
    WikiInfoboxSchema,
    WikiReferenceDiffSchema,
    WikiReferenceSchema,
    WikiRevisionDiffSchema,
    WikiRevisionDiffSummarySchema,
    WikiScalarFieldChangeSchema,
    WikiSectionDiffSchema,
    WikiTextDiffHunkSchema,
)


def flatten_sections(
    tree: WikiContentNodeModel,
) -> dict[str, tuple[WikiContentNodeModel, list[str]]]:
    result: dict[str, tuple[WikiContentNodeModel, list[str]]] = {}

    def walk(node: WikiContentNodeModel, path: list[str]) -> None:
        result[node.section] = (node, list(path))
        child_path = list(path)
        if node.section != "main" and node.title:
            child_path.append(node.title)
        for child in node.children:
            walk(child, child_path)

    walk(tree, [])
    return result


def diff_text(old: str, new: str) -> list[WikiTextDiffHunkSchema]:
    if old == new:
        return []
    a = old.splitlines(keepends=True)
    b = new.splitlines(keepends=True)
    if not a and not b:
        return []
    hunks: list[WikiTextDiffHunkSchema] = []
    for tag, i1, i2, j1, j2 in difflib.SequenceMatcher(None, a, b).get_opcodes():
        if tag == "equal":
            text = "".join(a[i1:i2])
            if text:
                hunks.append(WikiTextDiffHunkSchema(op="equal", text=text))
        elif tag == "delete":
            text = "".join(a[i1:i2])
            if text:
                hunks.append(WikiTextDiffHunkSchema(op="delete", text=text))
        elif tag == "insert":
            text = "".join(b[j1:j2])
            if text:
                hunks.append(WikiTextDiffHunkSchema(op="insert", text=text))
        elif tag == "replace":
            del_text = "".join(a[i1:i2])
            ins_text = "".join(b[j1:j2])
            if del_text:
                hunks.append(WikiTextDiffHunkSchema(op="delete", text=del_text))
            if ins_text:
                hunks.append(WikiTextDiffHunkSchema(op="insert", text=ins_text))
    return hunks


def _hunks_added(text: str) -> list[WikiTextDiffHunkSchema] | None:
    return diff_text("", text) or None


def _hunks_removed(text: str) -> list[WikiTextDiffHunkSchema] | None:
    return diff_text(text, "") or None


def _infobox_equal(
    a: WikiInfoboxModel | None, b: WikiInfoboxModel | None
) -> bool:
    if a is None and b is None:
        return True
    if a is None or b is None:
        return False
    return a.model_dump() == b.model_dump()


def _infobox_to_schema(box: WikiInfoboxModel | None) -> WikiInfoboxSchema | None:
    if box is None:
        return None
    return WikiInfoboxSchema.model_validate(box.model_dump())


def _node_body_equal(
    a: WikiContentNodeModel, b: WikiContentNodeModel
) -> bool:
    return (
        a.title == b.title
        and a.content == b.content
        and _infobox_equal(a.infobox, b.infobox)
    )


def _diff_meta(
    old: WikiPageSnapshotModel, new: WikiPageSnapshotModel
) -> tuple[list[WikiScalarFieldChangeSchema], WikiCategoriesDiffSchema | None]:
    meta: list[WikiScalarFieldChangeSchema] = []
    if old.title != new.title:
        meta.append(
            WikiScalarFieldChangeSchema(
                field="title",
                from_value=old.title,
                to_value=new.title,
                hunks=diff_text(old.title, new.title) or None,
            )
        )
    if old.source_note != new.source_note:
        meta.append(
            WikiScalarFieldChangeSchema(
                field="sourceNote",
                from_value=old.source_note,
                to_value=new.source_note,
                hunks=diff_text(old.source_note or "", new.source_note or "") or None,
            )
        )
    if old.status != new.status:
        meta.append(
            WikiScalarFieldChangeSchema(
                field="status",
                from_value=old.status.value,
                to_value=new.status.value,
                hunks=None,
            )
        )

    old_cats = set(old.categories)
    new_cats = set(new.categories)
    categories: WikiCategoriesDiffSchema | None = None
    added = sorted(new_cats - old_cats)
    removed = sorted(old_cats - new_cats)
    if added or removed:
        categories = WikiCategoriesDiffSchema(added=added, removed=removed)

    return meta, categories


def _diff_sections(
    old: WikiPageSnapshotModel, new: WikiPageSnapshotModel
) -> list[WikiSectionDiffSchema]:
    old_map = flatten_sections(old.content_tree)
    new_map = flatten_sections(new.content_tree)
    all_ids = set(old_map) | set(new_map)
    diffs: list[WikiSectionDiffSchema] = []

    for section_id in sorted(all_ids):
        old_entry = old_map.get(section_id)
        new_entry = new_map.get(section_id)

        if old_entry is None and new_entry is not None:
            node, path = new_entry
            has_infobox = node.infobox is not None
            diffs.append(
                WikiSectionDiffSchema(
                    section=section_id,
                    change="added",
                    path_to=path,
                    title_to=node.title,
                    content_hunks=_hunks_added(node.content),
                    infobox_changed=has_infobox,
                    infobox_to=_infobox_to_schema(node.infobox)
                    if has_infobox
                    else None,
                )
            )
            continue
        if new_entry is None and old_entry is not None:
            node, path = old_entry
            has_infobox = node.infobox is not None
            diffs.append(
                WikiSectionDiffSchema(
                    section=section_id,
                    change="removed",
                    path_from=path,
                    title_from=node.title,
                    content_hunks=_hunks_removed(node.content),
                    infobox_changed=has_infobox,
                    infobox_from=_infobox_to_schema(node.infobox)
                    if has_infobox
                    else None,
                )
            )
            continue

        old_node, path_from = old_entry  # type: ignore[misc]
        new_node, path_to = new_entry  # type: ignore[misc]
        body_equal = _node_body_equal(old_node, new_node)
        path_equal = path_from == path_to

        if body_equal and not path_equal:
            diffs.append(
                WikiSectionDiffSchema(
                    section=section_id,
                    change="moved",
                    path_from=path_from,
                    path_to=path_to,
                    title_from=old_node.title,
                    title_to=new_node.title,
                )
            )
            continue

        if body_equal:
            continue

        infobox_changed = not _infobox_equal(old_node.infobox, new_node.infobox)
        content_hunks = diff_text(old_node.content, new_node.content) or None
        diffs.append(
            WikiSectionDiffSchema(
                section=section_id,
                change="modified",
                path_from=path_from,
                path_to=path_to,
                title_from=old_node.title,
                title_to=new_node.title,
                content_hunks=content_hunks,
                infobox_changed=infobox_changed,
                infobox_from=_infobox_to_schema(old_node.infobox)
                if infobox_changed
                else None,
                infobox_to=_infobox_to_schema(new_node.infobox)
                if infobox_changed
                else None,
            )
        )

    return diffs


def _footnote_to_schema(item: WikiFootnoteModel) -> WikiFootnoteSchema:
    return WikiFootnoteSchema.model_validate(item.model_dump())


def _reference_to_schema(item: WikiReferenceModel) -> WikiReferenceSchema:
    return WikiReferenceSchema.model_validate(item.model_dump())


def _reference_equal(a: WikiReferenceModel, b: WikiReferenceModel) -> bool:
    return a.model_dump() == b.model_dump()


def _diff_footnotes(
    old: list[WikiFootnoteModel], new: list[WikiFootnoteModel]
) -> list[WikiFootnoteDiffSchema]:
    old_map = {f.id: f for f in old}
    new_map = {f.id: f for f in new}
    diffs: list[WikiFootnoteDiffSchema] = []
    for fid in sorted(set(old_map) | set(new_map)):
        o = old_map.get(fid)
        n = new_map.get(fid)
        if o is None and n is not None:
            diffs.append(
                WikiFootnoteDiffSchema(
                    id=fid,
                    change="added",
                    to_item=_footnote_to_schema(n),
                    text_hunks=_hunks_added(n.text),
                )
            )
        elif n is None and o is not None:
            diffs.append(
                WikiFootnoteDiffSchema(
                    id=fid,
                    change="removed",
                    from_item=_footnote_to_schema(o),
                    text_hunks=_hunks_removed(o.text),
                )
            )
        elif o is not None and n is not None and o.text != n.text:
            diffs.append(
                WikiFootnoteDiffSchema(
                    id=fid,
                    change="modified",
                    from_item=_footnote_to_schema(o),
                    to_item=_footnote_to_schema(n),
                    text_hunks=diff_text(o.text, n.text) or None,
                )
            )
    return diffs


def _diff_references(
    old: list[WikiReferenceModel], new: list[WikiReferenceModel]
) -> list[WikiReferenceDiffSchema]:
    old_map = {r.id: r for r in old}
    new_map = {r.id: r for r in new}
    diffs: list[WikiReferenceDiffSchema] = []
    for rid in sorted(set(old_map) | set(new_map)):
        o = old_map.get(rid)
        n = new_map.get(rid)
        if o is None and n is not None:
            diffs.append(
                WikiReferenceDiffSchema(
                    id=rid,
                    change="added",
                    to_item=_reference_to_schema(n),
                    text_hunks=_hunks_added(n.text),
                )
            )
        elif n is None and o is not None:
            diffs.append(
                WikiReferenceDiffSchema(
                    id=rid,
                    change="removed",
                    from_item=_reference_to_schema(o),
                    text_hunks=_hunks_removed(o.text),
                )
            )
        elif o is not None and n is not None and not _reference_equal(o, n):
            diffs.append(
                WikiReferenceDiffSchema(
                    id=rid,
                    change="modified",
                    from_item=_reference_to_schema(o),
                    to_item=_reference_to_schema(n),
                    text_hunks=diff_text(o.text, n.text) or None,
                )
            )
    return diffs


def build_revision_diff(
    wiki_id: str,
    from_revision: int,
    to_revision: int,
    old: WikiPageSnapshotModel,
    new: WikiPageSnapshotModel,
) -> WikiRevisionDiffSchema:
    meta, categories = _diff_meta(old, new)
    sections = _diff_sections(old, new)
    footnotes = _diff_footnotes(old.footnotes, new.footnotes)
    references = _diff_references(old.references, new.references)

    meta_changed = bool(meta) or categories is not None
    summary = WikiRevisionDiffSummarySchema(
        sections_added=sum(1 for s in sections if s.change == "added"),
        sections_removed=sum(1 for s in sections if s.change == "removed"),
        sections_modified=sum(1 for s in sections if s.change == "modified"),
        sections_moved=sum(1 for s in sections if s.change == "moved"),
        footnotes_changed=len(footnotes),
        references_changed=len(references),
        meta_changed=meta_changed,
    )

    return WikiRevisionDiffSchema(
        wiki_id=wiki_id,
        from_revision=from_revision,
        to_revision=to_revision,
        summary=summary,
        meta=meta,
        categories=categories,
        sections=sections,
        footnotes=footnotes,
        references=references,
    )
