"""app.schemas.embedding 嵌入接口 Schema 测试。"""

from app.schemas.embedding import (
    BatchEmbeddingItemSchema,
    BatchEmbeddingRequestSchema,
    EmbeddingRequestSchema,
    EmbeddingResponseSchema,
)


def test_embedding_request_response():
    # 单条文本嵌入的请求体与向量响应结构
    EmbeddingRequestSchema(text="hello")
    EmbeddingResponseSchema(vector=[0.1, 0.2])


def test_batch_embedding_request():
    # 批量条目列表应能正确装入请求模型
    req = BatchEmbeddingRequestSchema(
        datas=[
            BatchEmbeddingItemSchema(uuid="a", text="t1"),
            BatchEmbeddingItemSchema(uuid="b", text="t2"),
        ]
    )
    assert len(req.datas) == 2
