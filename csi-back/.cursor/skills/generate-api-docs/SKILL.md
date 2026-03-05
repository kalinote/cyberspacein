---
name: generate-api-docs
description: 根据新增或指定的 API 接口生成 Markdown 格式的接口文档，输出到项目根目录。适用于 FastAPI 路由与 Pydantic 模型。在用户新增接口后需要写接口文档、或明确要求生成接口文档时使用。
---

# 生成接口文档

## 使用时机

- 新增 API 接口后需要补充接口文档
- 用户明确要求为某个或某批接口生成/更新接口文档

## 输出位置

将生成的 Markdown 文档**直接放在项目根目录**下。文件名建议：`API-{模块或功能名}.md` 或 `API-{日期}-{功能}.md`，避免覆盖已有文档时可先确认或使用更具体的文件名。

## 文档生成流程

1. **定位接口**：从用户指定或当前修改的代码中，找到目标路由（如 `app/api/v1/endpoints/*.py` 中的 `@router.get/post/put/delete`）。
2. **提取信息**：
   - 请求：HTTP 方法、路径（含 prefix）、Query/Path/Body 参数
   - 请求体：对应的 Pydantic 模型（Request/Schema），从 `app.schemas` 或 endpoint 入参类型获取
   - 响应：`response_model`、`ApiResponseSchema[T]` 或 `PageResponseSchema[T]` 中的 `T`，以及各字段含义
   - 接口说明：路由的 `summary`、`description`（若有）
3. **按下方模板生成文档**，并写入项目根目录的 `.md` 文件。

## 文档结构模板

每个接口按以下结构编写，多个接口可放在同一文档中用标题区分。

```markdown
# [模块/功能名称] 接口文档

## 概述

（可选）简要说明本模块接口用途。

---

## [接口名称]

**接口说明**：（从路由 summary/description 填写，或简要描述用途）

- **请求方式**：`GET` | `POST` | `PUT` | `DELETE` | `PATCH`
- **请求路径**：`/api/v1/xxx/xxx`（含 prefix，与前端/网关一致）
- **Content-Type**：`application/json`（仅 Body 为 JSON 时写）

### 请求参数

#### Query 参数（GET 等）

| 参数名 | 类型 | 必填 | 说明 |
|--------|------|------|------|
| param_a | string | 是 | 说明 |
| param_b | integer | 否 | 说明，默认值 x |

#### Path 参数

| 参数名 | 类型 | 说明 |
|--------|------|------|
| id | string | 资源 ID |

#### Body 参数（POST/PUT/PATCH）

| 参数名 | 类型 | 必填 | 说明 |
|--------|------|------|------|
| field_a | string | 是 | 说明 |
| field_b | object | 否 | 说明 |

（若为嵌套对象，用子表格或缩进列出子字段。）

### 请求示例

**cURL**

````bash
curl -X POST "http://localhost:8000/api/v1/xxx/yyy" \\
  -H "Content-Type: application/json" \\
  -d '{
    "field_a": "示例值",
    "field_b": {}
  }'
````

**JSON Body（仅 POST/PUT/PATCH 且为 JSON 时）**

````json
{
  "field_a": "示例值",
  "field_b": {}
}
````

### 响应说明

- **成功**：HTTP 200，业务码 `code: 0`
- **失败**：HTTP 200，业务码 `code != 0`，或 HTTP 4xx/5xx

#### 响应体结构（成功时 data 字段）

| 字段名 | 类型 | 说明 |
|--------|------|------|
| code | int | 0 表示成功 |
| message | string | 提示信息 |
| data | object/array | 业务数据，结构见下表 |

**data 字段结构**（根据 response_model 展开）

| 字段名 | 类型 | 说明 |
|--------|------|------|
| id | string | 示例说明 |
| name | string | 示例说明 |

### 响应示例

**成功**

````json
{
  "code": 0,
  "message": "success",
  "data": {
    "id": "示例ID",
    "name": "示例名称"
  }
}
````

**失败**

````json
{
  "code": 404,
  "message": "资源不存在",
  "data": null
}
````
```

## 约定说明

- **路径**：需包含路由的 `prefix`（如 `/action`）及主路由前缀（如 `/api/v1`），与项目实际挂载一致。
- **类型**：与 Pydantic/OpenAPI 对应，如 `string`、`integer`、`number`、`boolean`、`array`、`object`；可选/nullable 在说明中注明。
- **请求示例**：Body 示例值尽量用中文占位或可读的示例值，便于联调。
- **分页**：若为分页接口，在请求参数中列出 `page`、`page_size`，在响应中说明 `total`、`items` 等分页字段。
- **认证**：若接口需鉴权，在接口说明或请求示例中注明（如 Header `Authorization`），不写死密钥。

## 质量要求

- 表格与代码块格式正确，能直接渲染为清晰 Markdown。
- 每个接口至少包含：请求方式、路径、请求参数表、请求示例、响应结构说明、成功/失败响应示例。
- 描述详细：参数与字段的说明从 Pydantic `Field(description=...)` 或模型含义提炼，不留空说明。
