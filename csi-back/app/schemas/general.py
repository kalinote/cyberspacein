from typing import Generic, TypeVar, List, Any
from pydantic import BaseModel, Field

T = TypeVar('T')


class DictModel(BaseModel):
    key: str
    value: Any


class PageParams(BaseModel):
    page: int = Field(default=1, ge=1, description="页码，从1开始")
    page_size: int = Field(default=10, ge=1, le=100, description="每页数量，最大100")


class PageResponse(BaseModel, Generic[T]):
    total: int = Field(description="总记录数")
    page: int = Field(description="当前页码")
    page_size: int = Field(description="每页数量")
    total_pages: int = Field(description="总页数")
    items: List[T] = Field(description="数据列表")

    @classmethod
    def create(cls, items: List[T], total: int, page: int, page_size: int) -> "PageResponse[T]":
        total_pages = (total + page_size - 1) // page_size if total > 0 else 0
        return cls(
            total=total,
            page=page,
            page_size=page_size,
            total_pages=total_pages,
            items=items
        )
