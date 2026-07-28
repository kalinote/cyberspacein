from datetime import datetime
from typing import Any

from beanie import Document
from pydantic import Field
from pymongo import ASCENDING, IndexModel


class RuntimeDomainEventModel(Document):
    """保存跨运行时消费者可重复处理的持久化领域事件。"""

    id: str = Field(alias="_id")
    topic: str
    aggregate_type: str
    aggregate_id: str
    payload: dict[str, Any] = Field(default_factory=dict)
    processed_by: list[str] = Field(default_factory=list)
    occurred_at: datetime = Field(default_factory=datetime.now)
    created_at: datetime = Field(default_factory=datetime.now)

    class Settings:
        name = "runtime_domain_events"
        indexes = [
            IndexModel(
                [
                    ("topic", ASCENDING),
                    ("processed_by", ASCENDING),
                    ("occurred_at", ASCENDING),
                ]
            ),
            IndexModel(
                [
                    ("aggregate_type", ASCENDING),
                    ("aggregate_id", ASCENDING),
                ]
            ),
        ]
