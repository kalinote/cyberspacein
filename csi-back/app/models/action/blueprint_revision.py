from datetime import datetime
from typing import Any, Literal

from beanie import Document
from pydantic import Field
from pymongo import ASCENDING, IndexModel

from app.models.action.blueprint import ActionBlueprintSnapshotModel, GraphModel
from app.schemas.action.interface import BlueprintInterfaceSpec


class ActionBlueprintRevisionModel(Document):
    """保存发布后不可变的蓝图版本。"""

    id: str = Field(alias="_id")
    blueprint_id: str
    version: str
    revision_number: int = Field(ge=1)
    graph_snapshot: GraphModel
    blueprint_snapshot: ActionBlueprintSnapshotModel
    definition_snapshots: dict[str, dict[str, Any]]
    execution_specs_snapshot: dict[str, Any]
    interface_snapshot: BlueprintInterfaceSpec = Field(default_factory=BlueprintInterfaceSpec)
    template_snapshot: dict[str, Any] | None = None
    dependency_snapshot: list[str] = Field(default_factory=list)
    runtime_contract_version: Literal[2]
    reference_protocol_version: Literal["eos-v1"]
    content_hash: str
    published_at: datetime = Field(default_factory=datetime.now)
    published_by: str | None = None
    is_active: bool = True

    class Settings:
        name = "action_blueprint_revisions"
        indexes = [
            IndexModel(
                [("blueprint_id", ASCENDING), ("revision_number", ASCENDING)],
                unique=True,
            ),
            IndexModel([("content_hash", ASCENDING)]),
            "blueprint_id",
        ]
