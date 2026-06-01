from __future__ import annotations

from app.models.wiki import (
    WikiContentNodeModel,
    WikiFootnoteModel,
    WikiInfoboxModel,
    WikiInfoboxRowModel,
    WikiPageSnapshotModel,
    WikiReferenceModel,
)
from app.schemas.constants import WikiPageStatusEnum
from app.service.wiki.wiki_revision_diff import (
    build_revision_diff,
    diff_text,
    flatten_sections,
)


def _snapshot(
    *,
    title: str = "页",
    tree: WikiContentNodeModel | None = None,
    footnotes: list[WikiFootnoteModel] | None = None,
    references: list[WikiReferenceModel] | None = None,
    categories: list[str] | None = None,
) -> WikiPageSnapshotModel:
    return WikiPageSnapshotModel(
        title=title,
        source_note=None,
        content_tree=tree
        or WikiContentNodeModel(section="main", title="", content="导语", children=[]),
        footnotes=footnotes or [],
        references=references or [],
        categories=categories or [],
        status=WikiPageStatusEnum.PUBLISHED,
    )


def test_diff_text_insert_delete() -> None:
    hunks = diff_text("a\n", "b\n")
    ops = [h.op for h in hunks]
    assert "delete" in ops
    assert "insert" in ops


def test_diff_same_revision_empty() -> None:
    snap = _snapshot()
    diff = build_revision_diff("w" * 32, 1, 1, snap, snap)
    assert diff.summary.sections_added == 0
    assert diff.summary.meta_changed is False
    assert diff.meta == []
    assert diff.sections == []


def test_diff_meta_title_change() -> None:
    old = _snapshot(title="旧标题")
    new = _snapshot(title="新标题")
    diff = build_revision_diff("w" * 32, 1, 2, old, new)
    assert diff.summary.meta_changed is True
    assert len(diff.meta) == 1
    assert diff.meta[0].field == "title"
    assert diff.meta[0].from_value == "旧标题"
    assert diff.meta[0].to_value == "新标题"
    assert diff.meta[0].hunks is not None


def test_diff_categories() -> None:
    old = _snapshot(categories=["a"])
    new = _snapshot(categories=["a", "b"])
    diff = build_revision_diff("w" * 32, 1, 2, old, new)
    assert diff.categories is not None
    assert diff.categories.added == ["b"]
    assert diff.categories.removed == []


def test_diff_section_added_removed_modified() -> None:
    old_tree = WikiContentNodeModel(
        section="main",
        title="",
        content="",
        children=[
            WikiContentNodeModel(
                section="sec-a", title="A", content="旧正文", children=[]
            ),
        ],
    )
    new_tree = WikiContentNodeModel(
        section="main",
        title="",
        content="",
        children=[
            WikiContentNodeModel(
                section="sec-a", title="A", content="新正文", children=[]
            ),
            WikiContentNodeModel(
                section="sec-b", title="B", content="", children=[]
            ),
        ],
    )
    old = _snapshot(tree=old_tree)
    new = _snapshot(tree=new_tree)
    diff = build_revision_diff("w" * 32, 1, 2, old, new)
    changes = {s.section: s.change for s in diff.sections}
    assert changes["sec-a"] == "modified"
    assert changes["sec-b"] == "added"
    assert diff.summary.sections_modified == 1
    assert diff.summary.sections_added == 1


def test_diff_section_moved() -> None:
    node = WikiContentNodeModel(
        section="sec-x", title="X", content="同内容", children=[]
    )
    old_tree = WikiContentNodeModel(
        section="main",
        title="",
        content="",
        children=[
            WikiContentNodeModel(
                section="parent-a", title="父A", content="", children=[node.model_copy(deep=True)]
            ),
        ],
    )
    new_tree = WikiContentNodeModel(
        section="main",
        title="",
        content="",
        children=[
            WikiContentNodeModel(
                section="parent-b", title="父B", content="", children=[node.model_copy(deep=True)]
            ),
        ],
    )
    old = _snapshot(tree=old_tree)
    new = _snapshot(tree=new_tree)
    diff = build_revision_diff("w" * 32, 1, 2, old, new)
    moved = [s for s in diff.sections if s.section == "sec-x"]
    assert len(moved) == 1
    assert moved[0].change == "moved"
    assert moved[0].path_from == ["父A"]
    assert moved[0].path_to == ["父B"]


