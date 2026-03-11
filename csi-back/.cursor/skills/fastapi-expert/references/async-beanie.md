# Beanie 异步 MongoDB ODM

本项目使用 [Beanie](https://beanie-odm.dev/) 作为异步 MongoDB ODM，所有文档模型继承 `beanie.Document`，在应用启动时通过 `init_beanie` 注册。

## 文档模型定义

- 主键使用 `id: str = Field(alias="_id")`，由业务层生成（如 `app.utils.id_lib.generate_id`），不交给 MongoDB 自动生成。
- 集合名与索引在 `class Settings` 中配置。

```python
from datetime import datetime
from beanie import Document
from pydantic import BaseModel, Field

class AccountModel(Document):
    id: str = Field(alias="_id", description="由 generate_id 生成")
    platform_id: str = Field(description="关联平台表ID")
    account_name: str = Field(description="内部展示用的账号别名")
    is_deleted: bool = Field(default=False, description="是否已删除(软删除)")
    created_at: datetime = Field(default_factory=datetime.now, description="创建时间")
    updated_at: datetime = Field(default_factory=datetime.now, description="更新时间")

    class Settings:
        name = "action_accounts"
        indexes = [
            "id",
            "platform_id",
            "account_name",
        ]
```

## 内嵌模型（Embedded）

子结构用 Pydantic `BaseModel` 定义，在 Document 中作为字段类型使用，会以嵌入式文档形式存入库中。

```python
from pydantic import BaseModel, Field

class CredentialsModel(BaseModel):
    username: str | None = Field(default=None, description="用户名")
    password: str | None = Field(default=None, description="密码(加密存储)")
    email: str | None = Field(default=None, description="邮箱")

class AccountModel(Document):
    id: str = Field(alias="_id")
    platform_id: str
    account_name: str
    credentials: CredentialsModel = Field(default_factory=CredentialsModel)
    # ...
```

## 模型注册

在应用启动时（如 `main.py` 或数据库初始化模块）调用 `init_beanie`，传入数据库实例与所有 Document 模型列表。模型列表由 `app.models.get_all_models()` 统一维护。

```python
from beanie import init_beanie
from app.models import get_all_models

async def init_db():
    client = AsyncIOMotorClient(settings.MONGODB_URI)
    database = client[settings.MONGODB_DB_NAME]
    await init_beanie(database=database, document_models=get_all_models())
```

## 查询

- **按主键查单条**：`await Model.find_one({"_id": id})` 或 `await Model.get(id)`（不存在会抛异常）。
- **条件查询**：`Model.find({"is_deleted": False, "platform_id": platform_id})`，返回查询构造器，可链式 `.skip().limit().to_list()`、`.count()` 等。
- **分页**：`query.skip((page - 1) * page_size).limit(page_size).to_list()`，总数用 `await query.count()`。

```python
query_filters = {"is_deleted": False}
if platform_id is not None:
    query_filters["platform_id"] = platform_id
query = AccountModel.find(query_filters)
total = await query.count()
items = await query.skip((params.page - 1) * params.page_size).limit(params.page_size).to_list()
```

## 写入与更新

- **新增**：实例化 Document 后 `await doc.insert()`。
- **更新**：先 `find_one` 得到文档，再 `await doc.update({"$set": update_data})`，其中 `update_data` 为 `model_dump(exclude_unset=True)` 等得到的字典；若包含内嵌模型，需将字典转回对应 Model 再写入。
- **部分字段更新**：使用 `beanie.operators.Set` 仅更新指定字段（如软删除、updated_at）。

```python
from beanie.operators import Set

await doc.update(Set({
    AccountModel.is_deleted: True,
    AccountModel.updated_at: datetime.now(),
}))
```

## 与接口层配合

- **业务与转换**：CRUD、Model→Response 转换放在 **service**（如 `app.service.action.xxx`），接口层只调用 service 并返回统一响应。
- **单条/错误**：使用 `ApiResponseSchema.success(data=...)` 或 `ApiResponseSchema.error(code=..., message=...)`，不直接 `raise HTTPException`。
- **分页列表**：使用 `PageParamsSchema = Depends()` 获取 `page`、`page_size`，返回 `PageResponseSchema.create(items, total, page, page_size)`。

参考实现：`app.api.v1.endpoints.action.accounts`、Skill 内示例（含 `app.service.action.item`）。

## 速查

| 操作 | 写法 |
|------|------|
| 按 _id 查一条 | `await Model.find_one({"_id": id})` 或 `await Model.get(id)` |
| 条件查询 | `Model.find({"field": value})` |
| 总数 | `await query.count()` |
| 分页列表 | `query.skip((page-1)*page_size).limit(page_size).to_list()` |
| 新增 | `doc = Model(...); await doc.insert()` |
| 更新 | `await doc.update({"$set": update_dict})` |
| 部分字段更新 | `from beanie.operators import Set`；`await doc.update(Set({Model.field: value}))` |
| 集合名/索引 | `class Settings: name = "collection"; indexes = ["id", "platform_id"]` |
