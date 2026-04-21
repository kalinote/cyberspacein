"""app.schemas.annotation 批注 Schema 测试。"""

from app.schemas.annotation import AnnotationCreateSchema, AnnotationTargetSchema, TextOffsetSchema
from app.schemas.constants import AnnotationStyleEnum, AnnotationTypeEnum, ContentRegionEnum


def test_annotation_create_defaults():
    # 创建批注时类型、样式与 meta 的默认值
    t = AnnotationCreateSchema(
        entity_uuid="e1",
        entity_type="article",
        target=AnnotationTargetSchema(
            region=ContentRegionEnum.CLEAN,
            text_offset=TextOffsetSchema(start=0, end=1, text="x"),
        ),
    )
    assert t.annotation_type == AnnotationTypeEnum.TEXT
    assert t.style == AnnotationStyleEnum.HIGHLIGHT
    assert t.meta == {}
