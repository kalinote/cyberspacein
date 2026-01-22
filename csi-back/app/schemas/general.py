from typing import Generic, TypeVar, Any
from datetime import datetime
from pydantic import BaseModel, Field

T = TypeVar('T')


class DictModelSchema(BaseModel):
    key: str
    value: Any


class PageParamsSchema(BaseModel):
    page: int = Field(default=1, ge=1, description="页码，从1开始")
    page_size: int = Field(default=10, ge=1, le=100, description="每页数量，最大100")


class PageResponseSchema(BaseModel, Generic[T]):
    total: int = Field(description="总记录数")
    page: int = Field(description="当前页码")
    page_size: int = Field(description="每页数量")
    total_pages: int = Field(description="总页数")
    items: list[T] = Field(description="数据列表")

    @classmethod
    def create(cls, items: list[T], total: int, page: int, page_size: int) -> "PageResponseSchema[T]":
        total_pages = (total + page_size - 1) // page_size if total > 0 else 0
        return cls(
            total=total,
            page=page,
            page_size=page_size,
            total_pages=total_pages,
            items=items
        )

class BaseEntitySchema(BaseModel):
    uuid: str = Field(description="主键。md5(entity_type + source_id + last_edit_at + raw_content)。用于去重或版本控制。")
    source_id: str | None = Field(default=None, description="平台原本的ID（如推文ID、文章ID）")
    data_version: int | None = Field(default=None, description="数据版本号，用于追踪后续可能出现的字段更新")
    entity_type: str = Field(default=None, description="实体类型，该字段主要用于各中间件分类")
    url: str | None = Field(default=None, description="原始链接")
    tags: list[str] | None = Field(default=None, description="从原文内容中提取出的标签（如 #AI）")
    platform: str | None = Field(default=None, description="来源平台 (twitter, weibo, bbc, etc.)")
    section: str | None = Field(default=None, description="所属板块")
    spider_name: str | None = Field(default=None, description="爬虫名称")
    update_at: datetime | None = Field(default=None, description="最后一次存入数据库时间")
    crawled_at: datetime | None = Field(default=None, description="采集入库的时间")
    publish_at: datetime | None = Field(default=None, description="内容在平台上发布的实际时间（不同于采集时间）")
    last_edit_at: datetime | None = Field(default=None, description="内容最后编辑时间（不同于发表时间）")
    language: str | None = Field(default=None, description="语种 (zh-CN, en-US)，用于分词器选择和过滤")
    author_id: str | None = Field(default=None, description="作者在原平台的唯一ID")
    author_name: str | None = Field(default=None, description="作者昵称")
    nsfw: bool | None = Field(default=None, description="是否为NSFW内容")
    aigc: bool | None = Field(default=None, description="是否为AI生成内容")
    translation_content: str | None = Field(default=None, description="基于 clean_content 翻译到中文的内容")
    keywords: list[str] | None = Field(default=None, description="基于内容分析得到的关键词列表")
    emotion: float | None = Field(default=None, description="基于内容分析的情感分数，从-1(消极)到1(积极)")
    political_bias: list[str] | None = Field(default=None, description="基于内容分析的政治倾向")
    confidence: float | None = Field(default=None, description="内容置信度，范围-1,0-1，其中0-1为有效值，-1为零信任模式")
    subjective_rating: int | None = Field(default=None, description="主观评分，仅能由用户设置")
    clean_content: str | None = Field(default=None, description="正文内容")
    raw_content: str | None = Field(default=None, description="原始JSON或HTML")
    safe_raw_content: str | None = Field(default=None, description="经过处理js和css后的安全网页内容，用于前端页面还原展示")
    is_highlighted: bool = Field(default=False, description="是否为重点目标")
    highlighted_at: datetime | None = Field(default=None, description="标记时间")
    highlight_reason: str | None = Field(default=None, description="标记理由")
    