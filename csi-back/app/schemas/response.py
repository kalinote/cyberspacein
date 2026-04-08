from typing import Generic, TypeVar, Optional, Any
from pydantic import BaseModel, Field

T = TypeVar('T')


class ApiResponseSchema(BaseModel, Generic[T]):
    code: int = Field(description="响应码，0表示成功，其他表示失败")
    message: str = Field(description="响应消息")
    data: Optional[T] = Field(default=None, description="响应数据")

    @classmethod
    def success(cls, data: T = None, message: str = "success") -> "ApiResponseSchema[T]":
        return cls(code=0, message=message, data=data)

    @classmethod
    def error(cls, code: int, message: str, data: Any = None) -> "ApiResponseSchema":
        if code != 0 and not (100000 <= code <= 299999):
            raise ValueError(f"错误码必须是6位规范码，当前值: {code}")
        return cls(code=code, message=message, data=data)
