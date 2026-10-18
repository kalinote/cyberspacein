from typing import Any

from pydantic import Field

from app.schemas.general import BaseEntitySchema


class PostSchema(BaseEntitySchema):
    """贴文详情沿用系统实体字段，并保留关系、互动和媒体处理结果。"""

    title: str | None = Field(default=None, description="贴文标题，可为空")
    cover_image: str | None = Field(default=None, description="封面地址")
    post_type: str | None = Field(default=None, description="贴文类型")
    parent_id: str | None = Field(default=None, description="回复或转发的来源贴文 ID")
    mentions: list[str] | None = Field(default=None, description="提及的用户 ID")
    metrics: dict[str, Any] | None = Field(default=None, description="互动指标")
    geo_location: dict[str, Any] | None = Field(default=None, description="地理位置信息")
    ip_location: str | None = Field(default=None, description="IP 属地")
    media_resources: list[dict[str, Any] | str] | None = Field(default=None, description="结构化媒体及归档结果，空数组表示无媒体")
    files_urls: list[str] | None = Field(default=None, description="兼容媒体地址清单")
    media_summary: dict[str, Any] | None = Field(default=None, description="媒体处理统计")
