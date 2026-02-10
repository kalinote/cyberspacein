from pydantic import BaseModel, Field
from datetime import datetime
from app.schemas.general import PageParamsSchema
from app.schemas.constants import SearchModeEnum


class EntitySearchRequestSchema(PageParamsSchema):
    """
    实体搜索请求参数
    """
    keywords: str | None = Field(default=None, description="关键词搜索，可搜索title(模糊匹配)、clean_content(模糊匹配)、keywords(精确匹配)、author_name(精确匹配)")
    search_mode: SearchModeEnum = Field(default=SearchModeEnum.KEYWORD, description="搜索模式：keyword关键词、vector向量、hybrid融合")
    platform: str | None = Field(default=None, description="平台过滤，精确匹配")
    author: str | None = Field(default=None, description="作者名过滤，精确匹配")
    aigc: bool | None = Field(default=None, description="AIGC内容过滤")
    nsfw: bool | None = Field(default=None, description="NSFW内容过滤")
    is_highlighted: bool | None = Field(default=None, description="重点目标过滤")
    sort_by: str | None = Field(default=None, description="排序字段，可选值：crawled_at、last_edit_at、relevance（相关性）")
    sort_order: str | None = Field(default="desc", description="排序方向，可选值：asc、desc，默认为desc")

class SearchResultSchema(BaseModel):
    """
    搜索结果
    """
    uuid: str = Field(description="UUID")
    entity_type: str = Field(description="实体类型")
    source_id: str = Field(description="来源ID")
    data_version: int = Field(description="数据版本")
    platform: str = Field(description="平台")
    platform_id: str | None = Field(default=None, description="平台ID")
    section: str = Field(description="板块")
    update_at: datetime = Field(description="更新时间")
    author_uuid: str | None = Field(default=None, description="作者UUID")
    author_name: str = Field(description="作者名称")
    nsfw: bool = Field(description="是否为NSFW内容")
    aigc: bool = Field(description="是否为AI生成内容")
    keywords: list[str] = Field(description="关键词")
    title: str = Field(description="标题")
    clean_content: str | None = Field(default=None, description="正文内容")
    confidence: float = Field(default=1, description="置信度")
    is_highlighted: bool | None = Field(default=None, description="是否为重点目标")
    keywords_hits: int = Field(default=0, description="关键词命中次数")