import hashlib

from app.utils.id_lib import generate_id


def test_generate_id_length_and_hex():
    """输出 32 位十六进制，与 sha256 截断一致。"""
    s = "hello"
    out = generate_id(s)
    assert len(out) == 32
    assert out == hashlib.sha256(s.encode()).hexdigest()[:32]
    int(out, 16)


def test_generate_id_distinct_inputs():
    """不同输入产生不同 id。"""
    assert generate_id("a") != generate_id("b")
