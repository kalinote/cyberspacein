from typing import List, Optional, Any, Dict
from datetime import datetime, timezone
from beanie import Document
from pydantic import Field


class HandleModel(Document):
    id: str
    type: str
    position: str
    socket_type: str
    allowed_socket_types: Optional[List[str]] = None
    label: str
    custom_style: Optional[Dict[str, Any]] = None


class InputModel(Document):
    id: str
    type: str
    position: str
    label: str
    description: str
    required: bool
    default: Any
    options: Optional[List[Dict[str, str]]] = None
    custom_style: Optional[Dict[str, Any]] = None
    custom_props: Optional[Dict[str, Any]] = None


class NodeTypeConfigModel(Document):
    id: str = Field(unique=True)
    name: str
    description: str
    type: str
    version: str
    handles: List[HandleModel]
    inputs: List[InputModel]
    
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    
    class Settings:
        name = "node_type_configs"
        indexes = [
            "id",
            "type",
            "version",
            "created_at",
        ]

