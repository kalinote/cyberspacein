from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field


class TranslateRequest(BaseModel):
    text: str = Field(description="待翻译的文本内容", min_length=1)
    target_lang: str = Field(default="中文", description="目标语种（如：中文、英文、日文等）", min_length=1)


class TranslateResponse(BaseModel):
    result: str = Field(description="翻译后的文本内容")


class TranslateTaskStatus(str, Enum):
    pending = "pending"
    processing = "processing"
    completed = "completed"
    failed = "failed"


class TranslateAsyncRequest(BaseModel):
    text: str = Field(description="待翻译的文本内容", min_length=1)
    target_lang: str = Field(description="目标语种（如：中文、英文、日文等）", min_length=1)


class TranslateAsyncResponse(BaseModel):
    token: str = Field(description="任务token，用于查询翻译状态和结果")


class TranslateStatusResponse(BaseModel):
    status: TranslateTaskStatus = Field(description="任务状态")
    result: Optional[str] = Field(default=None, description="翻译结果，仅在状态为completed时返回")
    error: Optional[str] = Field(default=None, description="错误信息，仅在状态为failed时返回")
