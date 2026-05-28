from app.models.wiki import (
    WikiContentNodeModel,
    WikiFootnoteModel,
    WikiReferenceModel,
)
from app.service.wiki.wiki_citations import validate_citations


def _tree_with_citation() -> WikiContentNodeModel:
    return WikiContentNodeModel(
        section="main",
        title="",
        content="正文[^1][^a]",
        children=[],
    )


def test_validate_citations_missing():
    health = validate_citations(_tree_with_citation(), [], [])
    assert "1" in health.missing_refs
    assert "a" in health.missing_footnotes


def test_validate_citations_orphan():
    health = validate_citations(
        _tree_with_citation(),
        [WikiFootnoteModel(id="a", text="注")],
        [WikiReferenceModel(id="1", text="ref")],
    )
    assert health.missing_refs == []
    assert health.missing_footnotes == []


def test_orphan_when_not_cited():
    health = validate_citations(
        WikiContentNodeModel(section="main", title="", content="无引用", children=[]),
        [WikiFootnoteModel(id="b", text="注")],
        [WikiReferenceModel(id="9", text="ref")],
    )
    assert "9" in health.orphan_references
    assert "b" in health.orphan_footnotes
