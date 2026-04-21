"""app.core.exceptions 业务异常类测试。"""

import app.utils.status_codes as status_codes
from app.core.exceptions import (
    ApiException,
    BadRequestException,
    ForbiddenException,
    InternalServerException,
    NotFoundException,
    UnauthorizedException,
)


def test_api_exception_stores_code_message_data():
    # 基类应保存 code、message、data 并支持 str(message) 语义
    exc = ApiException(123456, "提示", {"k": 1})
    assert exc.code == 123456
    assert exc.message == "提示"
    assert exc.data == {"k": 1}
    assert str(exc) == "提示"


def test_bad_request_exception_default_code():
    # BadRequestException 使用 HTTP 标准 400 段拼装的状态码
    exc = BadRequestException()
    expected = status_codes.build_status_code(
        status_codes.StatusCodeSource.HTTP_STANDARD,
        status_codes.StatusCodeCategory.BAD_REQUEST,
    )
    assert exc.code == expected
    assert exc.message == "请求参数错误"


def test_unauthorized_exception():
    # 未授权异常码与公共常量一致
    exc = UnauthorizedException("自定义")
    assert exc.code == status_codes.UNAUTHORIZED
    assert exc.message == "自定义"


def test_forbidden_exception():
    # 禁止访问异常码与公共常量一致
    exc = ForbiddenException()
    assert exc.code == status_codes.FORBIDDEN


def test_not_found_exception():
    # 资源不存在异常码与公共常量一致
    exc = NotFoundException()
    assert exc.code == status_codes.NOT_FOUND


def test_internal_server_exception():
    # 内部错误异常码与公共常量一致
    exc = InternalServerException()
    assert exc.code == status_codes.INTERNAL_ERROR
