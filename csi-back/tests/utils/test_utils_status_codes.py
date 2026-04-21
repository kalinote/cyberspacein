import pytest

from app.utils.status_codes import (
    StatusCodeCategory,
    StatusCodeSource,
    build_status_code,
)


def test_build_status_code_basic():
    """枚举参数组合得到预期整数状态码。"""
    code = build_status_code(StatusCodeSource.INTERNAL, StatusCodeCategory.BAD_REQUEST, 7)
    assert code == 140007


def test_build_status_code_int_args():
    """允许传入整型 source/category/sub_category。"""
    assert build_status_code(2, 500, 0) == 250000


def test_build_status_code_invalid_source():
    """source 非 1/2 时抛出 ValueError。"""
    with pytest.raises(ValueError, match="source"):
        build_status_code(3, 400, 0)


def test_build_status_code_invalid_category_low():
    """category 小于 0 时抛出 ValueError。"""
    with pytest.raises(ValueError, match="category"):
        build_status_code(1, -1, 0)


def test_build_status_code_invalid_category_high():
    """category 大于 999 时抛出 ValueError。"""
    with pytest.raises(ValueError, match="category"):
        build_status_code(1, 1000, 0)


def test_build_status_code_invalid_sub_negative():
    """sub_category 为负时抛出 ValueError。"""
    with pytest.raises(ValueError, match="sub_category"):
        build_status_code(1, 400, -1)


def test_build_status_code_invalid_sub_high():
    """sub_category 大于 99 时抛出 ValueError。"""
    with pytest.raises(ValueError, match="sub_category"):
        build_status_code(1, 400, 100)
