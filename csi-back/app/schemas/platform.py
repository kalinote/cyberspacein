from datetime import datetime
from typing import TYPE_CHECKING

from pydantic import BaseModel, Field, field_validator
from urllib.parse import urlparse

if TYPE_CHECKING:
    from app.models.platform.platform import PlatformModel


class PlatformCreateRequestSchema(BaseModel):
    """
    创建平台请求
    """
    name: str = Field(description="平台名称", min_length=1, max_length=100)
    description: str = Field(description="平台描述", default="")
    type: str = Field(description="平台类型", min_length=1)
    net_type: str = Field(default="明网", description="网络类型(Tor/明网)", min_length=1)
    status: str = Field(description="平台状态", default="活跃")
    url: str = Field(description="平台URL")
    logo: str | None = Field(default=None, description="平台Logo（可选），不传或为空则不抓取")
    tags: list[str] = Field(description="平台标签", default_factory=list)
    category: str = Field(description="平台分类，表示站点类型", min_length=1)
    sub_category: str = Field(description="平台子分类，概况站点内容", min_length=1)
    confidence: float = Field(default=1, description="平台信任度")
    # TODO: 可能需要改成list
    spider_name: str | None = Field(default=None, description="爬虫名称")
    sections: list[str] = Field(description="平台板块", default_factory=list)
    
    @field_validator("url")
    @classmethod
    def validate_url(cls, v: str) -> str:
        if not v:
            raise ValueError("URL不能为空")
        parsed = urlparse(v)
        if not parsed.scheme or not parsed.netloc:
            raise ValueError("URL格式不正确，必须包含协议和域名")
        return v


class PlatformFilterItemSchema(BaseModel):
    """
    平台过滤器项
    """
    id: str = Field(description="平台ID")
    name: str = Field(description="平台名称")

    @classmethod
    def from_doc(cls, doc: "PlatformModel") -> "PlatformFilterItemSchema":
        return cls(id=doc.id, name=doc.name)


class PlatformBaseInfoSchema(BaseModel):
    """
    平台基本信息
    """
    id: str = Field(description="平台ID")
    name: str = Field(description="平台名称")
    description: str = Field(description="平台描述")
    type: str = Field(description="平台类型")
    net_type: str = Field(description="网络类型(Tor/明网)")
    status: str = Field(description="平台状态")
    created_at: datetime = Field(description="平台创建时间")
    updated_at: datetime = Field(description="平台更新时间")
    url: str = Field(description="平台URL")
    logo: str = Field(description="平台Logo")
    tags: list[str] = Field(description="平台标签")
    category: str = Field(description="平台分类")
    sub_category: str = Field(description="平台子分类")
    confidence: float = Field(description="平台信任度")
    spider_name: str | None = Field(default=None, description="爬虫名称")
    sections: list[str] = Field(description="平台板块")

    @classmethod
    def from_doc(cls, doc: "PlatformModel") -> "PlatformBaseInfoSchema":
        return cls(
            id=doc.id,
            name=doc.name,
            description=doc.description,
            type=doc.type,
            net_type=doc.net_type,
            status=doc.status,
            created_at=doc.created_at,
            updated_at=doc.updated_at,
            url=doc.url,
            logo=doc.logo,
            tags=doc.tags,
            category=doc.category,
            sub_category=doc.sub_category,
            confidence=doc.confidence,
            spider_name=doc.spider_name,
            sections=doc.sections,
        )