from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field
from pydantic.alias_generators import to_camel

from app.models.wiki import (
    WikiContentNodeModel,
    WikiFootnoteModel,
    WikiInfoboxModel,
    WikiPageModel,
    WikiPageRevisionModel,
    WikiReferenceModel,
)
from app.schemas.constants import WikiPageStatusEnum, WikiRevisionChangeTypeEnum


class WikiSchemaBase(BaseModel):
    model_config = ConfigDict(
        alias_generator=to_camel,
        populate_by_name=True,
        from_attributes=True,
    )


class WikiInfoboxRowSchema(WikiSchemaBase):
    label: str
    value: str


class WikiInfoboxSchema(WikiSchemaBase):
    caption: str | None = None
    series: str | None = None
    image: str | None = None
    rows: list[WikiInfoboxRowSchema] = Field(default_factory=list)


class WikiContentNodeSchema(WikiSchemaBase):
    section: str
    title: str = ""
    content: str = ""
    infobox: WikiInfoboxSchema | None = None
    children: list["WikiContentNodeSchema"] = Field(default_factory=list)


class WikiFootnoteSchema(WikiSchemaBase):
    id: str
    text: str


class WikiReferenceSchema(WikiSchemaBase):
    id: str
    text: str
    url: str | None = None
    entity_type: str | None = None
    entity_uuid: str | None = None


class WikiCitationHealthSchema(WikiSchemaBase):
    missing_refs: list[str] = Field(default_factory=list)
    missing_footnotes: list[str] = Field(default_factory=list)
    orphan_references: list[str] = Field(default_factory=list)
    orphan_footnotes: list[str] = Field(default_factory=list)


class WikiPageSnapshotSchema(WikiSchemaBase):
    title: str
    source_note: str | None = None
    content_tree: WikiContentNodeSchema
    footnotes: list[WikiFootnoteSchema] = Field(default_factory=list)
    references: list[WikiReferenceSchema] = Field(default_factory=list)
    categories: list[str] = Field(default_factory=list)
    status: WikiPageStatusEnum


class WikiPageCreateSchema(WikiSchemaBase):
    title: str = Field(min_length=1)
    source_note: str | None = None
    categories: list[str] = Field(default_factory=list)


class WikiMutateBaseSchema(WikiSchemaBase):
    expected_revision: int = Field(ge=1)
    change_summary: str = ""


class WikiPageMetaPatchSchema(WikiMutateBaseSchema):
    title: str | None = None
    source_note: str | None = None
    categories: list[str] | None = None
    status: WikiPageStatusEnum | None = None


class WikiMainPatchSchema(WikiMutateBaseSchema):
    content: str | None = None
    infobox: WikiInfoboxSchema | None = None


class WikiSectionCreateSchema(WikiMutateBaseSchema):
    parent_section: str = Field(min_length=1)
    title: str = Field(min_length=1)
    after_section: str | None = None


class WikiSectionPatchSchema(WikiMutateBaseSchema):
    title: str | None = None
    content: str | None = None
    infobox: WikiInfoboxSchema | None = None


class WikiSectionMoveSchema(WikiMutateBaseSchema):
    parent_section: str = Field(min_length=1)
    after_section: str | None = None


class WikiFootnotesPutSchema(WikiMutateBaseSchema):
    items: list[WikiFootnoteSchema]


class WikiReferencesPutSchema(WikiMutateBaseSchema):
    items: list[WikiReferenceSchema]


class WikiRestoreSchema(WikiMutateBaseSchema):
    pass


class WikiPageListItemSchema(WikiSchemaBase):
    id: str
    title: str
    source_note: str | None = None
    status: WikiPageStatusEnum
    categories: list[str] = Field(default_factory=list)
    last_modified: datetime
    revision: int
    created_at: datetime


class WikiPageDetailSchema(WikiSchemaBase):
    id: str
    title: str
    source_note: str | None = None
    last_modified: datetime
    revision: int
    status: WikiPageStatusEnum
    content_tree: WikiContentNodeSchema
    footnotes: list[WikiFootnoteSchema] = Field(default_factory=list)
    references: list[WikiReferenceSchema] = Field(default_factory=list)
    categories: list[str] = Field(default_factory=list)
    citation_health: WikiCitationHealthSchema


class WikiRevisionListItemSchema(WikiSchemaBase):
    revision: int
    change_type: WikiRevisionChangeTypeEnum
    target_section: str | None = None
    change_summary: str = ""
    operator: str | None = None
    restored_from_revision: int | None = None
    created_at: datetime


class WikiRevisionDetailSchema(WikiSchemaBase):
    wiki_id: str
    revision: int
    change_type: WikiRevisionChangeTypeEnum
    target_section: str | None = None
    change_summary: str = ""
    operator: str | None = None
    restored_from_revision: int | None = None
    created_at: datetime
    snapshot: WikiPageSnapshotSchema
    citation_health: WikiCitationHealthSchema


WikiTextDiffOp = Literal["equal", "insert", "delete"]
WikiSectionChangeType = Literal["added", "removed", "modified", "moved"]
WikiListItemChangeType = Literal["added", "removed", "modified"]


class WikiTextDiffHunkSchema(WikiSchemaBase):
    op: WikiTextDiffOp
    text: str


class WikiScalarFieldChangeSchema(WikiSchemaBase):
    field: str
    from_value: Any = None
    to_value: Any = None
    hunks: list[WikiTextDiffHunkSchema] | None = None


class WikiCategoriesDiffSchema(WikiSchemaBase):
    added: list[str] = Field(default_factory=list)
    removed: list[str] = Field(default_factory=list)


