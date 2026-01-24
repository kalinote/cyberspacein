from enum import Enum
from typing import Optional, List, Dict
from pydantic import BaseModel, Field


class EntitiesRequest(BaseModel):
    text: str = Field(description="待提取实体的文本内容", min_length=1)


class EntitiesResponse(BaseModel):
    entities: Dict[str, List[str]] = Field(description="提取的实体列表，按类别分组")


class EntitiesTaskStatus(str, Enum):
    pending = "pending"
    processing = "processing"
    completed = "completed"
    failed = "failed"


class EntitiesAsyncRequest(BaseModel):
    text: str = Field(description="待提取实体的文本内容", min_length=1)


class EntitiesAsyncResponse(BaseModel):
    token: str = Field(description="任务token，用于查询实体提取状态和结果")


class EntitiesStatusResponse(BaseModel):
    status: EntitiesTaskStatus = Field(description="任务状态")
    entities: Optional[Dict[str, List[str]]] = Field(default=None, description="提取的实体列表（按类别分组），仅在状态为completed时返回")
    error: Optional[str] = Field(default=None, description="错误信息，仅在状态为failed时返回")
    all: Optional[int] = Field(default=None, description="总段数，仅在状态为processing或completed时返回")
    finished: Optional[int] = Field(default=None, description="已处理段数，仅在状态为processing或completed时返回")
