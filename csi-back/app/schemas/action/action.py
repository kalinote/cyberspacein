from datetime import datetime
from pydantic import BaseModel, Field
from app.schemas.enum import ActionFlowStatusEnum

class StartActionRequest(BaseModel):
    blueprint_id: str = Field(description="蓝图ID")
    
class StartActionResponse(BaseModel):
    action_id: str = Field(description="行动ID")
    
class ActionInstanceBaseInfoResponse(BaseModel):
    id: str = Field(description="行动ID")
    name: str = Field(description="行动名称")
    description: str = Field(description="行动描述")
    status: ActionFlowStatusEnum = Field(description="行动实例化流程状态")
    start_at: datetime | None = Field(default=None, description="行动实例化流程开始时间")
    finished_at: datetime | None = Field(default=None, description="行动实例化流程结束时间")
    duration: int = Field(description="行动执行时长(秒)")
    progress: int = Field(description="行动实例化流程进度(%)")
    completed_steps: int = Field(description="已完成的节点数量")
    total_steps: int = Field(description="总节点数量")