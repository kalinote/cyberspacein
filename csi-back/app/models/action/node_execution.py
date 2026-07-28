from datetime import datetime
from typing import Any

from beanie import Document
from pydantic import Field
from pymongo import ASCENDING, IndexModel

from app.schemas.constants import ActionInstanceNodeStatusEnum


class ActionNodeExecutionModel(Document):
    """记录所有实际发起的节点执行尝试。"""

    id: str = Field(alias="_id")
    action_id: str
    node_instance_id: str
    execution_key: str = "default"
    driver: str
    handler: str
    schema_version: int = 1
    extension_contract_version: int | None = None
    attempt: int = 1
    status: ActionInstanceNodeStatusEnum = ActionInstanceNodeStatusEnum.QUEUED
    idempotency_key: str
    provider_run_id: str | None = None
    provider_session_id: str | None = None
    child_action_id: str | None = None
    progress: float = 0
    timeout_seconds: int = Field(default=0, ge=0)
    deadline_at: datetime | None = None
    outputs: dict[str, Any] = Field(default_factory=dict)
    extension_state: dict[str, Any] = Field(default_factory=dict)
    extension_result: dict[str, Any] = Field(default_factory=dict)
    error_message: str | None = None
    started_at: datetime | None = None
    finished_at: datetime | None = None
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)

    class Settings:
        name = "action_node_executions"
        indexes = [
            IndexModel(
                [
                    ("action_id", ASCENDING),
                    ("node_instance_id", ASCENDING),
                    ("execution_key", ASCENDING),
                    ("attempt", ASCENDING),
                ],
                unique=True,
            ),
            IndexModel([("idempotency_key", ASCENDING)], unique=True),
            IndexModel([("action_id", ASCENDING), ("status", ASCENDING)]),
            "provider_run_id",
            "child_action_id",
        ]
