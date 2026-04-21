"""app.utils.embedding 文本规范化与客户端状态测试。"""

import pytest
from fastapi import HTTPException

import app.utils.embedding as embedding_mod
from app.utils.embedding import normalize_whitespace


def test_normalize_whitespace_collapses_and_strips():
    # 连续空白压成单空格并去两端
    assert normalize_whitespace("  a  \n\t  b  ") == "a b"
    assert normalize_whitespace("") == ""
    assert normalize_whitespace(None) == ""


def test_get_embeddings_client_raises_when_not_initialized():
    # 未 init_embedding_client 时应返回 503
    prev = embedding_mod._embeddings_client
    embedding_mod._embeddings_client = None
    try:
        with pytest.raises(HTTPException) as exc_info:
            embedding_mod.get_embeddings_client()
        assert exc_info.value.status_code == 503
    finally:
        embedding_mod._embeddings_client = prev
