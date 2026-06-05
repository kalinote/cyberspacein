from __future__ import annotations

import re
from typing import TYPE_CHECKING

from pydantic import BaseModel, Field

if TYPE_CHECKING:
    from app.models.wiki import (
        WikiContentNodeModel,
        WikiFootnoteModel,
        WikiReferenceModel,
    )

_CITATION_RE = re.compile(r"\[\^([0-9]+|[a-zA-Z]+)\]")


class CitationHealthResult(BaseModel):
    missing_refs: list[str] = Field(default_factory=list)
    missing_footnotes: list[str] = Field(default_factory=list)
    orphan_references: list[str] = Field(default_factory=list)
    orphan_footnotes: list[str] = Field(default_factory=list)


def _flatten_contents(node: "WikiContentNodeModel") -> list[str]:
    parts = [node.content]
    for child in node.children:
        parts.extend(_flatten_contents(child))
    return parts


def _extract_citations(contents: list[str]) -> tuple[set[str], set[str]]:
    refs: set[str] = set()
    notes: set[str] = set()
    for text in contents:
        for match in _CITATION_RE.finditer(text or ""):
            token = match.group(1)
            if token.isdigit():
                refs.add(token)
            else:
                notes.add(token)
    return refs, notes


def validate_citations(
    tree: "WikiContentNodeModel",
    footnotes: list["WikiFootnoteModel"],
    references: list["WikiReferenceModel"],
) -> CitationHealthResult:
    contents = _flatten_contents(tree)
    cited_refs, cited_notes = _extract_citations(contents)

    ref_ids = {r.id for r in references}
    note_ids = {f.id for f in footnotes}

    missing_refs = sorted(cited_refs - ref_ids, key=lambda x: int(x) if x.isdigit() else x)
    missing_footnotes = sorted(cited_notes - note_ids)
    orphan_references = sorted(ref_ids - cited_refs, key=lambda x: int(x) if x.isdigit() else x)
    orphan_footnotes = sorted(note_ids - cited_notes)

    return CitationHealthResult(
        missing_refs=missing_refs,
        missing_footnotes=missing_footnotes,
        orphan_references=orphan_references,
        orphan_footnotes=orphan_footnotes,
    )