def test_diff_footnote_modified() -> None:
    old = _snapshot(footnotes=[WikiFootnoteModel(id="a", text="旧")])
    new = _snapshot(footnotes=[WikiFootnoteModel(id="a", text="新")])
    diff = build_revision_diff("w" * 32, 1, 2, old, new)
    assert len(diff.footnotes) == 1
    assert diff.footnotes[0].change == "modified"
    assert diff.footnotes[0].text_hunks is not None


def test_diff_section_added_has_insert_hunks() -> None:
    new_tree = WikiContentNodeModel(
        section="main",
        title="",
        content="",
        children=[
            WikiContentNodeModel(
                section="sec-new",
                title="新章",
                content="新增正文\n第二行",
                children=[],
            ),
        ],
    )
    old = _snapshot(
        tree=WikiContentNodeModel(section="main", title="", content="", children=[])
    )
    new = _snapshot(tree=new_tree)
    diff = build_revision_diff("w" * 32, 1, 2, old, new)
    added = diff.sections[0]
    assert added.change == "added"
    assert added.content_hunks is not None
    assert all(h.op == "insert" for h in added.content_hunks)
    assert "新增正文" in "".join(h.text for h in added.content_hunks)


def test_diff_section_removed_has_delete_hunks() -> None:
    old_tree = WikiContentNodeModel(
        section="main",
        title="",
        content="",
        children=[
            WikiContentNodeModel(
                section="sec-old",
                title="旧章",
                content="待删内容",
                children=[],
            ),
        ],
    )
    old = _snapshot(tree=old_tree)
    new = _snapshot(
        tree=WikiContentNodeModel(section="main", title="", content="", children=[])
    )
    diff = build_revision_diff("w" * 32, 1, 2, old, new)
    removed = diff.sections[0]
    assert removed.change == "removed"
    assert removed.content_hunks is not None
    assert all(h.op == "delete" for h in removed.content_hunks)
    assert "待删内容" in "".join(h.text for h in removed.content_hunks)


def test_diff_section_added_with_infobox() -> None:
    box = WikiInfoboxModel(caption="信息", series="系列", rows=[WikiInfoboxRowModel(label="k", value="v")])
    new_tree = WikiContentNodeModel(
        section="main",
        title="",
        content="",
        children=[
            WikiContentNodeModel(
                section="sec-i",
                title="节",
                content="",
                infobox=box,
                children=[],
            ),
        ],
    )
    old = _snapshot(
        tree=WikiContentNodeModel(section="main", title="", content="", children=[])
    )
    new = _snapshot(tree=new_tree)
    diff = build_revision_diff("w" * 32, 1, 2, old, new)
    sec = diff.sections[0]
    assert sec.infobox_changed is True
    assert sec.infobox_to is not None
    assert sec.infobox_from is None


def test_diff_footnote_added_has_text_hunks() -> None:
    old = _snapshot()
    new = _snapshot(footnotes=[WikiFootnoteModel(id="a", text="新脚注")])
    diff = build_revision_diff("w" * 32, 1, 2, old, new)
    fn = diff.footnotes[0]
    assert fn.change == "added"
    assert fn.to_item is not None
    assert fn.text_hunks is not None
    assert all(h.op == "insert" for h in fn.text_hunks)


def test_flatten_sections_paths() -> None:
    tree = WikiContentNodeModel(
        section="main",
        title="",
        content="",
        children=[
            WikiContentNodeModel(
                section="c1",
                title="章一",
                content="",
                children=[
                    WikiContentNodeModel(
                        section="c2", title="节二", content="", children=[]
                    ),
                ],
            ),
        ],
    )
    flat = flatten_sections(tree)
    assert flat["c2"][1] == ["章一"]
