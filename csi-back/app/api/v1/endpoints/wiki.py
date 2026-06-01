from typing import Any

from fastapi import APIRouter, Path, Query
from loguru import logger

from app.models.wiki import WikiFootnoteModel, WikiReferenceModel
from app.schemas.constants import WikiPageStatusEnum
from app.schemas.general import PageResponseSchema
from app.schemas.response import ApiResponseSchema
from app.schemas.wiki import (
    WikiFootnotesPutSchema,
    WikiMainPatchSchema,
    WikiPageCreateSchema,
    WikiPageDetailSchema,
    WikiPageListItemSchema,
    WikiPageMetaPatchSchema,
    WikiReferencesPutSchema,
    WikiRestoreSchema,
    WikiRevisionDetailSchema,
    WikiRevisionDiffSchema,
    WikiRevisionListItemSchema,
    WikiSectionCreateSchema,
    WikiSectionMoveSchema,
    WikiSectionPatchSchema,
    WikiCitationHealthSchema,
)
from app.service.wiki.exceptions import WikiError
from app.service.wiki.wiki_page_service import WikiPageService

logger = logger.bind(name=__name__)

router = APIRouter(prefix="/wiki", tags=["Wiki"])


def _wiki_error(exc: WikiError) -> ApiResponseSchema:
    return ApiResponseSchema.error(code=exc.code, message=exc.message)


@router.get(
    "/pages",
    response_model=PageResponseSchema[WikiPageListItemSchema],
    summary="Wiki 分页列表与搜索",
)
async def list_wiki_pages(
    q: str | None = Query(default=None, description="搜索关键词"),
    category: str | None = Query(default=None, description="分类标签"),
    status: WikiPageStatusEnum | None = Query(default=None, description="状态"),
    sort_by: str = Query(default="updated_at", description="排序字段"),
    sort_order: str = Query(default="desc", description="排序方向"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=10, ge=1, le=100),
):
    try:
        return await WikiPageService.list_pages(
            q=q,
            category=category,
            status=status,
            sort_by=sort_by,
            sort_order=sort_order,
            page=page,
            page_size=page_size,
        )
    except WikiError as exc:
        return _wiki_error(exc)
    except Exception as exc:
        logger.exception(f"Wiki 列表查询失败: {exc}")
        return ApiResponseSchema.error(code=241000, message=f"Wiki 列表查询失败: {exc}")


@router.post(
    "/pages",
    response_model=ApiResponseSchema[WikiPageDetailSchema],
    summary="创建 Wiki 页",
)
async def create_wiki_page(data: WikiPageCreateSchema):
    try:
        detail = await WikiPageService.create_page(
            title=data.title,
            source_note=data.source_note,
            categories=data.categories,
        )
        return ApiResponseSchema.success(data=detail)
    except WikiError as exc:
        return _wiki_error(exc)
    except Exception as exc:
        logger.exception(f"创建 Wiki 页失败: {exc}")
        return ApiResponseSchema.error(code=241000, message=f"创建 Wiki 页失败: {exc}")


@router.get(
    "/pages/{wiki_id}",
    response_model=ApiResponseSchema[WikiPageDetailSchema],
    summary="获取 Wiki 页详情",
)
async def get_wiki_page(wiki_id: str = Path(..., description="Wiki 页 ID（32 位 hex）")):
    try:
        detail = await WikiPageService.get_page(wiki_id)
        return ApiResponseSchema.success(data=detail)
    except WikiError as exc:
        return _wiki_error(exc)


@router.patch(
    "/pages/{wiki_id}/meta",
    response_model=ApiResponseSchema[WikiPageDetailSchema],
    summary="更新 Wiki 元数据",
)
async def patch_wiki_meta(
    wiki_id: str,
    data: WikiPageMetaPatchSchema,
):
    try:
        detail = await WikiPageService.patch_meta(
            wiki_id,
            expected_revision=data.expected_revision,
            change_summary=data.change_summary,
            title=data.title,
            source_note=data.source_note,
            categories=data.categories,
            status=data.status,
        )
        return ApiResponseSchema.success(data=detail)
    except WikiError as exc:
        return _wiki_error(exc)


