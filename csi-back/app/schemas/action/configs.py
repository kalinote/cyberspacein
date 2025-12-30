from typing import Any
from pydantic import BaseModel, Field

from app.schemas.enum import ActionConfigIOTypeEnum

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
    