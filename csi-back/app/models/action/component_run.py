from datetime import datetime
from typing import Any

from beanie import Document
from pydantic import Field
from pymongo import ASCENDING, IndexModel

from app.schemas.constants import ComponentRunStatusEnum


class ComponentRunModel(Document):
    id: str = Field(alias="_id")
    action_id: str
    node_instance_id: str
    component_id: str
    attempt: int = 1
    timeout_seconds: int = 0
    status: ComponentRunStatusEnum = ComponentRunStatusEnum.CREATED
    dispatch_ref: str | None = None
    platform_task_id: str | None = None
    progress: float = 0
    last_heartbeat_at: datetime | None = None
    lease_expires_at: datetime | None = None
    started_at: datetime | None = None
    finished_at: datetime | None = None
    exit_code: int | None = None
    error_message: str | None = None
    result_id: str | None = None
    outputs: dict[str, Any] = Field(default_factory=dict)
    cancel_requested: bool = False
    log_count: int = 0
    error_log_count: int = 0
    dropped_log_count: int = 0
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)

    class Settings:
        name = "component_runs"
        indexes = [
            IndexModel(
                [("node_instance_id", ASCENDING), ("component_id", ASCENDING), ("attempt", ASCENDING)],
                unique=True,
            ),
            IndexModel(
                [("result_id", ASCENDING)],
                unique=True,
                partialFilterExpression={"result_id": {"$type": "string"}},
            ),
            "action_id",
            "node_instance_id",
            "status",
        ]
