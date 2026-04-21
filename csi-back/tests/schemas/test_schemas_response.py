"""app.schemas.response ApiResponseSchema 测试。"""

import pytest

import app.utils.status_codes as status_codes
from app.schemas.response import ApiResponseSchema


def test_api_response_success_defaults():
    # success 默认 message 与 code=0
    r = ApiResponseSchema.success(data={"a": 1})
    assert r.code == 0
    assert r.message == "success"
    assert r.data == {"a": 1}


def test_api_response_success_custom_message():
    # 可自定义成功提示文案
    r = ApiResponseSchema.success(data=None, message="完成")
    assert r.message == "完成"


def test_api_response_error_valid_six_digit_code():
    # 合法六位业务码应能构造错误响应
    code = status_codes.INVALID_ARGUMENT
    r = ApiResponseSchema.error(code=code, message="参数错误")
    assert r.code == code
    assert r.message == "参数错误"


def test_api_response_error_rejects_invalid_code():
    # 非 0 且非 100000~299999 的码应拒绝
    with pytest.raises(ValueError, match="错误码"):
        ApiResponseSchema.error(code=999, message="bad")


def test_api_response_error_accepts_zero():
    # code=0 时允许（若业务层误用 error 仍可序列化）
    r = ApiResponseSchema.error(code=0, message="ok")
    assert r.code == 0
