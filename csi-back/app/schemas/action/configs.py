from typing import Any
from pydantic import BaseModel, Field

from app.schemas.constants import ActionConfigIOTypeEnum

class ActionNodesHandleConfigRequest(BaseModel):
    handle_name: str = Field(description="连接点名称")
    type: ActionConfigIOTypeEnum = Field(description="接口类型")
    label: str = Field(description="标签")
    color: str = Field(description="颜色代码")
    other_compatible_interfaces: list[str] = Field(default=[], description="其他兼容接口id列表")
    custom_style: dict[str, Any] | None = None
    
class ActionNodesHandleConfigResponse(ActionNodesHandleConfigRequest):
    id: str = Field(description="handle配置ID")
    
class ActionNodesHandleConfigAllResponse(BaseModel):
    id: str = Field(description="handle配置ID")
    label: str = Field(description="标签")
    
class ActionConfigsStatisticsResponse(BaseModel):
    node_count: int = Field(default=-1, description="节点数量")
    base_component_count: int = Field(default=-1, description="基础组件数量")
    handle_count: int = Field(default=-1, description="连接点数量")
    proxy_count: int = Field(default=-1, description="代理数量")
    account_count: int = Field(default=-1, description="账号数量")
    corpus_count: int = Field(default=-1, description="语料库数量")
    container_count: int = Field(default=-1, description="沙盒容器数量")
    