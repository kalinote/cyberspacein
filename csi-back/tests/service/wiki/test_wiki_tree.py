import pytest

from app.models.wiki import WikiContentNodeModel
from app.service.wiki.exceptions import WikiCannotDeleteMainError, WikiSectionNotFoundError
from app.service.wiki.wiki_tree import (
    add_child,
    assert_unique_sections,
    build_search_blob,
    empty_main_tree,
    find_node,
    move_node,
    remove_subtree,
    update_node_fields,
)


def _tree() -> WikiContentNodeModel:
    root = empty_main_tree()
    a = add_child(root, "page-1", "main", "一级", after_section=None)
    add_child(root, "page-1", a.section, "二级", after_section=None)
    return root


def test_empty_main_tree():
    root = empty_main_tree()
    assert root.section == "main"
    assert root.title == ""
    assert root.children == []


def test_add_child_and_find():
    root = _tree()
    child_sections = [c.section for c in root.children]
    assert len(child_sections) == 1
    node, parent, _ = find_node(root, child_sections[0])
    assert node.title == "一级"
    assert parent is root


def test_nested_add_five_levels():
    root = empty_main_tree()
    parent = "main"
    last_section = "main"
    for i in range(5):
        node = add_child(root, "p1", parent, f"层{i}", after_section=None)
        last_section = node.section
        parent = last_section
    node, _, _ = find_node(root, last_section)
    assert node.title == "层4"


def test_remove_subtree_forbidden_main():
    root = empty_main_tree()
    with pytest.raises(WikiCannotDeleteMainError):
        remove_subtree(root, "main")


def test_move_node():
    root = _tree()
    level1 = root.children[0]
    sub = add_child(root, "page-1", level1.section, "子节", after_section=None)
    move_node(root, sub.section, "main", after_section=None)
    assert any(c.section == sub.section for c in root.children)


def test_update_node_fields():
    root = empty_main_tree()
    update_node_fields(root, "main", content="导语", title="")
    assert root.content == "导语"


def test_build_search_blob_includes_title_and_content():
    root = empty_main_tree()
    root.content = "hello"
    blob = build_search_blob("标题", root)
    assert "标题" in blob
    assert "hello" in blob


def test_unique_sections():
    root = empty_main_tree()
    assert_unique_sections(root)
    with pytest.raises(WikiSectionNotFoundError):
        find_node(root, "missing-id")
