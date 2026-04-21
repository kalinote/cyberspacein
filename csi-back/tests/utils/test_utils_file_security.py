import pytest

from app.utils.file_security import calculate_file_hash, get_file_extension_from_mime


def test_calculate_file_hash_sha256():
    """sha256 结果与已知向量一致。"""
    data = b"abc"
    assert (
        calculate_file_hash(data, "sha256")
        == "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad"
    )


def test_calculate_file_hash_md5():
    """md5 结果与已知向量一致。"""
    data = b"abc"
    assert calculate_file_hash(data, "md5") == "900150983cd24fb0d6963f7d28e17f72"


def test_calculate_file_hash_invalid_algorithm():
    """不支持的算法名抛出 ValueError。"""
    with pytest.raises(ValueError, match="不支持的哈希算法"):
        calculate_file_hash(b"x", "sha1")


def test_get_file_extension_from_mime_known():
    """已知图片 MIME 返回对应扩展名。"""
    assert get_file_extension_from_mime("image/png") == ".png"


def test_get_file_extension_from_mime_unknown():
    """未配置 MIME 返回 .bin。"""
    assert get_file_extension_from_mime("application/octet-stream") == ".bin"
