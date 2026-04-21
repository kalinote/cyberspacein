from app.schemas.general import DictModelSchema
from app.utils.dict_helper import pack_dict, unpack_dict


def test_pack_dict_none_returns_empty_list():
    """None 映射为空列表。"""
    assert pack_dict(None) == []


def test_pack_dict_empty_dict():
    """空字典映射为空列表。"""
    assert pack_dict({}) == []


def test_pack_dict_roundtrip():
    """普通字典能正确转为 DictModel 列表并保留键值。"""
    data = {"a": 1, "b": "x"}
    packed = pack_dict(data)
    assert len(packed) == 2
    assert {p.key: p.value for p in packed} == data


def test_unpack_dict_none_returns_empty_dict():
    """None 映射为空字典。"""
    assert unpack_dict(None) == {}


def test_unpack_dict_empty_list():
    """空列表映射为空字典。"""
    assert unpack_dict([]) == {}


def test_unpack_dict_with_models():
    """DictModel 列表能还原为字典，含嵌套值。"""
    items = [
        DictModelSchema(key="k1", value=10),
        DictModelSchema(key="k2", value={"nested": True}),
    ]
    assert unpack_dict(items) == {"k1": 10, "k2": {"nested": True}}


def test_pack_unpack_roundtrip():
    """pack 再 unpack 与原字典一致。"""
    original = {"x": 1, "y": [1, 2]}
    assert unpack_dict(pack_dict(original)) == original
