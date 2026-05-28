from __future__ import annotations

import re
from datetime import datetime
from typing import Any
from uuid import uuid4

from app.models.wiki import (
    WikiContentNodeModel,
    WikiFootnoteModel,
    WikiPageModel,
    WikiReferenceModel,
)
from app.schemas.constants import WikiPageStatusEnum, WikiRevisionChangeTypeEnum
from app.schemas.general import PageResponseSchema
from app.schemas.wiki import (
    WikiCitationHealthSchema,
    WikiPageDetailSchema,
    WikiPageListItemSchema,
    WikiRevisionDetailSchema,
    build_detail_from_parts,
    page_to_list_item,
    revision_to_detail,
    schema_infobox_to_model,
)
from app.service.wiki.exceptions import (
    WikiPageNotFoundError,
    WikiRevisionConflictError,
    WikiSlugConflictError,
    WikiSnapshotFailedError,
)
from app.service.wiki.wiki_citations import validate_citations
from app.service.wiki.wiki_revision_service import WikiRevisionService
from app.service.wiki.wiki_tree import (
    add_child,
    build_search_blob,
    empty_main_tree,
    move_node,
    remove_subtree,
    update_node_fields,
)

_SLUG_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")


class WikiPageService:
    @staticmethod
    def _validate_slug(slug: str) -> None:
        if not _SLUG_RE.fullmatch(slug) or not (2 <= len(slug) <= 128):
            raise WikiSlugConflictError("slug 格式非法")

    @classmethod
    async def _get_page_or_404(cls, page_id: str) -> WikiPageModel:
        page = await WikiPageModel.find_one(WikiPageModel.id == page_id)
        if page is None:
            raise WikiPageNotFoundError(f"Wiki 页不存在: {page_id}")
        return page

    @classmethod
    def _check_revision(cls, page: WikiPageModel, expected_revision: int) -> None:
        if page.revision != expected_revision:
            raise WikiRevisionConflictError(
                f"修订号冲突：当前 {page.revision}，提交 {expected_revision}"
            )

    @classmethod
    def _to_detail(cls, page: WikiPageModel) -> WikiPageDetailSchema:
        return build_detail_from_parts(
            page_id=page.id,
            slug=page.slug,
            title=page.title,
            source_note=page.source_note,
            last_modified=page.last_modified,
            revision=page.revision,
            status=page.status,
            content_tree=page.content_tree,
            footnotes=page.footnotes,
            references=page.references,
            categories=page.categories,
        )

    @classmethod
    async def _save_with_revision(
        cls,
        page: WikiPageModel,
        *,
        change_type: WikiRevisionChangeTypeEnum,
        target_section: str | None = None,
        change_summary: str = "",
        restored_from_revision: int | None = None,
    ) -> WikiPageModel:
        page.search_blob = build_search_blob(page.title, page.content_tree)
        page.revision += 1
        now = datetime.now()
        page.last_modified = now
        page.updated_at = now
        await page.save()
        try:
            await WikiRevisionService.append_snapshot(
                page,
                change_type=change_type,
                target_section=target_section,
                change_summary=change_summary,
                restored_from_revision=restored_from_revision,
            )
        except WikiSnapshotFailedError:
            page.revision -= 1
            page.updated_at = datetime.now()
            await page.save()
            raise
        return page

    @classmethod
    async def create_page(
        cls,
        *,
        slug: str,
        title: str,
        source_note: str | None = None,
        categories: list[str] | None = None,
    ) -> WikiPageDetailSchema:
        cls._validate_slug(slug)
        existing = await WikiPageModel.find_one(WikiPageModel.slug == slug)
        if existing is not None:
            raise WikiSlugConflictError(f"slug 已存在: {slug}")

        now = datetime.now()
        page = WikiPageModel(
            id=str(uuid4()),
            slug=slug,
            title=title,
            source_note=source_note,
            content_tree=empty_main_tree(),
            footnotes=[],
            references=[],
            categories=list(categories or []),
            status=WikiPageStatusEnum.DRAFT,
            revision=1,
            search_blob="",
            created_by=None,
            last_modified=now,
            created_at=now,
            updated_at=now,
        )
        page.search_blob = build_search_blob(page.title, page.content_tree)
        await page.insert()
        await WikiRevisionService.append_snapshot(
            page,
            change_type=WikiRevisionChangeTypeEnum.CREATE,
        )
        return cls._to_detail(page)

    @classmethod
    async def get_page_by_id(cls, page_id: str) -> WikiPageDetailSchema:
        page = await cls._get_page_or_404(page_id)
        return cls._to_detail(page)

    @classmethod
    async def get_page_by_slug(cls, slug: str) -> WikiPageDetailSchema:
        page = await WikiPageModel.find_one(WikiPageModel.slug == slug)
        if page is None:
            raise WikiPageNotFoundError(f"Wiki 页不存在: slug={slug}")
        return cls._to_detail(page)

    @classmethod
    async def list_pages(
        cls,
        *,
        q: str | None = None,
        category: str | None = None,
        status: WikiPageStatusEnum | None = None,
        sort_by: str = "updated_at",
        sort_order: str = "desc",
        page: int = 1,
        page_size: int = 10,
    ) -> PageResponseSchema[WikiPageListItemSchema]:
        filters: list[Any] = []
        if status is not None:
            filters.append(WikiPageModel.status == status)
        if category:
            filters.append(WikiPageModel.categories == category)

        sort_field = sort_by if sort_by in ("updated_at", "created_at", "title") else "updated_at"
        direction = -1 if sort_order.lower() != "asc" else 1

        if q and q.strip():
            text_query = WikiPageModel.find(
                {"$text": {"$search": q.strip()}},
                *filters,
            )
            total = await text_query.count()
            if total == 0:
                pattern = re.compile(re.escape(q.strip()), re.IGNORECASE)
                regex_filters = [
                    *filters,
                    {
                        "$or": [
                            {"title": pattern},
                            {"slug": pattern},
                        ]
                    },
                ]
                query = WikiPageModel.find(*regex_filters)
                total = await query.count()
                skip = (page - 1) * page_size
                rows = (
                    await query.sort([(sort_field, direction)])
                    .skip(skip)
                    .limit(page_size)
                    .to_list()
                )
            else:
                skip = (page - 1) * page_size
                rows = (
                    await text_query.sort([(sort_field, direction)])
                    .skip(skip)
                    .limit(page_size)
                    .to_list()
                )
        else:
            query = WikiPageModel.find(*filters) if filters else WikiPageModel.find_all()
            total = await query.count()
            skip = (page - 1) * page_size
            rows = (
                await query.sort([(sort_field, direction)])
                .skip(skip)
                .limit(page_size)
                .to_list()
            )

        items = [page_to_list_item(p) for p in rows]
        return PageResponseSchema.create(
            items=items, total=total, page=page, page_size=page_size
        )

    @classmethod
    async def delete_page(cls, page_id: str) -> None:
        page = await cls._get_page_or_404(page_id)
        await WikiRevisionService.delete_all_for_page(page.id)
        await page.delete()

    @classmethod
    async def patch_meta(
        cls,
        page_id: str,
        *,
        expected_revision: int,
        change_summary: str = "",
        title: str | None = None,
        source_note: str | None = None,
        categories: list[str] | None = None,
        status: WikiPageStatusEnum | None = None,
    ) -> WikiPageDetailSchema:
        page = await cls._get_page_or_404(page_id)
        cls._check_revision(page, expected_revision)
        if title is not None:
            page.title = title
        if source_note is not None:
            page.source_note = source_note
        if categories is not None:
            page.categories = categories
        if status is not None:
            page.status = status
        page = await cls._save_with_revision(
            page,
            change_type=WikiRevisionChangeTypeEnum.META,
            change_summary=change_summary,
        )
        return cls._to_detail(page)

    @classmethod
    async def patch_main(
        cls,
        page_id: str,
        *,
        expected_revision: int,
        change_summary: str = "",
        content: str | None = None,
        infobox: Any = None,
        infobox_set: bool = False,
    ) -> WikiPageDetailSchema:
        page = await cls._get_page_or_404(page_id)
        cls._check_revision(page, expected_revision)
        if content is not None:
            page.content_tree.content = content
        if infobox_set:
            page.content_tree.infobox = schema_infobox_to_model(infobox)
        page = await cls._save_with_revision(
            page,
            change_type=WikiRevisionChangeTypeEnum.MAIN,
            target_section="main",
            change_summary=change_summary,
        )
        return cls._to_detail(page)

    @classmethod
    async def add_section(
        cls,
        page_id: str,
        *,
        expected_revision: int,
        parent_section: str,
        title: str,
        after_section: str | None = None,
        change_summary: str = "",
    ) -> tuple[WikiPageDetailSchema, str]:
        page = await cls._get_page_or_404(page_id)
        cls._check_revision(page, expected_revision)
        node = add_child(
            page.content_tree,
            page.id,
            parent_section,
            title,
            after_section=after_section,
        )
        page = await cls._save_with_revision(
            page,
            change_type=WikiRevisionChangeTypeEnum.STRUCTURE,
            target_section=node.section,
            change_summary=change_summary,
        )
        return cls._to_detail(page), node.section

    @classmethod
    async def patch_section(
        cls,
        page_id: str,
        section_id: str,
        *,
        expected_revision: int,
        change_summary: str = "",
        title: str | None = None,
        content: str | None = None,
        infobox: Any = None,
        infobox_set: bool = False,
    ) -> WikiPageDetailSchema:
        page = await cls._get_page_or_404(page_id)
        cls._check_revision(page, expected_revision)
        update_node_fields(
            page.content_tree,
            section_id,
            title=title,
            content=content,
            infobox=schema_infobox_to_model(infobox) if infobox_set else None,
            infobox_set=infobox_set,
        )
        page = await cls._save_with_revision(
            page,
            change_type=WikiRevisionChangeTypeEnum.SECTION,
            target_section=section_id,
            change_summary=change_summary,
        )
        return cls._to_detail(page)

    @classmethod
    async def move_section(
        cls,
        page_id: str,
        section_id: str,
        *,
        expected_revision: int,
        parent_section: str,
        after_section: str | None = None,
        change_summary: str = "",
    ) -> WikiPageDetailSchema:
        page = await cls._get_page_or_404(page_id)
        cls._check_revision(page, expected_revision)
        move_node(
            page.content_tree,
            section_id,
            parent_section,
            after_section=after_section,
        )
        page = await cls._save_with_revision(
            page,
            change_type=WikiRevisionChangeTypeEnum.STRUCTURE,
            target_section=section_id,
            change_summary=change_summary,
        )
        return cls._to_detail(page)

    @classmethod
    async def delete_section(
        cls,
        page_id: str,
        section_id: str,
        *,
        expected_revision: int,
        change_summary: str = "",
    ) -> WikiPageDetailSchema:
        page = await cls._get_page_or_404(page_id)
        cls._check_revision(page, expected_revision)
        remove_subtree(page.content_tree, section_id)
        page = await cls._save_with_revision(
            page,
            change_type=WikiRevisionChangeTypeEnum.STRUCTURE,
            target_section=section_id,
            change_summary=change_summary,
        )
        return cls._to_detail(page)

    @classmethod
    async def put_footnotes(
        cls,
        page_id: str,
        *,
        expected_revision: int,
        items: list[WikiFootnoteModel] | list[dict[str, Any]],
        change_summary: str = "",
    ) -> WikiPageDetailSchema:
        page = await cls._get_page_or_404(page_id)
        cls._check_revision(page, expected_revision)
        page.footnotes = [
            i if isinstance(i, WikiFootnoteModel) else WikiFootnoteModel(**i)
            for i in items
        ]
        page = await cls._save_with_revision(
            page,
            change_type=WikiRevisionChangeTypeEnum.FOOTNOTES,
            change_summary=change_summary,
        )
        return cls._to_detail(page)

    @classmethod
    async def put_references(
        cls,
        page_id: str,
        *,
        expected_revision: int,
        items: list[WikiReferenceModel] | list[dict[str, Any]],
        change_summary: str = "",
    ) -> WikiPageDetailSchema:
        page = await cls._get_page_or_404(page_id)
        cls._check_revision(page, expected_revision)
        page.references = [
            i if isinstance(i, WikiReferenceModel) else WikiReferenceModel(**i)
            for i in items
        ]
        page = await cls._save_with_revision(
            page,
            change_type=WikiRevisionChangeTypeEnum.REFERENCES,
            change_summary=change_summary,
        )
        return cls._to_detail(page)

    @classmethod
    async def validate_citations_only(cls, page_id: str) -> WikiCitationHealthSchema:
        page = await cls._get_page_or_404(page_id)
        health = validate_citations(
            page.content_tree, page.footnotes, page.references
        )
        return WikiCitationHealthSchema.model_validate(health.model_dump())

    @classmethod
    async def get_revision_detail(
        cls, page_id: str, revision: int
    ) -> WikiRevisionDetailSchema:
        await cls._get_page_or_404(page_id)
        rev = await WikiRevisionService.get_revision(page_id, revision)
        return revision_to_detail(rev)

    @classmethod
    async def list_revisions(
        cls, page_id: str, page: int, page_size: int
    ) -> PageResponseSchema:
        await cls._get_page_or_404(page_id)
        return await WikiRevisionService.list_revisions(page_id, page, page_size)

    @classmethod
    async def restore_revision(
        cls,
        page_id: str,
        target_revision: int,
        *,
        expected_revision: int,
        change_summary: str = "",
    ) -> WikiPageDetailSchema:
        page = await cls._get_page_or_404(page_id)
        cls._check_revision(page, expected_revision)
        rev = await WikiRevisionService.get_revision(page_id, target_revision)
        snap = rev.snapshot
        page.slug = snap.slug
        page.title = snap.title
        page.source_note = snap.source_note
        page.content_tree = snap.content_tree.model_copy(deep=True)
        page.footnotes = [f.model_copy(deep=True) for f in snap.footnotes]
        page.references = [r.model_copy(deep=True) for r in snap.references]
        page.categories = list(snap.categories)
        page.status = snap.status
        page = await cls._save_with_revision(
            page,
            change_type=WikiRevisionChangeTypeEnum.RESTORE,
            change_summary=change_summary,
            restored_from_revision=target_revision,
        )
        return cls._to_detail(page)
