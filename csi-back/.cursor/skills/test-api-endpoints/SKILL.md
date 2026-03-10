---
name: test-api-endpoints
description: 根据接口文档对 API 接口进行请求测试并验证结果。使用预制脚本执行测试，专注于接口输入输出验证；支持跨步骤变量传递，视情况添加 teardown 恢复现场。在用户要求测试接口、验证接口是否正常、或完成接口开发后需要回归测试时使用。
---

# 接口测试技能

## 测试脚本

脚本位于 `scripts/api_tester.py`（相对于本 SKILL.md 所在目录）。

运行方式（必须使用 `.venv` 虚拟环境）：

```powershell
# 测试计划模式（多接口、支持变量传递）
.venv\Scripts\python.exe .cursor\skills\test-api-endpoints\scripts\api_tester.py plan <测试计划.json> [--verbose]

# 单接口快速测试
.venv\Scripts\python.exe .cursor\skills\test-api-endpoints\scripts\api_tester.py request --url http://localhost:8000/api/v1 --path /action/resource --method GET --expected-code 0
```

---

## 工作流程

1. **阅读接口文档**：从用户提供的文档或 `../csi-front/tmp_docs/` 中定位目标接口。
2. **确认服务地址**：询问用户或从 `.env` 读取 `SERVER_HOST`、`SERVER_PORT`、`API_V1_STR` 拼接 base_url。
3. **设计测试步骤**：根据被测接口设计 `tests` 步骤；若有可恢复操作（如有删除接口、开关接口等），视情况添加 `teardown`。
4. **执行测试**：
   - 若参数简单，直接用 `request` 命令行模式测试。
   - 若需多步骤或变量传递，将测试计划保存为临时 JSON 文件（如 `.cursor/skills/test-api-endpoints/tmp_<功能名>.json`），用 `plan` 模式运行。
5. **分析结果**：向用户报告通过/失败情况及原因。
6. **清理文件**：测试完成后删除步骤 4 创建的临时 JSON 文件。

---

## 测试计划格式

```json
{
  "base_url": "http://localhost:8080/api/v1",
  "headers": {
    "Authorization": "Bearer <token>"
  },
  "tests": [
    {
      "name": "新增资源",
      "method": "POST",
      "path": "/action/resource",
      "body": {
        "name": "测试资源"
      },
      "expected": { "code": 0 },
      "extract": {
        "resource_id": "data.id"
      }
    },
    {
      "name": "查询资源详情",
      "method": "GET",
      "path": "/action/resource/{resource_id}",
      "expected": { "code": 0, "data": { "name": "测试资源" } }
    },
    {
      "name": "删除资源",
      "method": "DELETE",
      "path": "/action/resource/{resource_id}",
      "expected": { "code": 0 }
    }
  ],
  "teardown": [
    {
      "name": "恢复：确保资源已删除",
      "method": "DELETE",
      "path": "/action/resource/{resource_id}",
      "expected": { "code": 0 }
    }
  ]
}
```

### 字段说明

| 字段 | 说明 |
|------|------|
| `base_url` | 服务基础地址，含 API 前缀 |
| `headers` | 全局请求头，所有步骤共用 |
| `tests` | 测试阶段，执行所有被测接口；测试结果计入统计 |
| `teardown` | 恢复阶段（可选），用于恢复现场；无论 tests 是否通过都会执行，失败仅警告不计入统计 |
| `extract` | 从响应中提取变量，供后续步骤使用（支持点路径如 `data.id`）；tests 和 teardown 之间共享 |
| `expected` | 期望验证：`code`（业务码）、`status_code`（HTTP 码）、`data`（字段值） |
| `{variable}` | 路径和 body 中可引用 extract 存储的变量 |

---

## 核心原则

- **专注输入输出**：测试重点是验证接口的请求参数与响应结果是否符合预期，而非强制要求创建/查询/删除的完整流程。
- **按接口设计步骤**：根据实际被测接口灵活组织步骤，可以只有查询，可以只有新增，也可以是业务功能调用等。
- **tests 承担测试职责**：所有被测接口均在 `tests` 中执行和验证，包括删除、开关等接口，即便这些接口也会出现在 teardown 中。
- **teardown 仅用于恢复**：`teardown` 不是测试，而是恢复现场的手段（如删除测试中新增的数据、恢复被修改的开关状态等）。仅在有合适的接口支持时才添加 teardown。
- **临时 JSON 文件清理**：测试结束后删除测试计划 JSON 文件。

---

## 单接口命令行示例

```powershell
# GET 请求，验证业务码
.venv\Scripts\python.exe .cursor\skills\test-api-endpoints\scripts\api_tester.py request `
  --url http://localhost:8080/api/v1 --path /action/resource `
  --method GET --query '{"page":1,"page_size":10}' `
  --expected-code 0

# POST 请求，验证业务码 + 响应字段
.venv\Scripts\python.exe .cursor\skills\test-api-endpoints\scripts\api_tester.py request `
  --url http://localhost:8080/api/v1 --path /action/resource `
  --method POST --body '{"name":"测试"}' `
  --expected-code 0 --expected-data name=测试

# 同时验证 HTTP 状态码
.venv\Scripts\python.exe .cursor\skills\test-api-endpoints\scripts\api_tester.py request `
  --url http://localhost:8080/api/v1 --path /action/resource/999 `
  --method GET --expected-status-code 404
```

## expected 验证示例

```json
{ "code": 0 }
{ "code": 0, "status_code": 200 }
{ "code": 0, "data": { "name": "xxx" } }
{ "code": 404 }
```
