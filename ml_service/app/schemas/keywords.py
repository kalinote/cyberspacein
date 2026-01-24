from enum import Enum
from typing import Optional, List
from pydantic import BaseModel, Field


class KeywordsRequest(BaseModel):
    text: str = Field(description="待提取关键词的文本内容", min_length=1)


class KeywordsResponse(BaseModel):
    keywords: List[str] = Field(description="提取的关键词列表")


class KeywordsTaskStatus(str, Enum):
    pending = "pending"
    processing = "processing"
    completed = "completed"
    failed = "failed"


class KeywordsAsyncRequest(BaseModel):
    text: str = Field(description="待提取关键词的文本内容", min_length=1)


class KeywordsAsyncResponse(BaseModel):
    token: str = Field(description="任务token，用于查询关键词提取状态和结果")


class KeywordsStatusResponse(BaseModel):
    status: KeywordsTaskStatus = Field(description="任务状态")
    keywords: Optional[List[str]] = Field(default=None, description="提取的关键词列表，仅在状态为completed时返回")
    error: Optional[str] = Field(default=None, description="错误信息，仅在状态为failed时返回")
    all: Optional[int] = Field(default=None, description="总段数，仅在状态为processing或completed时返回")
    finished: Optional[int] = Field(default=None, description="已处理段数，仅在状态为processing或completed时返回")
