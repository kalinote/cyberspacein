from datetime import datetime, timezone

from beanie import Document
from pydantic import Field
from pymongo import ASCENDING, DESCENDING, IndexModel

from app.schemas.evidence import EvidenceGraph


class EvidenceChainModel(Document, EvidenceGraph):
    id: str = Field(alias="_id")
    revision: int = 1
    created_by: str = ""
    updated_by: str = ""
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    deleted: bool = False

    class Settings:
        name = "evidence_chains"
        indexes = [
            IndexModel([("deleted", ASCENDING), ("updated_at", DESCENDING)]),
            IndexModel([("nodes.chain_id", ASCENDING)]),
        ]
