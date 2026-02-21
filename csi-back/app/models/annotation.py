from datetime import datetime
from beanie import Document
from pydantic import BaseModel, Field

from app.schemas.constants import AnnotationTypeEnum, AnnotationStyleEnum, ContentRegionEnum


class TextOffsetModel(BaseModel):
    """文本偏移量定位"""
    start: int = Field(description="字符起始偏移量")
    end: int = Field(description="字符结束偏移量")
    text: str = Field(description="选中文本快照，用于内容变更后的重定位校验")


class AnnotationTargetModel(BaseModel):
    """批注定位信息"""
    region: ContentRegionEnum = Field(description="内容区域")
    text_offset: TextOffsetModel = Field(description="文本偏移量")


class AnnotationModel(Document):
    """内容批注"""
    id: str = Field(alias="_id")
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
    target: AnnotationTargetModel = Field(description="定位信息")
    meta: dict = Field(default_factory=dict, description="扩展元数据，类型相关的额外信息")
    operator: str | None = Field(default=None, description="操作者")
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)

    class Settings:
        name = "annotations"
        indexes = [
            [("entity_uuid", 1), ("entity_type", 1)],
        ]
