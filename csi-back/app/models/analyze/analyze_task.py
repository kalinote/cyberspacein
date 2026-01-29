from datetime import datetime
from typing import Any

from beanie import Document
from pydantic import Field
from pymongo import IndexModel


class AnalyzeTaskModel(Document):
    entity_type: str = Field(description="实体类型 article/forum")
    uuid: str = Field(description="实体 UUID")
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)
    steps: dict[str, Any] = Field(default_factory=dict, description="大步骤聚合，如 content_analysis")

    class Settings:
        name = "analyze_tasks"
        indexes = [
            IndexModel([("entity_type", 1), ("uuid", 1)], unique=True),
        ]
