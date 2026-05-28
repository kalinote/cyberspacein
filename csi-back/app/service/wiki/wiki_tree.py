from __future__ import annotations

from copy import deepcopy
from typing import Any

from app.models.wiki import WikiContentNodeModel, WikiInfoboxModel
from app.service.wiki.exceptions import WikiCannotDeleteMainError, WikiSectionNotFoundError
from app.service.wiki.section_id import new_section_id


def collect_section_ids(node: WikiContentNodeModel) -> list[str]:
    ids = [node.section]
    for child in node.children:
        ids.extend(collect_section_ids(child))
    return ids


def assert_unique_sections(tree: WikiContentNodeModel) -> None:
    ids = collect_section_ids(tree)
    if len(ids) != len(set(ids)):
        raise ValueError("章节 section 存在重复")


def empty_main_tree() -> WikiContentNodeModel:
    return WikiContentNodeModel(
        section="main",
        title="",
        content="",
        infobox=None,
        children=[],
    )


def find_node(
    tree: WikiContentNodeModel, section_id: str
) -> tuple[WikiContentNodeModel, WikiContentNodeModel | None, int]:
    if tree.section == section_id:
        return tree, None, -1

    def _walk(
        parent: WikiContentNodeModel,
    ) -> tuple[WikiContentNodeModel, WikiContentNodeModel, int] | None:
        for idx, child in enumerate(parent.children):
            if child.section == section_id:
                return child, parent, idx
            found = _walk(child)
            if found is not None:
                return found
        return None

    result = _walk(tree)
    if result is None:
        raise WikiSectionNotFoundError(f"章节不存在: {section_id}")
    return result


def _insert_after(
    siblings: list[WikiContentNodeModel],
    new_node: WikiContentNodeModel,
    after_section: str | None,
) -> None:
    if not after_section:
        siblings.append(new_node)
        return
    for i, sib in enumerate(siblings):
        if sib.section == after_section:
            siblings.insert(i + 1, new_node)
            return
    raise WikiSectionNotFoundError(f"参考章节不存在: {after_section}")


def add_child(
    tree: WikiContentNodeModel,
    page_id: str,
    parent_section: str,
    title: str,
    *,
    after_section: str | None = None,
) -> WikiContentNodeModel:
    parent, _, _ = find_node(tree, parent_section)
    node = WikiContentNodeModel(
        section=new_section_id(page_id),
        title=title,
        content="",
        infobox=None,
        children=[],
    )
    _insert_after(parent.children, node, after_section)
    assert_unique_sections(tree)
    return node


def remove_subtree(tree: WikiContentNodeModel, section_id: str) -> None:
    if section_id == "main":
        raise WikiCannotDeleteMainError("不能删除根节点 main")
    node, parent, index = find_node(tree, section_id)
    if parent is None:
        raise WikiCannotDeleteMainError("不能删除根节点 main")
    parent.children.pop(index)
    assert_unique_sections(tree)


def move_node(
    tree: WikiContentNodeModel,
    section_id: str,
    new_parent_section: str,
    *,
    after_section: str | None = None,
) -> None:
    if section_id == "main":
        raise WikiSectionNotFoundError("不能移动根节点 main")
    node, parent, index = find_node(tree, section_id)
    if parent is None:
        raise WikiSectionNotFoundError("不能移动根节点 main")
    if new_parent_section == section_id:
        raise WikiSectionNotFoundError("不能将章节移动到自身之下")

    detached = parent.children.pop(index)
    new_parent, _, _ = find_node(tree, new_parent_section)

    def _is_descendant(ancestor: WikiContentNodeModel, target_id: str) -> bool:
        for child in ancestor.children:
            if child.section == target_id:
                return True
            if _is_descendant(child, target_id):
                return True
        return False

    if _is_descendant(detached, new_parent_section):
        parent.children.insert(index, detached)
        raise WikiSectionNotFoundError("不能将章节移动到其子孙节点之下")

    _insert_after(new_parent.children, detached, after_section)
    assert_unique_sections(tree)


def update_node_fields(
    tree: WikiContentNodeModel,
    section_id: str,
    *,
    title: str | None = None,
    content: str | None = None,
    infobox: WikiInfoboxModel | None = None,
    infobox_set: bool = False,
) -> WikiContentNodeModel:
    node, _, _ = find_node(tree, section_id)
    if title is not None:
        node.title = title
    if content is not None:
        node.content = content
    if infobox_set:
        node.infobox = infobox
    return node


def flatten_contents(node: WikiContentNodeModel) -> list[str]:
    parts = [node.content]
    for child in node.children:
        parts.extend(flatten_contents(child))
    return parts


def build_search_blob(title: str, tree: WikiContentNodeModel) -> str:
    parts = [title, *flatten_contents(tree)]
    return "\n".join(p for p in parts if p)
