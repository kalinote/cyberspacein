from datetime import datetime
from typing import Any

from beanie import Document
from pydantic import Field


class SearchTemplateModel(Document):
    id: str = Field(alias="_id")
    title: str = Field(description="模板标题")
    description: str = Field(description="模板描述")
    search_query: str = Field(description="检索关键词/查询")
    rules: dict[str, Any] = Field(default_factory=dict, description="检索规则，格式可扩展")
    created_at: datetime = Field(default_factory=datetime.now, description="创建时间")
    updated_at: datetime = Field(default_factory=datetime.now, description="更新时间")

    class Settings:
        name = "search_templates"
        indexes = ["title"]
