from datetime import datetime
from pydantic import BaseModel, Field
from app.schemas.constants import EntityType

class TimelineDiffCompareResponseSchema(BaseModel):
    raw_content: str = Field(description="原始内容，用于变更对比")
    last_edit_at: datetime | None = Field(default=None, description="最后编辑时间")
    title: str = Field(default="", description="标题")


class TimelineResponseSchema(BaseModel):
    uuid: str = Field(description="UUID")
    entity_type: EntityType = Field(description="实体类型")
    source_id: str = Field(description="来源ID")
    last_edit_at: datetime = Field(description="最后编辑时间")
    crawled_at: datetime = Field(description="爬取时间")
    title: str = Field(description="标题")
    clean_content: str | None = Field(default=None, description="正文内容")
    confidence: float | None = Field(default=None, description="置信度")
    is_highlighted: bool | None = Field(default=None, description="是否为重点目标")
    highlight_reason: str | None = Field(default=None, description="标记理由")
