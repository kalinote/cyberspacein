from pydantic import BaseModel
from pydantic import Field

class EmbeddingRequestSchema(BaseModel):
    text: str = Field(description="待嵌入的文本")
    
class EmbeddingResponseSchema(BaseModel):
    vector: list[float] = Field(description="嵌入后的向量")
    
class BatchEmbeddingItemSchema(BaseModel):
    uuid: str = Field(description="本条数据的唯一标识")
    text: str = Field(description="待嵌入的文本")
    
class BatchEmbeddingItemResponseSchema(BaseModel):
    uuid: str = Field(description="本条数据的唯一标识")
    vector: list[float] = Field(description="嵌入后的向量")
    
class BatchEmbeddingRequestSchema(BaseModel):
    datas: list[BatchEmbeddingItemSchema] = Field(description="待嵌入的文本列表")
    
class BatchEmbeddingResponseSchema(BaseModel):
    datas: list[BatchEmbeddingItemResponseSchema] = Field(description="嵌入后的向量列表")