@router.delete(
    "/pages/{wiki_id}",
    response_model=ApiResponseSchema[None],
    summary="删除整个 Wiki 页",
)
async def delete_wiki_page(wiki_id: str = Path(..., description="页面 ID")):
    try:
        await WikiPageService.delete_page(wiki_id)
        return ApiResponseSchema.success(data=None)
    except WikiError as exc:
        return _wiki_error(exc)


@router.patch(
    "/pages/{wiki_id}/main",
    response_model=ApiResponseSchema[WikiPageDetailSchema],
    summary="更新导语区 main",
)
async def patch_wiki_main(wiki_id: str, data: WikiMainPatchSchema):
    try:
        infobox_set = "infobox" in data.model_fields_set
        detail = await WikiPageService.patch_main(
            wiki_id,
            expected_revision=data.expected_revision,
            change_summary=data.change_summary,
            content=data.content,
            infobox=data.infobox,
            infobox_set=infobox_set,
        )
        return ApiResponseSchema.success(data=detail)
    except WikiError as exc:
        return _wiki_error(exc)


@router.post(
    "/pages/{wiki_id}/sections",
    response_model=ApiResponseSchema[dict[str, Any]],
    summary="新增章节",
)
async def create_wiki_section(wiki_id: str, data: WikiSectionCreateSchema):
    try:
        detail, section = await WikiPageService.add_section(
            wiki_id,
            expected_revision=data.expected_revision,
            parent_section=data.parent_section,
            title=data.title,
            after_section=data.after_section,
            change_summary=data.change_summary,
        )
        return ApiResponseSchema.success(
            data={"section": section, "detail": detail.model_dump(by_alias=True)}
        )
    except WikiError as exc:
        return _wiki_error(exc)


@router.patch(
    "/pages/{wiki_id}/sections/{section_id}",
    response_model=ApiResponseSchema[WikiPageDetailSchema],
    summary="更新章节",
)
async def patch_wiki_section(
    wiki_id: str,
    section_id: str,
    data: WikiSectionPatchSchema,
):
    try:
        infobox_set = "infobox" in data.model_fields_set
        detail = await WikiPageService.patch_section(
            wiki_id,
            section_id,
            expected_revision=data.expected_revision,
            change_summary=data.change_summary,
            title=data.title,
            content=data.content,
            infobox=data.infobox,
            infobox_set=infobox_set,
        )
        return ApiResponseSchema.success(data=detail)
    except WikiError as exc:
        return _wiki_error(exc)


@router.patch(
    "/pages/{wiki_id}/sections/{section_id}/move",
    response_model=ApiResponseSchema[WikiPageDetailSchema],
    summary="移动章节",
)
async def move_wiki_section(
    wiki_id: str,
    section_id: str,
    data: WikiSectionMoveSchema,
):
    try:
        detail = await WikiPageService.move_section(
            wiki_id,
            section_id,
            expected_revision=data.expected_revision,
            parent_section=data.parent_section,
            after_section=data.after_section,
            change_summary=data.change_summary,
        )
        return ApiResponseSchema.success(data=detail)
    except WikiError as exc:
        return _wiki_error(exc)


@router.delete(
    "/pages/{wiki_id}/sections/{section_id}",
    response_model=ApiResponseSchema[WikiPageDetailSchema],
    summary="删除章节",
)
async def delete_wiki_section(
    wiki_id: str,
    section_id: str,
    expected_revision: int = Query(
        ...,
        ge=1,
        alias="expectedRevision",
        description="当前修订号",
    ),
    change_summary: str = Query(
        default="",
        alias="changeSummary",
        description="变更说明",
    ),
):
    try:
        detail = await WikiPageService.delete_section(
            wiki_id,
            section_id,
            expected_revision=expected_revision,
            change_summary=change_summary,
        )
        return ApiResponseSchema.success(data=detail)
    except WikiError as exc:
        return _wiki_error(exc)


