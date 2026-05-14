# 分析引擎（Agent）运行时 API — 并行会话改造 · 前端对接说明

本文档说明与「多会话并行」相关的接口路径、调用方式及请求/响应变更，便于前端与 `csi-back` 对齐。统一前缀为 **`{API_V1}/agent`**，其中 `{API_V1}` 与部署一致（例如 `/api/v1`，见服务端 `settings.API_V1_STR`）。

## 1. 通用响应格式

除 SSE 外，JSON 接口均包裹为：

```json
{
  "code": 0,
  "message": "success",
  "data": { }
}
```

- `code === 0` 表示业务成功。  
- `code !== 0` 表示业务失败；**HTTP 状态码可能仍为 200**（由具体路由实现决定），前端必须以 **`code`** 为准判断是否成功。  
- 并行会话占满时，`POST /agent/start` 可能返回 `code` 为冲突类业务码（见下文「并行上限」），`data` 一般为 `null`。

## 2. 启动分析：`POST {API_V1}/agent/start`

### 2.1 作用

为指定 Agent 创建**新会话**并在后台开始分析；返回的 **`session_id` 为本轮唯一标识**，后续 SSE、取消、审批必须携带同一 ID。

### 2.2 请求

- **Method / Path**：`POST {API_V1}/agent/start`  
- **Content-Type**：`application/json`

**Body（`StartAgentRequestSchema`）**

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `agent_id` | string | 是 | 分析引擎 ID |
| `user_prompt` | string \| null | 否 | 用户本轮输入；若为空，服务端可用模板默认 `user_prompt` 渲染 |
| `entity_uuid` | string \| null | 否 | 业务实体 UUID |
| `entity_type` | string 枚举 \| null | 否 | 实体类型，与后端 `EntityType` 一致 |
| `extra_context` | object | 否 | 其它上下文，参与模板渲染 |

### 2.3 成功响应

**`data`（`StartAgentResponseSchema`）**

| 字段 | 类型 | 说明 |
|------|------|------|
| `agent_id` | string | 同请求 |
| `session_id` | string | **本次运行会话 ID**；前端必须持久化到当前「分析任务」上下文 |

### 2.4 并行会话与上限（变更要点）

- 同一 `agent_id` **允许同时存在多个运行中会话**（每次 `/start` 生成新的 `session_id`）。  
- 服务端可通过环境变量 **`NANOBOT_AGENT_MAX_PARALLEL_SESSIONS`** 限制单 Agent **在库中状态为 `running` 的会话数量**：  
  - `0`（默认）：不限制。  
  - `> 0`：当该 Agent 已有不少于上限个 **`running`** 会话时，本次 `start` **失败**，返回业务错误（`code` 为冲突态，与资源冲突同类语义；文案见 `message`）。  
- 前端建议：在收到冲突类错误时提示用户稍后再试或先取消/等待其它会话结束。

## 3. 订阅 SSE：`GET {API_V1}/agent/status`

### 3.1 变更要点（必改）

- **`session_id` 为必填查询参数**。未传或传错会话将无法只订阅本轮任务，且与后端按 `(agent_id, session_id)` 路由事件不一致。

### 3.2 请求

- **Method / Path**：`GET {API_V1}/agent/status`  
- **Query**

| 参数 | 必填 | 说明 |
|------|------|------|
| `agent_id` | 是 | 分析引擎 ID |
| `session_id` | 是 | 与 `/start` 返回的 `session_id` 一致 |
| `debug` | 否 | `true` 时额外推送调试类事件（若后端启用） |

### 3.3 响应

- **Content-Type**：`text/event-stream`（标准 SSE）  
- 每条事件 `data` 为 JSON 字符串，解析后通常含 `event` 与业务字段；业务负载中若含会话维度字段，会带 **`session_id`**，前端可按需过滤（同一条连接内应均为当前会话）。

### 3.3.1 事件 `approval_required`（人工审批）

**持久化（回放）**：每个 `approval_request_id` 在 `nanobot_agent_sse_events` 中**仅对应一条** `approval_required` 记录。首次下发时 `resolution` 为 **`null`**（待审批）；用户提交 `/agent/approve` 且工具侧处理完成后，服务端**就地更新**该条记录的 `data`：写入 `resolution`（`approved` / `rejected` / `mixed`）及可选的 `reject_reasons`。断线重连后按 `seq` 回放，**只会看到一条**含最终 `resolution` 的 `approval_required`（若重连发生在审批前，先看到 `null`，审批后再订阅则直接看到已更新后的单条）。

**在线推送**：除更新数据库外，服务端会向当前在线的 SSE 订阅者**再推送一条**同名的 `approval_required`（**不再次落库**，`persist=false`），结构与持久化中的 `data` 一致（含已填的 `resolution`）。前端可用同一 `approval_request_id` 合并状态：第二次推送用于立即关闭弹窗/展示结果，无需依赖重连。

