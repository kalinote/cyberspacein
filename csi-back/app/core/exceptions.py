from typing import Any, Optional


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
        super().__init__(code=400, message=message, data=data)


class UnauthorizedException(ApiException):
    def __init__(self, message: str = "未授权", data: Optional[Any] = None):
        super().__init__(code=401, message=message, data=data)


class ForbiddenException(ApiException):
    def __init__(self, message: str = "无权限访问", data: Optional[Any] = None):
        super().__init__(code=403, message=message, data=data)


class NotFoundException(ApiException):
    def __init__(self, message: str = "资源不存在", data: Optional[Any] = None):
        super().__init__(code=404, message=message, data=data)


class InternalServerException(ApiException):
    def __init__(self, message: str = "服务器内部错误", data: Optional[Any] = None):
        super().__init__(code=500, message=message, data=data)
