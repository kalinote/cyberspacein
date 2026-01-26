from typing import Optional, List
from pydantic import BaseModel, Field


class EmbeddingRequest(BaseModel):
    text: str = Field(description="待计算嵌入向量的文本内容", min_length=1)


class EmbeddingResponse(BaseModel):
    embedding: List[float] = Field(description="文本的嵌入向量")


class EmbeddingBatchItem(BaseModel):
    uuid: str = Field(description="数据项的唯一标识符")
    text: str = Field(description="待计算嵌入向量的文本内容", min_length=1)


class EmbeddingBatchRequest(BaseModel):
    datas: List[EmbeddingBatchItem] = Field(description="批量数据列表", min_length=1)


class EmbeddingBatchItemResponse(BaseModel):
    uuid: str = Field(description="数据项的唯一标识符")
    embedding: Optional[List[float]] = Field(default=None, description="文本的嵌入向量，处理失败时为None")
    error: Optional[str] = Field(default=None, description="错误信息，处理成功时为None")


class EmbeddingBatchResponse(BaseModel):
    results: List[EmbeddingBatchItemResponse] = Field(description="批量处理结果列表")