class WikiSectionDiffSchema(WikiSchemaBase):
    section: str
    change: WikiSectionChangeType
    path_from: list[str] | None = None
    path_to: list[str] | None = None
    title_from: str | None = None
    title_to: str | None = None
    content_hunks: list[WikiTextDiffHunkSchema] | None = None
    infobox_changed: bool = False
    infobox_from: WikiInfoboxSchema | None = None
    infobox_to: WikiInfoboxSchema | None = None


class WikiFootnoteDiffSchema(WikiSchemaBase):
    id: str
    change: WikiListItemChangeType
    from_item: WikiFootnoteSchema | None = None
    to_item: WikiFootnoteSchema | None = None
    text_hunks: list[WikiTextDiffHunkSchema] | None = None


class WikiReferenceDiffSchema(WikiSchemaBase):
    id: str
    change: WikiListItemChangeType
    from_item: WikiReferenceSchema | None = None
    to_item: WikiReferenceSchema | None = None
    text_hunks: list[WikiTextDiffHunkSchema] | None = None


class WikiRevisionDiffSummarySchema(WikiSchemaBase):
    sections_added: int = 0
    sections_removed: int = 0
    sections_modified: int = 0
    sections_moved: int = 0
    footnotes_changed: int = 0
    references_changed: int = 0
    meta_changed: bool = False


class WikiRevisionDiffSchema(WikiSchemaBase):
    wiki_id: str
    from_revision: int
    to_revision: int
    summary: WikiRevisionDiffSummarySchema
    meta: list[WikiScalarFieldChangeSchema] = Field(default_factory=list)
    categories: WikiCategoriesDiffSchema | None = None
    sections: list[WikiSectionDiffSchema] = Field(default_factory=list)
    footnotes: list[WikiFootnoteDiffSchema] = Field(default_factory=list)
    references: list[WikiReferenceDiffSchema] = Field(default_factory=list)


def _health_to_schema(health) -> WikiCitationHealthSchema:
    return WikiCitationHealthSchema.model_validate(health.model_dump())


def _validate_citations(tree, footnotes, references):
    from app.service.wiki.wiki_citations import validate_citations

    return validate_citations(tree, footnotes, references)


def _node_to_schema(node: WikiContentNodeModel) -> WikiContentNodeSchema:
    return WikiContentNodeSchema(
        section=node.section,
        title=node.title,
        content=node.content,
        infobox=(
            WikiInfoboxSchema.model_validate(node.infobox.model_dump())
            if node.infobox
            else None
        ),
        children=[_node_to_schema(c) for c in node.children],
    )


def build_detail_from_parts(
    *,
    wiki_id: str,
    title: str,
    source_note: str | None,
    last_modified: datetime,
    revision: int,
    status: WikiPageStatusEnum,
    content_tree: WikiContentNodeModel,
    footnotes: list[WikiFootnoteModel],
    references: list[WikiReferenceModel],
    categories: list[str],
) -> WikiPageDetailSchema:
    return WikiPageDetailSchema(
        id=wiki_id,
        title=title,
        source_note=source_note,
        last_modified=last_modified,
        revision=revision,
        status=status,
        content_tree=_node_to_schema(content_tree),
        footnotes=[WikiFootnoteSchema.model_validate(f.model_dump()) for f in footnotes],
        references=[
            WikiReferenceSchema.model_validate(r.model_dump()) for r in references
        ],
        categories=list(categories),
        citation_health=_health_to_schema(
            _validate_citations(content_tree, footnotes, references)
        ),
    )


def page_to_list_item(page: WikiPageModel) -> WikiPageListItemSchema:
    return WikiPageListItemSchema(
        id=page.id,
        title=page.title,
        source_note=page.source_note,
        status=page.status,
        categories=list(page.categories),
        last_modified=page.last_modified,
        revision=page.revision,
        created_at=page.created_at,
    )


def revision_to_list_item(rev: WikiPageRevisionModel) -> WikiRevisionListItemSchema:
    return WikiRevisionListItemSchema(
        revision=rev.revision,
        change_type=rev.change_type,
        target_section=rev.target_section,
        change_summary=rev.change_summary,
        operator=rev.operator,
        restored_from_revision=rev.restored_from_revision,
        created_at=rev.created_at,
    )


def revision_to_detail(rev: WikiPageRevisionModel) -> WikiRevisionDetailSchema:
    snap = rev.snapshot
    tree = snap.content_tree
    footnotes = list(snap.footnotes)
    references = list(snap.references)
    return WikiRevisionDetailSchema(
        wiki_id=rev.wiki_id,
        revision=rev.revision,
        change_type=rev.change_type,
        target_section=rev.target_section,
        change_summary=rev.change_summary,
        operator=rev.operator,
        restored_from_revision=rev.restored_from_revision,
        created_at=rev.created_at,
        snapshot=WikiPageSnapshotSchema(
            title=snap.title,
            source_note=snap.source_note,
            content_tree=_node_to_schema(tree),
            footnotes=[WikiFootnoteSchema.model_validate(f.model_dump()) for f in footnotes],
            references=[
                WikiReferenceSchema.model_validate(r.model_dump()) for r in references
            ],
            categories=list(snap.categories),
            status=snap.status,
        ),
        citation_health=_health_to_schema(
            _validate_citations(tree, footnotes, references)
        ),
    )


def schema_infobox_to_model(
    infobox: WikiInfoboxSchema | dict[str, Any] | None,
) -> WikiInfoboxModel | None:
    if infobox is None:
        return None
    if isinstance(infobox, dict):
        return WikiInfoboxModel.model_validate(infobox)
    return WikiInfoboxModel.model_validate(infobox.model_dump())
