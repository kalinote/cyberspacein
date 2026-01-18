from typing import Any
from datetime import datetime
from beanie import Document
from pydantic import BaseModel, Field
from app.schemas.general import DictModelSchema


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
    form_data: list[DictModelSchema]


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
    nodes: list[GraphNodeModel]
    edges: list[GraphEdgeModel]
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
    resource: dict[str, Any] | None = None
    graph: GraphModel
    is_deleted: bool = Field(default=False, description="是否已删除")
    is_template: bool = Field(default=False, description="是否为模板")
    # TODO: 后续增加对应的模型
    template: dict[str, Any] | None = Field(default=None, description="模板配置")
    
    created_at: datetime = Field(default_factory=lambda: datetime.now())
    updated_at: datetime = Field(default_factory=lambda: datetime.now())
    
    class Settings:
        name = "action_blueprints"
        indexes = [
            "id",
            "name",
        ]

