from __future__ import annotations

from datetime import datetime

from loguru import logger

from app.models.wiki import WikiPageModel, WikiPageRevisionModel, WikiPageSnapshotModel
from app.schemas.constants import WikiRevisionChangeTypeEnum
from app.schemas.general import PageResponseSchema
from app.schemas.wiki import WikiRevisionListItemSchema, revision_to_list_item
from app.service.wiki.exceptions import WikiRevisionNotFoundError, WikiSnapshotFailedError
from app.utils.id_lib import generate_id

logger = logger.bind(name=__name__)


class WikiRevisionService:
    @staticmethod
    def build_snapshot(page: WikiPageModel) -> WikiPageSnapshotModel:
        return WikiPageSnapshotModel(
            title=page.title,
            source_note=page.source_note,
            content_tree=page.content_tree.model_copy(deep=True),
            footnotes=[f.model_copy(deep=True) for f in page.footnotes],
            references=[r.model_copy(deep=True) for r in page.references],
            categories=list(page.categories),
            status=page.status,
        )

    @classmethod
    async def append_snapshot(
        cls,
        page: WikiPageModel,
        *,
        change_type: WikiRevisionChangeTypeEnum,
        target_section: str | None = None,
        change_summary: str = "",
        operator: str | None = None,
        restored_from_revision: int | None = None,
    ) -> WikiPageRevisionModel:
        rev = WikiPageRevisionModel(
            id=generate_id(f"wiki_rev:{page.id}:{page.revision}"),
            wiki_id=page.id,
            revision=page.revision,
            snapshot=cls.build_snapshot(page),
            change_type=change_type,
            target_section=target_section,
            change_summary=change_summary or "",
            operator=operator,
            restored_from_revision=restored_from_revision,
            created_at=datetime.now(),
        )
        try:
            await rev.insert()
        except Exception as exc:
            logger.exception(
                f"Wiki 版本快照写入失败: wiki_id={page.id} revision={page.revision} err={exc}"
            )
            raise WikiSnapshotFailedError(f"版本快照写入失败: {exc}") from exc
        return rev

    @classmethod
    async def get_revision(cls, wiki_id: str, revision: int) -> WikiPageRevisionModel:
        rev = await WikiPageRevisionModel.find_one(
            WikiPageRevisionModel.wiki_id == wiki_id,
            WikiPageRevisionModel.revision == revision,
        )
        if rev is None:
            raise WikiRevisionNotFoundError(
                f"历史版本不存在: wiki_id={wiki_id} revision={revision}"
            )
        return rev

    @classmethod
    async def list_revisions(
        cls,
        wiki_id: str,
        page: int,
        page_size: int,
    ) -> PageResponseSchema[WikiRevisionListItemSchema]:
        query = WikiPageRevisionModel.find(
            WikiPageRevisionModel.wiki_id == wiki_id
        ).sort(-WikiPageRevisionModel.revision)
        total = await query.count()
        skip = (page - 1) * page_size
        rows = await query.skip(skip).limit(page_size).to_list()
        items = [revision_to_list_item(r) for r in rows]
        return PageResponseSchema.create(
            items=items, total=total, page=page, page_size=page_size
        )

    @classmethod
    async def delete_all_for_page(cls, wiki_id: str) -> None:
        await WikiPageRevisionModel.find(
            WikiPageRevisionModel.wiki_id == wiki_id
        ).delete()
