# Agent 真并行多会话重构说明

## 1. 背景与目标

### 1.1 现状

- 每个 `NanobotAgentModel` 同时只允许一个后台分析任务；进程内以 `agent_id` 为键缓存 `Nanobot` 与 `asyncio.Task`。
- `steps`、`todos`、`pending_approval`、`result`、运行态 `status` 等写在 **Agent 文档**上；每次 `/start` 会清空 `steps` 等并生成新 `session_id`。
- SSE 按 `agent_id` 订阅；取消/审批等语义隐含「单活跃会话」。

### 1.2 目标

- **真并行**：同一 Agent 下可同时运行多个 `session_id`，互不阻塞（可另加每 Agent 或每租户并发上限）。
- **数据归属**：**会话级**状态（含 `steps` 等）迁移到 **Session** 持久化；**Agent** 仅保留配置及与单次运行无关的字段。

---

## 2. 设计原则

1. **编排主键**：运行时与 API 以 `session_id` 为第一公民；`agent_id` 用于鉴权、加载配置、列表过滤。
2. **Agent 文档**：不再承载「当前这一轮」的独占可变状态（避免并行写冲突）。
3. **向后兼容**：若需过渡期，对旧客户端的兼容策略单独成文（建议短期双轨 API，尽快收敛到必传 `session_id`）。
4. **资源边界**：并行仅扩展任务与连接数，需评估 LLM 并发、Mongo 写热点与进程内队列数量。

---

## 3. 数据库与模型

### 3.1 Agent 模型（`nanobot_agents`）保留字段（建议）

- 标识与归属：`id`、`workspace_id`、`name`、`description`
- 配置：`prompt_template_id`、`model_config_id`、`tools`、`skills`、`mcp_servers`、`llm_config`
- 可选聚合（非必须）：`active_session_count`、`last_activity_at`（由服务层维护）

### 3.2 Agent 模型待移除或弃用字段

- `status`（运行态）、`current_session_id`、`steps`、`todos`、`pending_approval`、`result`

> 若产品仍要列表页展示「Agent 是否忙」，用 Session 集合查询推导，或维护可选聚合字段，避免与多会话语义打架。

### 3.3 Session 模型（`nanobot_sessions`）新增或承接字段（建议）

- `status`：会话级枚举（如 `RUNNING` / `COMPLETED` / `FAILED` / `AWAITING_APPROVAL` / `CANCELLED`）
- `steps`：`list[dict]`（与现 `StatusHook` 结构对齐，可按需增加每条 `session_id` 冗余字段便于排障）
- `todos`、`pending_approval`、`result`
- 可选：`user_prompt`（或摘要）、`title`、`error_message`、`started_at`、`finished_at`

### 3.4 索引

- `("agent_id", "status", "updated_at")`：按 Agent 查活跃会话、列表页
- 已有 `(agent_id, created_at)` 等按需保留或补充

### 3.5 其他集合

- `nanobot_session_messages`：保持按 `session_id`，无需结构性变更。
- `nanobot_agent_sse_events` / `nanobot_agent_sse_event_state`：已为 `(agent_id, session_id)`，与多会话一致。
- Workspace 级 memory/history：仍按 `workspace_id`；注意多会话并行共享记忆的语义是否满足业务。

---

## 4. 服务层（`AnalystService`）

### 4.1 进程内结构改造

| 现状 | 目标 |
|------|------|
| `_running_tasks[agent_id]` | `_running_tasks[session_id]`（或等价唯一键） |
| `_bots[agent_id]` | `_bots[session_id]` |
| `_pending_resumes[agent_id]` | `_pending_resumes[session_id]` |
| `_cancel_reasons[agent_id]` | `_cancel_reasons[session_id]` |
| SSE 订阅者仅 `agent_id` | 支持按 `session_id` 过滤或分队列（见第 6 节） |

### 4.2 `build_bot`

- 生成 `session_id` 后：**写入/初始化 `NanobotSessionModel`**（`status`、`steps=[]` 等），**不再**在 Agent 上清空/写入运行态。
- 装配 `Nanobot.from_components` 逻辑可保留；每个并行会话各自持有一个实例。

### 4.3 `start_agent`

- 移除「Agent 处于 RUNNING 即拒绝」的全局互斥；改为可选：**每 Agent 最大并行数**、或租户级限流。
- 并发校验改为基于 **session 列表** 或计数。

### 4.4 `run_analysis`

- 开始/结束/异常时：**更新对应 `NanobotSessionModel`**（`status`、`result`、`error_message` 等）。
- Agent 文档仅在配置变更路径更新；不在每轮迭代写 Agent。

