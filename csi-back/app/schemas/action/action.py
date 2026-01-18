from datetime import datetime
from typing import Any
from pydantic import BaseModel, Field
from app.schemas.action.blueprint import GraphSchema
from app.schemas.enum import ActionConfigIOTypeEnum, ActionFlowStatusEnum, ActionInstanceNodeStatusEnum

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
    duration: float = Field(description="行动执行时长(秒)")
    progress: int = Field(description="行动实例化流程进度(%)")
    completed_steps: int = Field(description="已完成的节点数量")
    total_steps: int = Field(description="总节点数量")
    

class ActionNodeDetailResponse(BaseModel):
    status: ActionInstanceNodeStatusEnum = Field(description="节点状态")
    progress: int = Field(default=0, description="节点执行进度(%)")
    start_at: datetime | None = Field(default=None, description="节点执行开始时间")
    finished_at: datetime | None = Field(default=None, description="节点执行结束时间")
    duration: float = Field(default=0, description="节点执行时长(秒)")
    inputs: dict[str, Any] = Field(default={}, description="节点输入配置")
    outputs: dict[str, Any] = Field(default={}, description="节点输出配置")
    error_message: str | None = Field(default=None, description="节点执行错误信息")

class ActionDetailResponse(ActionInstanceBaseInfoResponse):
    """
    行动详细信息的响应，用于正在执行的行动详细的信息页
    """
    graph: GraphSchema = Field(description="行动蓝图，用于标识基本结构和布局")
    resource: dict[str, Any] = Field(default={}, description="分配资源，暂未实现")
    implementation_period: int = Field(description="执行期限(秒)")
    node_details: dict[str, ActionNodeDetailResponse] = Field(description="节点详细信息")

class ActionConfigMeta(BaseModel):
    node_instance_id: str = Field(description="节点实例ID")
    action_id: str = Field(description="行动ID")

class ActionConfigIO(BaseModel):
    type: ActionConfigIOTypeEnum = Field(description="数据类型")
    value: Any | None = Field(default=None, description="数据值")

class ActionNodeConfigInitResponse(BaseModel):
    """
    节点配置初始化响应，用于基础构建SDK获取基本节点参数配置
    """
    meta: ActionConfigMeta = Field(description="节点配置元数据")
    config: dict[str, Any] = Field(default={}, description="节点配置")
    inputs: dict[str, ActionConfigIO] = Field(default={}, description="节点输入配置")
    outputs: dict[str, ActionConfigIO] = Field(default={}, description="节点输出配置")
