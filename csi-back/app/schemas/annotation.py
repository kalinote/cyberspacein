from datetime import datetime
from typing import Any
from pydantic import BaseModel, ConfigDict, Field

from app.schemas.constants import AnnotationTypeEnum, AnnotationStyleEnum, ContentRegionEnum


class TextOffsetSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    start: int = Field(description="字符起始偏移量")
    end: int = Field(description="字符结束偏移量")
    text: str = Field(description="选中文本快照")


class AnnotationTargetSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    region: ContentRegionEnum = Field(description="内容区域")
    text_offset: TextOffsetSchema = Field(description="文本偏移量")


class AnnotationCreateSchema(BaseModel):
    """
    创建批注请求
    """
    entity_uuid: str = Field(description="被批注实体的 UUID")
    entity_type: str = Field(description="实体类型，如 article / forum")
    annotation_type: AnnotationTypeEnum = Field(
        default=AnnotationTypeEnum.TEXT,
        description="批注类型"
    )
    style: AnnotationStyleEnum = Field(
        default=AnnotationStyleEnum.HIGHLIGHT,
        description="批注样式"
    )
    content: str = Field(default="", description="批注正文")
    target: AnnotationTargetSchema = Field(description="定位信息")
    meta: dict[str, Any] = Field(default_factory=dict, description="扩展元数据")


class AnnotationUpdateSchema(BaseModel):
    """
    更新批注请求
    """
    content: str | None = Field(default=None, description="批注正文")
    meta: dict[str, Any] | None = Field(default=None, description="扩展元数据")


class AnnotationSchema(BaseModel):
    """
    批注响应
    """
    model_config = ConfigDict(from_attributes=True)

    id: str = Field(description="批注 ID")
    entity_uuid: str = Field(description="被批注实体的 UUID")
    entity_type: str = Field(description="实体类型")
    annotation_type: AnnotationTypeEnum = Field(description="批注类型")
    style: AnnotationStyleEnum = Field(description="批注样式")
    content: str = Field(description="批注正文")
    target: AnnotationTargetSchema = Field(description="定位信息")
    meta: dict[str, Any] = Field(description="扩展元数据")
    operator: str | None = Field(description="操作者")
    created_at: datetime = Field(description="创建时间")
    updated_at: datetime = Field(description="更新时间")
