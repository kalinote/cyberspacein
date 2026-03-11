---
name: fastapi-expert
description: "适用于使用 FastAPI 与 Pydantic V2 构建高性能异步 Python API。可用于：创建 REST 接口、定义 Pydantic 模型、配置异步 MongoDB（Beanie ODM）、编写 WebSocket 接口或生成 OpenAPI 文档。触发词：FastAPI、Pydantic、async Python、Python API、REST API Python、Beanie、MongoDB、OpenAPI、Swagger Python。"
---

# FastAPI 专家

专注于异步 Python、Pydantic V2 以及基于 FastAPI 的生产级 API 开发。项目使用 Beanie 作为异步 MongoDB ODM，接口统一使用 `ApiResponseSchema` 与 `PageResponseSchema` 封装返回。

## 何时使用本 Skill

- 使用 FastAPI 构建 REST API
- 编写 Pydantic V2 校验用 Schema
- 使用 Beanie 进行异步 MongoDB 读写
- 编写 WebSocket 接口
- 优化 API 性能

## 核心流程

1. **分析需求** — 明确接口、数据模型与业务规则
2. **设计 Schema** — 用 Pydantic V2 定义请求/响应模型
3. **实现接口** — 用依赖注入编写异步端点，单条数据用 `ApiResponseSchema`，列表分页用 `PageResponseSchema` + `PageParamsSchema`

> **每步完成后确认：** Schema 校验正确、接口返回预期 HTTP 状态码与统一响应结构，再继续下一步。

## 统一响应与分页

- **单条/任意数据**：`response_model=ApiResponseSchema[YourResponse]`，成功用 `ApiResponseSchema.success(data=...)`，失败用 `ApiResponseSchema.error(code=..., message=...)`，不返回 `HTTPException`。
- **分页列表**：`response_model=PageResponseSchema[ItemResponse]`，查询参数用 `PageParamsSchema = Depends()`（含 `page`、`page_size`），返回用 `PageResponseSchema.create(items, total, page, page_size)`。

Schema 定义见 `app.schemas.general`（`PageParamsSchema`、`PageResponseSchema`）与 `app.schemas.response`（`ApiResponseSchema`）。

## 最简完整示例

基于 Beanie 的 Schema、Model、**业务层（service）**、**工具（utils）** 与接口分层示例：业务与 Model→Response 转换写在 service，工具写在 utils，接口只调用并返回统一响应。

```python
# app/schemas/action/example.py（节选）
from datetime import datetime
from pydantic import BaseModel, Field

class ItemCreateRequest(BaseModel):
    name: str = Field(description="名称")
    platform_id: str = Field(description="关联平台ID")

class ItemUpdateRequest(BaseModel):
    name: str | None = Field(default=None, description="名称")
    platform_id: str | None = Field(default=None, description="关联平台ID")

class ItemResponse(BaseModel):
    id: str = Field(description="ID")
    name: str = Field(description="名称")
    platform_id: str = Field(description="关联平台ID")
    created_at: datetime = Field(description="创建时间")
    updated_at: datetime = Field(description="更新时间")
```

```python
# app/models/action/example.py
from datetime import datetime
from beanie import Document
from pydantic import Field

class ItemModel(Document):
    id: str = Field(alias="_id")
    name: str
    platform_id: str
    is_deleted: bool = Field(default=False)
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)

    class Settings:
        name = "action_items"
        indexes = ["id", "platform_id"]
```

```python
# app/service/action/item.py（业务：CRUD + Model→Response 转换）
from datetime import datetime
from beanie.operators import Set

from app.models.action.example import ItemModel
from app.schemas.action.example import ItemCreateRequest, ItemUpdateRequest, ItemResponse
from app.utils.id_lib import generate_id


def item_doc_to_response(doc: ItemModel) -> ItemResponse:
    return ItemResponse(
        id=doc.id,
        name=doc.name,
        platform_id=doc.platform_id,
        created_at=doc.created_at,
        updated_at=doc.updated_at,
    )


async def create_item(data: ItemCreateRequest) -> ItemModel | None:
    item_id = generate_id(data.platform_id + data.name + datetime.now().isoformat())
    if await ItemModel.find_one({"_id": item_id}):
        return None
    item = ItemModel(id=item_id, name=data.name, platform_id=data.platform_id)
    await item.insert()
    return item


async def get_item(item_id: str) -> ItemModel | None:
    return await ItemModel.find_one({"_id": item_id, "is_deleted": False})


async def get_item_list(
    platform_id: str | None, page: int, page_size: int
) -> tuple[list[ItemResponse], int]:
    query_filters: dict = {"is_deleted": False}
    if platform_id is not None:
        query_filters["platform_id"] = platform_id
    query = ItemModel.find(query_filters)
    total = await query.count()
    items = await query.skip((page - 1) * page_size).limit(page_size).to_list()
    return [item_doc_to_response(doc) for doc in items], total


async def update_item(item_id: str, data: ItemUpdateRequest) -> ItemModel | None:
    doc = await ItemModel.find_one({"_id": item_id, "is_deleted": False})
    if not doc:
        return None
    update_data = data.model_dump(exclude_unset=True)
    update_data["updated_at"] = datetime.now()
    await doc.update({"$set": update_data})
    return await ItemModel.get(item_id)


async def delete_item_soft(item_id: str) -> bool:
    doc = await ItemModel.find_one({"_id": item_id, "is_deleted": False})
    if not doc:
        return False
    await doc.update(Set({ItemModel.is_deleted: True, ItemModel.updated_at: datetime.now()}))
    return True
```