@router.put(
    "/pages/{wiki_id}/footnotes",
    response_model=ApiResponseSchema[WikiPageDetailSchema],
    summary="替换脚注列表",
)
async def put_wiki_footnotes(wiki_id: str, data: WikiFootnotesPutSchema):
    try:
        items = [WikiFootnoteModel.model_validate(i.model_dump()) for i in data.items]
        detail = await WikiPageService.put_footnotes(
            wiki_id,
            expected_revision=data.expected_revision,
            items=items,
            change_summary=data.change_summary,
        )
        return ApiResponseSchema.success(data=detail)
    except WikiError as exc:
        return _wiki_error(exc)


@router.put(
    "/pages/{wiki_id}/references",
    response_model=ApiResponseSchema[WikiPageDetailSchema],
    summary="替换参考文献列表",
)
async def put_wiki_references(wiki_id: str, data: WikiReferencesPutSchema):
    try:
        items = [WikiReferenceModel.model_validate(i.model_dump()) for i in data.items]
        detail = await WikiPageService.put_references(
            wiki_id,
            expected_revision=data.expected_revision,
            items=items,
            change_summary=data.change_summary,
        )
        return ApiResponseSchema.success(data=detail)
    except WikiError as exc:
        return _wiki_error(exc)


@router.get(
    "/pages/{wiki_id}/citations/validate",
    response_model=ApiResponseSchema[WikiCitationHealthSchema],
    summary="校验引用与脚注",
)
async def validate_wiki_citations(wiki_id: str):
    try:
        health = await WikiPageService.validate_citations_only(wiki_id)
        return ApiResponseSchema.success(data=health)
    except WikiError as exc:
        return _wiki_error(exc)


@router.get(
    "/pages/{wiki_id}/revisions",
    response_model=PageResponseSchema[WikiRevisionListItemSchema],
    summary="版本历史列表",
)
async def list_wiki_revisions(
    wiki_id: str,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
):
    try:
        return await WikiPageService.list_revisions(wiki_id, page, page_size)
    except WikiError as exc:
        return _wiki_error(exc)


@router.get(
    "/pages/{wiki_id}/revisions/diff",
    response_model=ApiResponseSchema[WikiRevisionDiffSchema],
    summary="对比两个历史版本差异",
)
async def diff_wiki_revisions(
    wiki_id: str = Path(..., description="Wiki 页 ID（32 位 hex）"),
    from_revision: int = Query(
        ...,
        ge=1,
        alias="from",
        description="基线修订号",
    ),
    to_revision: int = Query(
        ...,
        ge=1,
        alias="to",
        description="目标修订号",
    ),
):
    try:
        diff = await WikiPageService.diff_revisions(
            wiki_id, from_revision, to_revision
        )
        return ApiResponseSchema.success(data=diff)
    except WikiError as exc:
        return _wiki_error(exc)


@router.get(
    "/pages/{wiki_id}/revisions/{revision}",
    response_model=ApiResponseSchema[WikiRevisionDetailSchema],
    summary="回放指定版本",
)
async def get_wiki_revision(
    wiki_id: str,
    revision: int = Path(..., ge=1),
):
    try:
        detail = await WikiPageService.get_revision_detail(wiki_id, revision)
        return ApiResponseSchema.success(data=detail)
    except WikiError as exc:
        return _wiki_error(exc)


@router.post(
    "/pages/{wiki_id}/revisions/{revision}/restore",
    response_model=ApiResponseSchema[WikiPageDetailSchema],
    summary="恢复到指定版本",
)
async def restore_wiki_revision(
    wiki_id: str,
    revision: int,
    data: WikiRestoreSchema,
):
    try:
        detail = await WikiPageService.restore_revision(
            wiki_id,
            revision,
            expected_revision=data.expected_revision,
            change_summary=data.change_summary,
        )
        return ApiResponseSchema.success(data=detail)
    except WikiError as exc:
        return _wiki_error(exc)
