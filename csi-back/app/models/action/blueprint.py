from typing import List, Optional, Any, Dict
from datetime import datetime, timezone
from beanie import Document
from pydantic import BaseModel, Field
from app.schemas.general import DictModel


class PositionModel(BaseModel):
    """
    位置坐标模型
    """
    x: float
    y: float


class NodeDataModel(BaseModel):
    """
    节点数据模型
    """
    definition_id: str
    version: str
    form_data: List[DictModel]


class GraphNodeModel(BaseModel):
    """
    图节点模型
    """
    id: str
    type: str
    position: PositionModel
    data: NodeDataModel


class GraphEdgeModel(BaseModel):
    """
    图边模型
    """
    id: str
    source: str
    sourceHandle: str
    target: str
    targetHandle: str


class ViewportModel(BaseModel):
    """
    视口模型
    """
    x: float
    y: float
    zoom: float


class GraphModel(BaseModel):
    """
    图结构模型
    """
    nodes: List[GraphNodeModel]
    edges: List[GraphEdgeModel]
    viewport: ViewportModel


class ActionBlueprintModel(Document):
    """
    行动蓝图模型
    """
    id: str = Field(alias="_id")
    name: str
    version: str
    description: str
    target: str
    implementation_period: int
    resource: Optional[Dict[str, Any]] = None
    graph: GraphModel
    
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    
    class Settings:
        name = "action_blueprints"
        indexes = [
            "id",
            "name",
        ]

