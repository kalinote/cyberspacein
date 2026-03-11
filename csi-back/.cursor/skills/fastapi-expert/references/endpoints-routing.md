# 接口与路由

项目接口统一使用 `ApiResponseSchema`（单条/任意数据与错误）和 `PageResponseSchema`（分页列表），定义见 `app.schemas.response` 与 `app.schemas.general`。

## Router 与依赖

```python
from fastapi import APIRouter, Depends, Query
from typing import Annotated

router = APIRouter(prefix="/items", tags=["示例"])

# 分页参数统一用 PageParamsSchema
from app.schemas.general import PageParamsSchema, PageResponseSchema
from app.schemas.response import ApiResponseSchema
```

## 单条数据与错误返回

- 成功：`return ApiResponseSchema.success(data=...)`
- 失败：`return ApiResponseSchema.error(code=404, message="不存在")`，不直接 `raise HTTPException`
- 数据获取与 Model→Response 转换放在 service，接口只调用并拼装响应。

```python
from app.service.action.item import get_item, create_item, item_doc_to_response

@router.get("/detail/{item_id}", response_model=ApiResponseSchema[ItemResponse], summary="详情")
async def get_item_detail(item_id: str):
    doc = await get_item(item_id)
    if not doc:
        return ApiResponseSchema.error(code=404, message=f"不存在，ID: {item_id}")
    return ApiResponseSchema.success(data=item_doc_to_response(doc))

@router.post("", response_model=ApiResponseSchema[ItemResponse], summary="创建")
async def create_item_endpoint(data: ItemCreateRequest):
    item = await create_item(data)
    if item is None:
        return ApiResponseSchema.error(code=400, message="已存在")
    return ApiResponseSchema.success(data=item_doc_to_response(item))
```

## 分页列表

- 查询参数：`params: PageParamsSchema = Depends()`（含 `page` 默认 1、`page_size` 默认 10，最大 100）
- 返回：`PageResponseSchema.create(items, total, page, page_size)`
- 分页查询与转换放在 service，接口只调用并返回 `PageResponseSchema.create`。

```python
from app.service.action.item import get_item_list

@router.get("/list", response_model=PageResponseSchema[ItemResponse], summary="分页列表")
async def get_item_list_endpoint(
    params: PageParamsSchema = Depends(),
    platform_id: str | None = Query(default=None),
):
    results, total = await get_item_list(platform_id, params.page, params.page_size)
    return PageResponseSchema.create(results, total, params.page, params.page_size)
```

## 路径与查询参数

```python
from fastapi import Query, Path

@router.get("/search")
async def search(
    q: str = Query(min_length=1, max_length=100),
    status: str | None = None,
    item_id: Annotated[str, Path(description="资源ID")],
):
    ...
```

## 挂载路由

```python
# main.py 或路由聚合模块
from fastapi import FastAPI
from app.api.v1.endpoints.action import accounts, example

app = FastAPI()
app.include_router(accounts.router, prefix="/api/v1/action")
app.include_router(example.router, prefix="/api/v1/action")
```

## 速查

| 用途 | 写法 |
|------|------|
| 单条/创建/更新/删除成功 | `ApiResponseSchema.success(data=...)` 或 `ApiResponseSchema.success()` |
| 业务错误 | `ApiResponseSchema.error(code=4xx/5xx, message="...")` |
| 分页入参 | `params: PageParamsSchema = Depends()` |
| 分页返回 | `PageResponseSchema.create(items, total, params.page, params.page_size)` |
| response_model 单条 | `ApiResponseSchema[YourResponse]` |
| response_model 分页 | `PageResponseSchema[ItemResponse]` |