### 4.5 `cancel_agent` / `submit_approval` / `await_approval`

- 入参增加 **`session_id`（必填）**（或与 `agent_id` 组合唯一标识一次运行）。
- 取消：定位 `_running_tasks[session_id]` 并 cancel；更新该 session `status`。
- 审批：向 `_pending_resumes[session_id]` 投递，避免串台。

---

## 5. Hooks 与业务工具

### 5.1 Hooks（`app/service/analyst/hooks.py`）

- `StatusHook`：由「加载 Agent 追加 `steps`」改为「**按 `get_current_session_id()` 加载 Session** 追加 `steps` 并 `save`」。
- `TodosHook` / `ApprovalHook`：读写的 `todos`、`pending_approval`、`status` 均落在 **Session**。
- `ResultHook`：若有机读结果落库，与 `SubmitTaskResultTool` 一致改为写 **Session**。

### 5.2 业务工具（`app/service/analyst/tools.py` 等）

- 所有依赖 `get_current_agent_id()` 写回 Mongo 的路径，改为写 **当前 session**（`get_current_session_id()` 已存在，需与 Session 模型字段对齐）。
- 审批等待：`await_approval` 与队列键改为 `session_id`。

### 5.3 `ContextVar`

- 保持 `run_analysis` 内设置 `current_agent_id` / `current_session_id`；确保任意异步边界不丢失（已有模式可沿用）。

---

## 6. API 与 SSE

### 6.1 REST

- `POST /agent/start`：响应仍为 `session_id`；服务端允许多个未结束 session 并存。
- `POST /agent/cancel`：请求体增加 **`session_id`**。
- `POST /agent/approve`：请求体增加 **`session_id`**。
- 列表/查询接口（若有）：支持按 `agent_id` 列出 session 及 `status`。

### 6.2 SSE `GET /agent/status`

- 查询参数增加 **`session_id`（推荐必填）**：只推送该会话相关事件。
- 若需「订阅 Agent 下全部会话」：明确文档化并考虑事件负载；实现上可为多队列合并或单队列带 `session_id` 由客户端过滤。

---

## 7. Nanobot 核心（可选核对）

- `AgentLoop` / `MongoSessionStore`：已按 `session_id` 隔离消息，一般无需为并行改核心循环。
- `spawn` 子代理：确认 `session_key` 与父会话一致，避免子任务写入错误 session。
- 每会话一个 `Nanobot` 实例时，MCP 连接是否每实例一套需评估资源（可后续优化为共享连接池）。

---

## 8. 数据迁移

1. 脚本：对存量 `nanobot_agents` 若存在 `current_session_id` 且仍有运行态字段，将 `steps/todos/pending_approval/result/status` **合并写入**对应 `nanobot_sessions` 文档（仅当 session 仍存在且可对应）。
2. 清空 Agent 上已迁移字段（或保留只读 deprecated 字段一期后删）。
3. 记录迁移版本号与回滚说明（若需要）。

---

## 9. 测试与验收

- 单 Agent 连续两次 `/start` 不等待第一次结束：两次均 `RUNNING`，两条 session 文档独立更新。
- 交错 `steps`：两 session 的 `steps` 长度与内容互不污染。
- `cancel` 只影响目标 `session_id`，另一 session 继续运行。
- `approve` 只唤醒目标 session 的阻塞工具。
- SSE：带 `session_id` 的订阅不应收到其他会话事件（按选定实现验收）。
- 全量 `pytest` 通过（项目规则）。

---

## 10. 风险与待决

- **大文档**：单 session `steps` 过长可能导致 Mongo 单文档体积上升；预留拆表或归档策略。
- **共享记忆**：多会话并行写同一份 workspace memory 时的冲突与业务语义需产品确认。
- **前端**：列表、详情、SSE 连接数与取消入口需同步改造。

---

## 11. 实现进度 Todo List

以下为建议顺序；完成后将 `[ ]` 改为 `[x]`。

### 11.1 数据模型与迁移草案

- [x] 定稿 `NanobotSessionModel` 新增字段及 `NanobotAgentModel` 删除/弃用字段清单（见 `app/models/agent/nanobot.py`、`NanobotSessionStatusEnum`）
- [x] 补充 Beanie 索引（`agent_id` + `status` + `updated_at` 等，见 `NanobotSessionModel.Settings.indexes`）

### 11.2 服务层