```python
# app/api/v1/endpoints/action/example.py（接口层仅调用 service，不做业务/工具）
from fastapi import APIRouter, Depends, Query

from app.schemas.action.example import ItemCreateRequest, ItemUpdateRequest, ItemResponse
from app.schemas.general import PageParamsSchema, PageResponseSchema
from app.schemas.response import ApiResponseSchema
from app.service.action.item import (
    create_item,
    get_item,
    get_item_list,
    update_item,
    delete_item_soft,
    item_doc_to_response,
)

router = APIRouter(prefix="/items", tags=["示例"])


@router.post("", response_model=ApiResponseSchema[ItemResponse], summary="创建")
async def create_item_endpoint(data: ItemCreateRequest):
    item = await create_item(data)
    if item is None:
        return ApiResponseSchema.error(code=400, message="已存在")
    return ApiResponseSchema.success(data=item_doc_to_response(item))


@router.get("/list", response_model=PageResponseSchema[ItemResponse], summary="分页列表")
async def get_item_list_endpoint(
    params: PageParamsSchema = Depends(),
    platform_id: str | None = Query(default=None),
):
    results, total = await get_item_list(platform_id, params.page, params.page_size)
    return PageResponseSchema.create(results, total, params.page, params.page_size)


@router.get("/detail/{item_id}", response_model=ApiResponseSchema[ItemResponse], summary="详情")
async def get_item_detail_endpoint(item_id: str):
    doc = await get_item(item_id)
    if not doc:
        return ApiResponseSchema.error(code=404, message=f"不存在，ID: {item_id}")
    return ApiResponseSchema.success(data=item_doc_to_response(doc))


@router.patch("/{item_id}", response_model=ApiResponseSchema[ItemResponse], summary="更新")
async def update_item_endpoint(item_id: str, data: ItemUpdateRequest):
    updated = await update_item(item_id, data)
    if not updated:
        return ApiResponseSchema.error(code=404, message=f"不存在，ID: {item_id}")
    return ApiResponseSchema.success(data=item_doc_to_response(updated))


@router.delete("/{item_id}", response_model=ApiResponseSchema[None], summary="软删除")
async def delete_item_endpoint(item_id: str):
    ok = await delete_item_soft(item_id)
    if not ok:
        return ApiResponseSchema.error(code=404, message=f"不存在，ID: {item_id}")
    return ApiResponseSchema.success()
```

## 参考文档

按需查阅对应主题：

| 主题 | 参考文件 | 适用场景 |
|------|----------|----------|
| Pydantic V2 | `references/pydantic-v2.md` | Schema、校验、model_config |
| Beanie（MongoDB ODM） | `references/async-beanie.md` | Document 模型、查询、分页、CRUD |
| 接口与路由 | `references/endpoints-routing.md` | APIRouter、依赖、统一响应与分页 |

## 约束

### 必须遵守

- 全程使用类型注解（FastAPI 依赖类型）
- 使用 Pydantic V2 写法（`field_validator`、`model_validator`、`model_config`）
- 依赖注入使用 `Annotated` 写法
- 所有 I/O 使用 async/await
- 使用 `X | None`，不用 `Optional[X]`
- 单条/错误返回使用 `ApiResponseSchema.success` / `ApiResponseSchema.error`，不直接 `raise HTTPException`
- 分页列表使用 `PageParamsSchema` + `PageResponseSchema.create(items, total, page, page_size)`
- 为接口补充 `summary` 等说明（便于生成 OpenAPI 文档）
- **业务逻辑与 Model→Response 转换放在 service，通用工具放在 utils，接口层只做调用与统一响应封装**

### 禁止做法

- 使用同步数据库操作
- 跳过 Pydantic 校验
- 在响应中返回敏感字段
- 使用 Pydantic V1 写法（`@validator`、`class Config`）
- 混用同步/异步且用法不当
- 硬编码配置（密钥、环境相关值等）
- 在接口文件中定义业务函数或工具函数（应放到 service / utils）

## 输出模板

实现 FastAPI 功能时，建议包含：

1. Schema 文件（请求/响应 Pydantic 模型）
2. 若涉及 MongoDB：Beanie Document 模型（含 `Settings` 与 `indexes`）
3. **Service 层**：CRUD 与 Model→Response 转换（如 `app.service.action.xxx`）
4. 若需通用能力：**utils** 中工具函数（如 `app.utils.id_lib.generate_id`）
5. 接口文件：仅调用 service/utils，返回 `ApiResponseSchema` / `PageResponseSchema`
6. 关键设计决策的简要说明

## 知识参考

FastAPI、Pydantic V2、Beanie、MongoDB、BackgroundTasks、WebSocket、依赖注入、OpenAPI/Swagger
