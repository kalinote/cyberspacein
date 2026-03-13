import logging
import uuid
from datetime import datetime
from fastapi import APIRouter, Path, Query

from app.models.annotation import AnnotationModel, AnnotationTargetModel, TextOffsetModel
from app.schemas.annotation import (
    AnnotationCreateSchema,
    AnnotationSchema,
    AnnotationUpdateSchema,
)
from app.schemas.response import ApiResponseSchema

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/annotation",
    tags=["批注"],
)


@router.get("/list", response_model=ApiResponseSchema[list[AnnotationSchema]], summary="获取批注列表")
async def list_annotations(
    entity_uuid: str = Query(..., description="实体 UUID"),
    entity_type: str = Query(..., description="实体类型，如 article / forum"),
):
    annotations = await AnnotationModel.find(
        AnnotationModel.entity_uuid == entity_uuid,
        AnnotationModel.entity_type == entity_type,
    ).sort(AnnotationModel.created_at).to_list()

    result = [AnnotationSchema.from_doc(a) for a in annotations]
    return ApiResponseSchema.success(data=result)


@router.post("", response_model=ApiResponseSchema[AnnotationSchema], summary="创建批注")
async def create_annotation(data: AnnotationCreateSchema):
    annotation = AnnotationModel(
        id=str(uuid.uuid4()),
        entity_uuid=data.entity_uuid,
        entity_type=data.entity_type,
        annotation_type=data.annotation_type,
        style=data.style,
        content=data.content,
        target=AnnotationTargetModel(
            region=data.target.region,
            text_offset=TextOffsetModel(
                start=data.target.text_offset.start,
                end=data.target.text_offset.end,
                text=data.target.text_offset.text,
            ),
        ),
        meta=data.meta,
    )
    await annotation.insert()

    return ApiResponseSchema.success(data=AnnotationSchema.from_doc(annotation))


@router.put("/{annotation_id}", response_model=ApiResponseSchema[AnnotationSchema], summary="更新批注")
async def update_annotation(
    annotation_id: str = Path(..., description="批注 ID"),
    data: AnnotationUpdateSchema = ...,
):
    annotation = await AnnotationModel.find_one({"_id": annotation_id})
    if not annotation:
        return ApiResponseSchema.error(code=404, message=f"批注不存在，ID: {annotation_id}")

    if data.content is not None:
        annotation.content = data.content
    if data.meta is not None:
        annotation.meta = data.meta
    annotation.updated_at = datetime.now()

    await annotation.save()
    return ApiResponseSchema.success(data=AnnotationSchema.from_doc(annotation))


@router.delete("/{annotation_id}", response_model=ApiResponseSchema[None], summary="删除批注")
async def delete_annotation(
    annotation_id: str = Path(..., description="批注 ID"),
):
    annotation = await AnnotationModel.find_one({"_id": annotation_id})
    if not annotation:
        return ApiResponseSchema.error(code=404, message=f"批注不存在，ID: {annotation_id}")

    await annotation.delete()
    return ApiResponseSchema.success()