- [x] `AnalystService`：`_running_tasks` / `_bots` / `_cancel_reasons` 改为以 `session_id` 为键
- [x] `AnalystService`：`_pending_resumes` 改为以 `session_id` 为键；`await_approval` / `submit_approval` 适配
- [x] `build_bot`：初始化 session 运行态，移除对 Agent 运行态字段的写入/清空
- [x] `start_agent`：移除单会话互斥；并行上限由环境变量 `NANOBOT_AGENT_MAX_PARALLEL_SESSIONS`（`app/core/config.py`，仅统计 `nanobot_sessions` 中 `status=running`；**0 表示不限制**）在 `build_bot` 前校验，超限抛 `CONFLICT_STATE`
- [x] `run_analysis`：起止与异常时更新 `NanobotSessionModel`，不再依赖 Agent 上的 `status/result/...`
- [x] `run_analysis` / `finally`：释放 `_bots` / `_running_tasks` 时使用 `session_id`

### 11.3 Hooks 与工具

- [x] `StatusHook`：改为读写 Session 的 `steps`
- [x] `TodosHook` / `ApprovalHook`：改为基于 Session 的 `todos` / `pending_approval` / `status`
- [x] `SubmitTaskResultTool`：机读结果仍经 `ContextVar`；**会话级 `result`/`status` 由 `run_analysis` finally 落库**（与收口语义一致）
- [x] `tools.py`：`modify_entity` / `write_todos` 等写 Session；不再写 Agent 运行态

### 11.4 API 与 Schema

- [x] `CancelAgentRequestSchema` / `ApproveRequestSchema`：`session_id` 必填（`app/schemas/agent/agent.py`）
- [x] `runtime.py`：cancel/approve 转发带 `session_id`
- [x] `GET /agent/status`：`session_id` 查询参数必填；`subscribe` / `broadcast_sse` 按 `(agent_id, session_id)` 分发
- [x] 对外 OpenAPI / 前端对接说明：`POST /agent/start` 路由已补充 `description`（`session_id` 后续用法、`NANOBOT_AGENT_MAX_PARALLEL_SESSIONS` 超限语义）；完整前端联调清单仍以接口/前端仓库为准

### 11.5 Agent 只读配置面

- [x] Agent 列表项：`NanobotAgentListItemSchema` 去掉 `status`；**「是否有活跃会话」**由 `AgentService._has_active_session` 查 `NanobotSessionModel`（`RUNNING` / `AWAITING_APPROVAL`）实现更新/删除保护
- [x] `app/schemas/agent/nanobot_agent.py` 中 `NanobotAgentSchema` / `from_doc` 与仅配置字段的 Agent 模型对齐

### 11.6 Nanobot 与边界情况

- [x] `spawn` / `session_key`：`SpawnTool.set_context(..., nanobot_session_id=...)` + `AgentLoop._set_tool_context` / `_LoopHook` 在每轮工具执行前刷新；`SubagentManager.spawn` 的 `session_key` 优先为 Nanobot `Session.id`，与 `cancel_by_session(session_id)`、`AnalystService.cancel_agent` 对齐（避免多会话均为 `cli:direct` 时子任务桶冲突）
- [x] MCP 资源：主会话 `AgentRunSpec.session_key` 已为 `session.id`；子代理 `AgentRunSpec` 使用 `workspace=self.workspace` 与 `session_key=sub:{父会话spawn的session_key}:{task_id}`（无父会话键时为 `sub:none:{task_id}`），便于工具落盘与 MCP 路径按子任务区分

### 11.7 测试

- [x] 调整 `tests/analyst/`、`tests/api/`、`tests/models/` 等与 session 维度、SSE、cancel/approve 契约一致
- [x] 可选补强：同一 Agent 双 session 的 **mock 级** 覆盖（`tests/analyst/test_dual_session_isolation.py`：`StatusHook` 按 `current_session_id` 隔离 `steps`；`cancel_agent` 仅对目标 session 调用 `cancel_by_session`）。端到端「真并行 LLM + steps + 单 cancel」仍为可选增强
- [x] 并行上限单测：`tests/analyst/test_parallel_session_cap.py`；子代理 runner：`tests/nanobot/agent/test_subagent_runner_session_key.py`
- [x] 全量执行 `python -m pytest tests` 并通过（959 passed）

### 11.8 收尾

- [x] Agent 文档已移除运行态字段（与 Beanie 模型一致；**无单独迁移脚本**）
- [ ] 团队内评审：并发上限、SSE 默认行为、共享 memory 语义

---

**文档版本**：已与 2026-05 代码落地同步（未完项见上文 `[ ]`）。
