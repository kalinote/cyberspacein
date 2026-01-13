from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, Field


class BaseEntitySchema(BaseModel):
    uuid: str = Field(description="主键。md5(entity_type + source_id + last_edit_at + raw_content)。用于去重或版本控制。")
    source_id: Optional[str] = Field(default=None, description="平台原本的ID（如推文ID、文章ID）")
    data_version: Optional[int] = Field(default=None, description="数据版本号，用于追踪后续可能出现的字段更新")
    entity_type: Optional[str] = Field(default=None, description="实体类型，该字段主要用于各中间件分类")
    url: Optional[str] = Field(default=None, description="原始链接")
    tags: Optional[List[str]] = Field(default=None, description="从原文内容中提取出的标签（如 #AI）")
    platform: Optional[str] = Field(default=None, description="来源平台 (twitter, weibo, bbc, etc.)")
    section: Optional[str] = Field(default=None, description="所属板块")
    spider_name: Optional[str] = Field(default=None, description="爬虫名称")
    update_at: Optional[datetime] = Field(default=None, description="最后一次存入数据库时间")
    crawled_at: Optional[datetime] = Field(default=None, description="采集入库的时间")
    publish_at: Optional[datetime] = Field(default=None, description="内容在平台上发布的实际时间（不同于采集时间）")
    last_edit_at: Optional[datetime] = Field(default=None, description="内容最后编辑时间（不同于发表时间）")
    language: Optional[str] = Field(default=None, description="语种 (zh-CN, en-US)，用于分词器选择和过滤")
    author_id: Optional[str] = Field(default=None, description="作者在原平台的唯一ID")
    author_name: Optional[str] = Field(default=None, description="作者昵称")
    nsfw: Optional[bool] = Field(default=None, description="是否为NSFW内容")
    aigc: Optional[bool] = Field(default=None, description="是否为AI生成内容")
    translation_content: Optional[str] = Field(default=None, description="基于 clean_content 翻译到中文的内容")
    keywords: Optional[List[str]] = Field(default=None, description="基于内容分析得到的关键词列表")
    emotion: Optional[float] = Field(default=None, description="基于内容分析的情感分数，从-1(消极)到1(积极)")
    political_bias: Optional[List[str]] = Field(default=None, description="基于内容分析的政治倾向")
    confidence: Optional[float] = Field(default=None, description="内容置信度，范围-1,0-1，其中0-1为有效值，-1为零信任模式")
    subjective_rating: Optional[int] = Field(default=None, description="主观评分，仅能由用户设置")


class ArticleSchema(BaseEntitySchema):
    title: Optional[str] = Field(default=None, description="标题")
    clean_content: Optional[str] = Field(default=None, description="正文内容")
    raw_content: Optional[str] = Field(default=None, description="原始JSON或HTML")
    safe_raw_content: Optional[str] = Field(default=None, description="经过处理js和css后的安全网页内容，用于前端页面还原展示")
    cover_image: Optional[str] = Field(default=None, description="封面图/缩略图 URL")
    likes: Optional[int] = Field(default=None, description="点赞数")
