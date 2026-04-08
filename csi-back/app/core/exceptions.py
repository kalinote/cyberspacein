from typing import Any, Optional
import app.utils.status_codes as status_codes


class ApiException(Exception):
    def __init__(
        self,
        code: int,
        message: str,
        data: Optional[Any] = None
    ):
        self.code = code
        self.message = message
        self.data = data
        super().__init__(message)


class BadRequestException(ApiException):
    def __init__(self, message: str = "请求参数错误", data: Optional[Any] = None):
        super().__init__(
            code=status_codes.build_status_code(
                status_codes.StatusCodeSource.HTTP_STANDARD,
                status_codes.StatusCodeCategory.BAD_REQUEST,
            ),
            message=message,
            data=data,
        )


class UnauthorizedException(ApiException):
    def __init__(self, message: str = "未授权", data: Optional[Any] = None):
        super().__init__(code=status_codes.UNAUTHORIZED, message=message, data=data)


class ForbiddenException(ApiException):
    def __init__(self, message: str = "无权限访问", data: Optional[Any] = None):
        super().__init__(code=status_codes.FORBIDDEN, message=message, data=data)


class NotFoundException(ApiException):
    def __init__(self, message: str = "资源不存在", data: Optional[Any] = None):
        super().__init__(code=status_codes.NOT_FOUND, message=message, data=data)


class InternalServerException(ApiException):
    def __init__(self, message: str = "服务器内部错误", data: Optional[Any] = None):
        super().__init__(code=status_codes.INTERNAL_ERROR, message=message, data=data)