| 字段 | 类型 | 说明 |
|------|------|------|
| `agent_id` | string | 分析引擎 ID |
| `session_id` | string | 会话 ID |
| `approval_request_id` | string | 本次审批请求 UUID |
| `resolution` | string \| null | **`null`**：待审批；**`approved`** / **`rejected`** / **`mixed`**：已决（回放里在同一条记录上更新） |
| `payload` | object | 内含 `entity_type`、`entity_uuid`、`modifications`、`reason`、`requested_at`、`session_id`、`approval_request_id` |
| `reject_reasons` | string[] \| null | 已决后可能为非空（拒绝理由列表） |

**前端建议**：以 `approval_request_id` 为 key；`resolution === null` 时打开/保持审批 UI；收到同 id 且 `resolution` 非空时关闭弹窗并展示结果（可结合 `reject_reasons` 与 `payload`）。在线时以第二次推送为准；重放时只解析每条记录的**最终** `data` 即可。

### 3.4 前端建议

- **每个运行中的会话一条 SSE 连接**（`agent_id` + `session_id` 唯一对应）；多会话并行时打开多条连接。  
- 断开页面或切换任务时关闭对应 `EventSource` / fetch 流，避免泄漏。

## 4. 提交审批：`POST {API_V1}/agent/approve`

### 4.1 变更要点

- 请求体必须包含 **`session_id`**，以指定待审批的会话。

### 4.2 请求 Body（`ApproveRequestSchema`）

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `agent_id` | string | 是 | 分析引擎 ID |
| `session_id` | string | 是 | 会话 ID，非空 |
| `decisions` | array | 是 | 审批决策列表（结构与后端约定一致） |

## 5. 取消运行：`POST {API_V1}/agent/cancel`

### 5.1 变更要点

- 请求体必须包含 **`session_id`**；仅取消**该会话**对应的后台任务，不影响同 Agent 其它会话。

### 5.2 请求 Body（`CancelAgentRequestSchema`）

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `agent_id` | string | 是 | 分析引擎 ID |
| `session_id` | string | 是 | 会话 ID，非空 |
| `reason` | string | 否 | 默认 `"user cancel"`，用于审计与日志 |

### 5.3 成功响应 `data`（`CancelAgentResponseSchema`）

| 字段 | 类型 | 说明 |
|------|------|------|
| `agent_id` | string | 同请求 |
| `cancelled` | boolean | 是否实际向后台发出了取消（无运行中任务时为 `false`） |

## 6. Agent 配置类接口的响应变更（列表/详情）

运行时状态（如运行中、步骤等）**不再挂在 Agent 文档上**，而落在会话集合中。

- **`GET {API_V1}/agent/agents`**、**`GET {API_V1}/agent/agents/{id}`** 等返回的 **`NanobotAgentSchema`**：仅含配置字段（`id`、`workspace_id`、`name`、`tools`、`skills`、`mcp_servers`、`llm_config` 等），**不含**会话级 `status` / `current_session_id` / `steps` 等。  
- **`GET {API_V1}/agent/agents-list`** 列表项仅 **`id` / `name` / `workspace_id`**。  
- 若前端曾用 Agent 上的 `status` 展示「是否在跑」，需改为：  
  - 由用户当前打开的 **`session_id`** 驱动；或  
  - 另接会话列表/详情接口（若产品后续提供）；或  
  - 通过 SSE `/status` 的 `session_id` 与事件推断。

## 7. 与旧版前端行为对照（迁移检查清单）

| 场景 | 旧行为（可能） | 新行为 |
|------|----------------|--------|
| 启动分析 | 仅依赖 `agent_id` 即可跟踪 | 必须保存并使用 **`session_id`** |
| SSE | 可能只传 `agent_id` | **必须**传 `agent_id` + **`session_id`** |
| 取消 | 可能只按 Agent 取消 | **必须**传 **`session_id`**，只取消该会话 |
| 审批 | 可能未区分会话 | **必须**传 **`session_id`** |
| 多任务并行 | 可能被后端互斥 | 同一 Agent **可多会话并行**（受环境变量上限约束） |
| Agent 列表展示运行态 | 读 Agent.`status` | Agent 响应**无**运行态，改由会话/SSE 驱动 |

## 8. 参考代码位置（后端）

| 内容 | 路径 |
|------|------|
| 运行时路由 | `app/api/v1/endpoints/agent/runtime.py` |
| 请求/响应 Schema | `app/schemas/agent/agent.py` |
| Agent 配置 Schema | `app/schemas/agent/nanobot_agent.py` |
| 并行上限配置 | `app/core/config.py` → `NANOBOT_AGENT_MAX_PARALLEL_SESSIONS` |

---

**文档版本**：与当前 `csi-back` 仓库并行会话实现一致；若路由前缀或字段再变更，请以 OpenAPI（`/docs`）或上述源码为准。
