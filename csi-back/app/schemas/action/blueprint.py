from typing import List, Optional, Any, Dict
from datetime import datetime
from pydantic import BaseModel, Field
from app.schemas.general import DictModel


class Position(BaseModel):
    """位置坐标"""
    x: float = Field(description="X坐标")
    y: float = Field(description="Y坐标")


class NodeData(BaseModel):
    """节点数据"""
    definition_id: str = Field(description="定义ID")
    version: str = Field(description="版本")
    form_data: Dict[str, Any] = Field(description="表单数据，字典格式")


class GraphNode(BaseModel):
    """图节点"""
    id: str = Field(description="节点ID")
    type: str = Field(description="节点类型")
    position: Position = Field(description="节点位置")
    data: NodeData = Field(description="节点数据")


class GraphEdge(BaseModel):
    """图边"""
    id: str = Field(description="边ID")
    source: str = Field(description="源节点ID")
    sourceHandle: str = Field(description="源节点连接点")
    target: str = Field(description="目标节点ID")
    targetHandle: str = Field(description="目标节点连接点")


class Viewport(BaseModel):
    """视口"""
    x: float = Field(description="视口X坐标")
    y: float = Field(description="视口Y坐标")
    zoom: float = Field(description="缩放比例")


class Graph(BaseModel):
    """图结构"""
    nodes: List[GraphNode] = Field(description="节点列表")
    edges: List[GraphEdge] = Field(description="边列表")
    viewport: Viewport = Field(description="视口信息")


class ActionBlueprint(BaseModel):
    """行动蓝图"""
    name: str = Field(description="蓝图名称")
    description: str = Field(description="蓝图描述")
    version: str = Field(description="蓝图版本")
    target: str = Field(description="行动目标")
    implementation_period: int = Field(description="实施周期（秒）")
    resource: Optional[Dict[str, Any]] = Field(default=None, description="资源信息")
    graph: Graph = Field(description="图结构")


class ActionBlueprintResponse(ActionBlueprint):
    """行动蓝图响应"""
    id: str = Field(description="蓝图ID")
    created_at: datetime = Field(description="创建时间")
    updated_at: datetime = Field(description="更新时间")

