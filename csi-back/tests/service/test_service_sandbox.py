"""app.service.sandbox 端口解析等纯函数测试。"""

from app.service.sandbox import _parse_port_range


def test_parse_port_range_single():
    # 单个端口
    assert _parse_port_range("8080") == [8080]


def test_parse_port_range_inclusive():
    # 闭区间展开并去重排序
    assert _parse_port_range("16700-16702") == [16700, 16701, 16702]


def test_parse_port_range_comma_mixed():
    # 混合格式
    out = _parse_port_range("80, 90-91")
    assert out == [80, 90, 91]


def test_parse_port_range_invalid_skipped():
    # 非法段被跳过，不抛错
    assert _parse_port_range("abc, 9000") == [9000]


def test_parse_port_range_empty():
    assert _parse_port_range("") == []
    assert _parse_port_range("   ") == []
