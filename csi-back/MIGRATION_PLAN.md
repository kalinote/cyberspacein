# csi-nanobot-sdk → csi-back 集成迁移计划

> 本文档描述将 `csi-nanobot-sdk` 整体迁入 `csi-back` 后端（最终位置：`csi-back/app/service/nanobot/`），并将所有持久化从文件系统改为 MongoDB 的实施方案。项目迁移完成后不再保持与上游 nanobot 的同步。

---

## 一、目标与边界

### 1.1 总体目标

- 把当前 `csi-nanobot-sdk` 整包移入 `csi-back/app/service/nanobot/`，不作为外部依赖包使用。
- 全部持久化（配置、会话、记忆、历史、技能状态等）改为 MongoDB（Beanie/Motor），复用 `csi-back` 已有的数据库栈。
- 在 `csi-back` 层用 nanobot 完整替换 `app/service/agent/` 下的 LangChain 实现；对外 API 路径保留但**语义升级**：新增 Workspace/Agent CRUD，`/agent/start`、`/agent/status (SSE)`、`/agent/approve` 的行为参数化到 `agent_id` 粒度。
- 保留 LangChain 版已有的关键业务能力：多模型/模板/Agent 配置、HITL 审批、`write_todos`、SSE 实时状态、暂停/取消/恢复、结构化最终结果。
- **本期先跑通核心流程**：Skills DB 化、Sandbox、Tool 粒度权限、Dream 逻辑优化都留到后续迭代。

### 1.2 本期不做（后续迭代）

- Skills 独立 CRUD 与数据库化（本期仍用源码目录里的静态 md 文件）。
- Sandbox（workspace 工具先整体禁用，代码保留）。
- 跨 workspace 知识共享 / 全文检索召回。

### 1.3 Workspace / Agent 分层架构（核心变动）

引入两层业务域，取代原计划里"agent 即顶层域"的假设：

```
Workspace（最基本的域，代表一个专项任务领域）
  │
  │ 绑定（候选资源池）
  │   ├─ prompt_template_ids: list[str]       ← 多套可选系统提示词（来自 AgentPromptTemplateModel）
  │   ├─ model_config_ids: list[str]           ← 多套可选模型提供商（来自 AgentModelConfigModel）
  │   ├─ enabled_tools: list[str]              ← 白名单（工具）
  │   ├─ enabled_skills: list[str]             ← 白名单（技能）
  │   └─ enabled_mcp_servers: dict             ← 白名单（MCP 服务）
  │
  │ 共享（按 workspace_id 隔离）
  │   ├─ nanobot_memory_docs   (MEMORY/SOUL/USER)
  │   ├─ nanobot_history       (append-only 摘要条目)
  │   └─ nanobot_history_state (last_cursor / last_dream_cursor)
  │
  └─ 包含多个 Agent（多实例 Nanobot，可并行）
        │
        ├─ 从 workspace 资源池中各选一个：prompt_template_id / model_config_id
        ├─ tools/skills/mcp_servers 必须是 workspace 对应白名单的子集
        ├─ llm_config（temperature / max_tokens / reasoning_effort 等）
        ├─ 业务运行时状态直接挂在 Agent 上：
        │    status / current_session_id / steps / todos / pending_approval / result
        │
        └─ Session（每次 /start 新建一条，同一 agent 同时只跑 1 个）
              └─ Message 流（nanobot_session_messages，按 seq 递增）
```

关键约束：

- **记忆隔离粒度 = workspace**：同 workspace 下所有 agent 共享 MEMORY / history / cursor，可以跨多次任务、多个 agent 累积经验。
- **子集校验**：创建/更新 Agent 时，服务端强制校验其 prompt/model/tools/skills/mcp 选择必须是所属 workspace 的子集。
- **Session 语义 = 一次完整任务**：`/agent/start` 每次生成新的 `session_id`，`nanobot_sessions` 表会持续增长；`NanobotAgentModel.current_session_id` 始终指向最近一次 run。
- **nanobot_configs 全局配置表取消**：nanobot 的 `Config` 对象每次实例化时从 Workspace + Agent + 环境变量拼出来，不落库。

---

## 二、当前架构分析

### 2.1 csi-nanobot-sdk 侧：持久化落点清单

> 下表是接下来**每一项都要改成 MongoDB**（或清理掉）的完整清单。


| 模块             | 源文件                                                                | 当前落盘                                                      | 作用                                      | 迁移目标                                            |
| -------------- | ------------------------------------------------------------------ | --------------------------------------------------------- | --------------------------------------- | ----------------------------------------------- |
| 全局配置           | `nanobot/config/loader.py`                                         | `~/.nanobot/config.json`                                  | Providers / AgentDefaults / Tools / MCP | **取消全局配置集合与文件读取**：`Config` 每次实例化时从 Workspace + Agent + 环境变量动态拼装；`load_config` / `save_config` / `config.json` 相关文件读写代码直接删除 |
| 运行时路径派生        | `nanobot/config/paths.py`                                          | `~/.nanobot/{logs,media,...}`                             | 各子目录路径                                  | 大部分删除；仅保留媒体临时目录用于上传缓存                           |
| 会话             | `nanobot/session/manager.py`                                       | `{workspace}/sessions/{key}.jsonl`                        | 会话 metadata + messages                  | `nanobot_sessions` + `nanobot_session_messages`（按 `agent_id` 查询） |
| 长期记忆           | `nanobot/agent/memory.py::MemoryStore`                             | `{workspace}/memory/MEMORY.md`、`SOUL.md`、`USER.md`        | 长期事实 / 人格 / 用户画像                        | `nanobot_memory_docs`（**按 workspace_id 隔离**，同 workspace 下多 agent 共享） |
| 历史条目           | 同上                                                                 | `{workspace}/memory/history.jsonl`                        | append-only 摘要条目                        | `nanobot_history`（按 workspace_id 隔离）            |
| 游标             | 同上                                                                 | `.cursor` / `.dream_cursor`                               | 最新 cursor / Dream 已处理 cursor            | `nanobot_history_state`（`_id = workspace_id`）   |
| 记忆版本控制         | `nanobot/utils/gitstore.py`                                        | `{workspace}/.git` (dulwich)                              | 版本/line_ages                            | **清理（见 §4.2）**                                  |
| 技能             | `nanobot/agent/skills.py`                                          | `{workspace}/skills/*/SKILL.md` + 源码内置 `nanobot/skills/`* | SKILL.md + frontmatter                  | **本期仅保留源码内置目录**；workspace skills 不启用            |
| 定时任务           | `nanobot/cron/service.py`                                          | `{cron_dir}/store.json`+`action.jsonl`+lock               | 定时 job                                  | **清理（见 §4.1）**                                  |
| 工作区工具          | `nanobot/agent/tools/{filesystem,shell,search,notebook,web,spawn}` | 直接读写 workspace 文件                                         | 文件/命令/浏览/Web                            | **代码保留，默认全关**，等后续 sandbox                       |
| MCP 连接         | `nanobot/agent/tools/mcp.py` + `ToolsConfig.mcp_servers`           | 配置项                                                       | 外部 MCP 服务                               | 保留实现；配置项从 workspace/agent 拼装（workspace 存白名单，agent 存子集引用） |
| 工具/Skill 白名单   | 硬编码 `ToolsConfig`                                                  | 源码常量                                                      | 默认工具集                                   | 业务层由 `NanobotWorkspaceModel` 维护白名单，`NanobotAgentModel` 存子集；nanobot 侧注册工具时按 agent 级传入 |
| 运行时 checkpoint | `AgentLoop._set_runtime_checkpoint`                                | 写入 `session.metadata`                                     | 中断恢复                                    | 随 session 入库即可                                  |
| 业务运行时状态        | 原 LangChain 版 `AgentAnalysisSessionModel`                          | MongoDB                                                   | steps/todos/pending_approval/result     | **合并进 `NanobotAgentModel`**（见 §6）；利用"agent 同时只跑 1 session"的约束去掉独立表 |


### 2.2 csi-back 侧：LangChain 现状与业务能力

关键文件：`app/service/agent/{agent.py,tools.py,motor_checkpinter.py}`、`app/models/agent/{agent,configs,checkpoint}.py`、`app/api/v1/endpoints/agent.py`。

**迁移时保留**的能力（全部通过 nanobot + hook + 业务工具等价实现）：

1. 配置 CRUD：`AgentModelConfigModel` / `AgentPromptTemplateModel` / `AgentModel`（**保留**，与 nanobot 正交）。
2. 会话业务状态：`AgentAnalysisSessionModel`（**保留**，继续作为前端可见的 `status/steps/todos/pending_approval/result` 容器）。
3. 对外路由：`/agent/configs/`*、`/agent/agents`、`/agent/start`、`/agent/status (SSE)`、`/agent/approve`（**路径与响应不变**）。
4. HITL：`modify_entity` 审批。
5. `write_todos` 任务分解。
6. SSE 事件：`status / approval_required / result / message`。
7. 暂停 / 取消 / 恢复。
8. 结构化最终结果 `ResultPayloadSchema`。

**迁移时删除**的：

1. `motor_checkpinter.py`、`CheckpointModel`、`CheckpointWriteModel`（被 nanobot 自己的 session+checkpoint 机制取代）。
2. `app/service/agent/agent.py`（整个 langchain 版 `AgentService`）。
3. `app/service/agent/tools.py`（改写为 nanobot `BaseTool`）。
4. requirements 里 `langchain / langgraph / langchain-openai / langchain-core / langgraph.checkpoint.mongodb` 全部。

---

## 三、已对齐的设计决策


| 决策点                                      | 结论                                                                                                                         |
| ---------------------------------------- | -------------------------------------------------------------------------------------------------------------------------- |
| 存储选型                                     | 所有 nanobot 数据 → **MongoDB**（Beanie）；ES 维持不变只服务实体检索                                                                         |
| **分层架构**                                 | **Workspace → Agent → Session** 三层，详见 §1.3                                                                                 |
| **记忆隔离粒度**                               | **`workspace_key = workspace_id`**（按 workspace 隔离；同 workspace 下所有 agent 共享 MEMORY/history/cursor）                         |
| **全局配置集合**                               | **取消**；原 `nanobot_configs` 集合不再使用；`Config` 每次实例化时从 Workspace + Agent + env 拼出                                             |
| **业务运行时状态**                              | 合并进 `NanobotAgentModel`（status / current_session_id / steps / todos / pending_approval / result）；不单独建 `AgentAnalysisSessionModel` |
| **Session 生命周期**                         | `/agent/start` 每次生成新 `session_id`（`new_per_run`）；同 agent 同时只跑 1 个；`NanobotAgentModel.current_session_id` 指向最近一次         |
| **资源白名单 / 子集约束**                         | `NanobotWorkspaceModel` 存 prompt_template_ids / model_config_ids / enabled_tools / enabled_skills / enabled_mcp_servers；`NanobotAgentModel` 各字段必须是对应白名单的子集，服务端在 create/update 时强校验 |
| Dream 触发                                 | 默认关闭；**改为基于 token 预测触发**：`当前 prompt tokens + Dream 自身提示词 tokens ≥ context_window × 90%` 时强制执行一次 Dream                      |
| Cron                                     | **迁移前彻底清理**（模块、工具、测试、skill md 全删）                                                                                          |
| GitStore                                 | **迁移前彻底清理**（含 `annotate_line_ages`、`MemoryStore.git`、相关 command/skill/ignore 逻辑）                                           |
| workspace 工具（fs/exec/web/spawn/notebook） | 代码保留；默认全关；后续 sandbox 上线再放开                                                                                                 |
| builtin skills                           | 保留源码目录（`nanobot/skills/`*），**cron skill 一并删除**，`SkillsLoader` 只从源码内置目录读；workspace skill 不启用                                |
| Model Provider                           | 每个 Agent 实例化时从其绑定的 `AgentModelConfigModel` 读取 `base_url/api_key/model`，叠加 `NanobotAgentModel.llm_config`，映射到 nanobot 的 `AgentDefaults` |
| 目标路径                                     | `csi-back/app/service/nanobot/`，与现有 `app/service/agent/` 同级；迁入后删除旧 `agent/` 目录                                             |


### Dream 新触发策略（细化）

文件：`nanobot/agent/memory.py::Consolidator`、`Dream`、`AgentLoop`。

- `DreamConfig` 字段变更：  
  - 保留 `max_batch_size` / `max_iterations` / `model_override`。  
  - 删除 `interval_h` / `cron` / `build_schedule` / `describe_schedule`（跟 cron 一起走）。  
  - 新增 `force_trigger_ratio: float = 0.9`（可 agent 配置覆盖）。
- 在 `AgentLoop._process_message` 调用 `consolidator.maybe_consolidate_by_tokens` 之前新增一步 `dream.maybe_force_run(session)`：  
  - 估算 `current_prompt_tokens` + Dream Phase 1 提示词 tokens（提示词 tokens 预先 tokenize 一次缓存）。  
  - 若 `>= context_window_tokens × force_trigger_ratio`，同步执行一轮 Dream（仅处理到 `min(batch, unprocessed)` 条）。
- 保留 `Dream.run()` 语义，但调用入口从"定时 cron 驱动"改为"token 阈值驱动"。后续如果需要周期化，可以再在 service 层用 `asyncio.create_task` + `asyncio.sleep` 另起，跟 nanobot 内部 cron 解耦。

---

## 四、迁移前预清理（阶段 0）

> 本阶段在 csi-nanobot-sdk 内完成。完成标志：`pytest` 全绿、`nanobot_tester.py` 能跑通对话。

### 4.1 Cron 清理清单

**删除目录/文件**：

- `nanobot/cron/`（`__init__.py`、`service.py`、`types.py`）
- `nanobot/agent/tools/cron.py`
- `nanobot/skills/cron/`（整个 skill 目录）
- `nanobot/heartbeat/`（`__init__.py`、`service.py`——heartbeat 本质上依赖 cron）
- `nanobot/utils/evaluator.py`（"Post-run evaluation for background tasks (heartbeat & cron)"）
- 测试：`tests/cron/`、`tests/agent/test_loop_cron_timezone.py`、`tests/agent/test_heartbeat_service.py`、`tests/agent/test_evaluator.py`

**代码改点**：


| 文件                                         | 操作                                                                                                                                                                                                                                                         |
| ------------------------------------------ | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `nanobot/agent/loop.py`                    | 删 `from nanobot.agent.tools.cron import CronTool`；删 `from nanobot.cron.service import CronService`；`AgentLoop.__init__` 去掉 `cron_service` 参数；`_register_default_tools` 去掉 cron 分支；`_set_tool_context` 的遍历元组 `("spawn", "cron", "my")` 改成 `("spawn", "my")` |
| `nanobot/config/paths.py`                  | 删 `get_cron_dir`                                                                                                                                                                                                                                           |
| `nanobot/config/__init__.py`               | 导出列表去掉 `get_cron_dir`                                                                                                                                                                                                                                      |
| `nanobot/config/schema.py::DreamConfig`    | 删 `cron` 字段、`build_schedule`、`describe_schedule`；删 `interval_h` 的 `_HOUR_MS`；新增 `force_trigger_ratio: float = 0.9`                                                                                                                                         |
| `tests/config/test_dream_config.py`        | 按新 DreamConfig 字段改断言                                                                                                                                                                                                                                       |
| `tests/config/test_config_paths.py`        | 删 cron 目录相关用例                                                                                                                                                                                                                                              |
| `nanobot/agent/memory.py`                  | 注释 "heavyweight cron-scheduled" 改为 "token-threshold triggered"；按 §3 的触发策略重写 `Dream` 外层触发                                                                                                                                                                   |
| `nanobot/templates/AGENTS.md` / `TOOLS.md` | 删 cron 工具相关段落                                                                                                                                                                                                                                              |


**依赖清理**：  

- `requirements.txt` 删 `croniter>=6.0.0,<7.0.0`、`tzdata`（如果其它地方没用）。  
- `pyproject.toml` 暂无 cron 直接声明。

### 4.2 GitStore 清理清单

**删除文件**：

- `nanobot/utils/gitstore.py`
- `tests/utils/test_gitstore.py`
- `tests/agent/test_git_store.py`
- `tests/command/test_builtin_dream.py`（`/dream` 命令的 diff 渲染强依赖 git，整体删除；Dream 相关业务逻辑的测试已由 `tests/agent/test_dream.py` 覆盖）

**代码改点**：


| 文件                                                                                                  | 操作                                                                                                                                                                              |
| --------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `nanobot/agent/memory.py::MemoryStore`                                                              | 删 `self._git`、`@property git`、`_maybe_migrate_legacy_history` 里与 git 无关的保留即可                                                                                                    |
| `nanobot/agent/memory.py::Dream`                                                                    | 删 `annotate_line_ages` 参数 / `_STALE_THRESHOLD_DAYS` / `_annotate_with_ages`；Phase 1 提示词删 `stale_threshold_days`；`run()` 里删 `self.store.git.is_initialized()` + `auto_commit` 分支 |
| `nanobot/config/schema.py::DreamConfig`                                                             | 删 `annotate_line_ages` 字段                                                                                                                                                       |
| `nanobot/utils/helpers.py`                                                                          | `create_workspace_files` 里删除 `GitStore(...).init()` 那段                                                                                                                          |
| `nanobot/command/builtin.py`                                                                        | `cmd_dream` / `cmd_dream_revert` 的 git 读取分支全部简化：改成"展示 Dream 上次 analysis 文本 + 最近 N 条 history 条目"，不做 diff。具体实现可以保留命令名，但方法体改写                                                      |
| `nanobot/agent/tools/filesystem.py` / `search.py` / `skills/skill-creator/scripts/package_skill.py` | `.git` 仅作为要忽略的目录名字符串存在，保留字面量即可（那只是忽略规则）                                                                                                                                         |
| `nanobot/templates/AGENTS.md` / `TOOLS.md` / `MEMORY.md` 等                                          | 如有提"git"/"line ages"/"← Nd"的描述，一并删除或简化                                                                                                                                          |


**依赖清理**：  

- `requirements.txt` 删 `dulwich>=0.22.0,<1.0.0`。

### 4.3 其他一并清理（与后端集成无关的 CLI 残留）

`git status` 显示 CLI/API/部分 provider 已被用户删除（显示为 `D`）。本阶段顺手把 `nanobot/command/builtin.py` 里的 `cmd_restart`（调用 `os.execv`）删掉或改成 no-op，因为 `os.execv(sys.executable, ["-m", "nanobot", ...])` 在 csi-back 进程内调用会直接替换掉 FastAPI 进程，非常危险。

### 4.4 预清理验收

```powershell
# 在 .venv 里
.\.venv\Scripts\Activate.ps1
pytest -q
python .\nanobot_tester.py --message "hello"
```

要求：

- `pytest` 全绿（新删掉的模块测试自然也被移除，不是 skip）。
- `nanobot_tester.py` 单轮对话跑通，不再产生 `.git`、`cron/store.json`。

---

## 五、目标目录结构

整包迁入后，`csi-back` 长这样：

```
csi-back/
├─ app/
│  ├─ service/
│  │  ├─ nanobot/                     ← 整个 nanobot 源码（§4 清理后的版本）
│  │  │  ├─ __init__.py               ← 对外暴露 Nanobot / AgentHook 等
│  │  │  ├─ nanobot.py
│  │  │  ├─ agent/
│  │  │  │  ├─ loop.py
│  │  │  │  ├─ memory.py
│  │  │  │  ├─ context.py
│  │  │  │  ├─ runner.py
│  │  │  │  ├─ subagent.py
│  │  │  │  ├─ autocompact.py
│  │  │  │  ├─ skills.py
│  │  │  │  ├─ hook.py
│  │  │  │  └─ tools/               ← 文件工具全保留，默认不注册
│  │  │  ├─ providers/
│  │  │  ├─ session/manager.py
│  │  │  ├─ config/
│  │  │  ├─ command/
│  │  │  ├─ bus/
│  │  │  ├─ security/
│  │  │  ├─ utils/
│  │  │  ├─ skills/                  ← 源码内置 skill md（builtin）
│  │  │  ├─ templates/
│  │  │  └─ storage/                 ← 新增：存储抽象 + Mongo 实现
│  │  │     ├─ __init__.py
│  │  │     ├─ base.py               ← Protocol 定义
│  │  │     ├─ mongo_session.py       ← ConfigStore 不再需要
│  │  │     ├─ mongo_memory.py
│  │  │     └─ models.py              ← 不在这里放 Beanie Document（统一放在 app/models/agent/）
│  │  │
│  │  ├─ analyst/                     ← 替代旧 agent/，负责业务编排
│  │  │  ├─ __init__.py
│  │  │  ├─ service.py                ← AnalystService（启动/停止/审批/SSE + Workspace/Agent CRUD 编排）
│  │  │  ├─ workspace.py              ← Workspace CRUD / 资源子集校验逻辑
│  │  │  ├─ agent.py                  ← Agent CRUD（创建时做子集校验、更新时同步状态）
│  │  │  ├─ tools.py                  ← get_entity / modify_entity / notify_user / write_todos
│  │  │  ├─ hooks.py                  ← StatusHook / TodosHook / ApprovalHook / ResultHook（目标是更新 NanobotAgentModel）
│  │  │  ├─ context.py                ← ContextVar 绑定 agent_id / session_id / AnalystService 引用
│  │  │  ├─ prompt.py                 ← 结果格式约束、todo 提示词等
│  │  │  └─ result.py                 ← 最终 JSON 解析与兜底
│  │  └─ （旧 agent/ 目录删除）
│  │
│  ├─ models/
│  │  └─ agent/
│  │     ├─ nanobot.py                ← Workspace/Agent/Session/Message/Memory/History/HistoryState 七张表
│  │     ├─ configs.py                ← 保留 AgentModelConfigModel / AgentPromptTemplateModel
│  │     └─ checkpoint.py             ← 删除
│  │
│  ├─ api/v1/endpoints/agent.py       ← 接口升级：新增 /agent/workspaces/*、/agent/agents/*（CRUD），
│  │                                     保留 /agent/configs/*、/agent/start、/agent/status、/agent/approve
│  └─ ...
```

### 迁入注意

- `nanobot/__init__.py` 里保留 `from nanobot.nanobot import Nanobot, RunResult`，迁入后 import 路径变成 `from app.service.nanobot import Nanobot, RunResult`。需要批量改所有 `from nanobot.xxx` 为 `from app.service.nanobot.xxx`。
- 建议用一次性脚本做：`rg -l "^from nanobot\."` + `sd "from nanobot\." "from app.service.nanobot."`（或 IDE 全仓库替换）。
- `nanobot_tester.py` 继续放在 sdk 仓库根（迁入时**不**带走），改写 import 后仍可作为脚本级冒烟入口；csi-back 运行期不依赖它。

---

## 六、MongoDB 数据模型

全部以 `nanobot_` 前缀，避开 csi-back 已有命名空间。Beanie Document 统一放在 `app/models/agent/nanobot.py`，并在 `app/models/__init__.py::get_all_models()` 注册。

本期共 **7 个集合**（删除了原计划里的 `nanobot_configs`）：

```
nanobot_workspaces          业务：workspace 元数据 + 资源白名单
nanobot_agents              业务：agent 元数据 + 运行时状态（status/steps/todos/result 等）
nanobot_sessions            nanobot：会话元数据（每次 /start 新建一条）
nanobot_session_messages    nanobot：消息事件流（按 session_id + seq）
nanobot_memory_docs         nanobot：MEMORY/SOUL/USER 记忆文档（按 workspace_id 隔离）
nanobot_history             nanobot：append-only history 条目（按 workspace_id 隔离）
nanobot_history_state       nanobot：游标状态（_id = workspace_id）
```

### 6.1 集合设计

```text
# === 业务层 ===

nanobot_workspaces
  _id: str                       # workspace_id（业务生成）
  name: str                      # 展示名
  description: str | None
  prompt_template_ids: list[str] # 绑定的候选系统提示词（来自 AgentPromptTemplateModel）
  model_config_ids: list[str]    # 绑定的候选模型提供商（来自 AgentModelConfigModel）
  enabled_tools: list[str]       # 工具白名单（agent 只能从中选）
  enabled_skills: list[str]      # 技能白名单
  enabled_mcp_servers: dict      # MCP 服务白名单，key = server_name → MCPServerConfig dump
  created_at: datetime
  updated_at: datetime

nanobot_agents
  _id: str                        # agent_id
  workspace_id: str               # 索引，指向所属 workspace
  name: str
  description: str | None
  # 选定资源（必须是 workspace 对应字段的子集，创建/更新时强校验）
  prompt_template_id: str         # 必须 ∈ workspace.prompt_template_ids
  model_config_id: str            # 必须 ∈ workspace.model_config_ids
  tools: list[str]                # ⊆ workspace.enabled_tools
  skills: list[str]               # ⊆ workspace.enabled_skills
  mcp_servers: list[str]          # ⊆ workspace.enabled_mcp_servers.keys()
  llm_config: dict                # temperature / max_tokens / reasoning_effort 等
  # 运行时业务状态（原 AgentAnalysisSessionModel 的内容合并到这里）
  status: str                     # idle / running / awaiting_approval / paused / completed / failed
  current_session_id: str | None  # 最近一次 /start 的 session_id
  steps: list[dict]               # 步骤流水
  todos: list[dict]               # write_todos 结果
  pending_approval: dict | None   # 待审批载荷
  result: dict | None             # 最近一次 ResultPayloadSchema
  created_at: datetime
  updated_at: datetime

# === nanobot 内部（按 workspace 隔离） ===

nanobot_sessions
  _id: str                   # session_id（每次 /start 新生成）
  agent_id: str              # 索引，反查 agent → workspace
  workspace_id: str          # 索引（冗余但方便按 workspace 聚合）
  metadata: dict             # runtime_checkpoint / pending_user_turn / _last_summary
  last_consolidated_seq: int # 已合并到 history 的消息 seq 上限
  created_at: datetime
  updated_at: datetime

nanobot_session_messages
  session_id: str            # 与 seq 复合唯一
  seq: int                   # 递增序号
  role: str                  # user / assistant / system / tool
  content: Any               # str 或 list[dict]（含图片等多模态块）
  created_at: datetime
  # 可选字段（按 role 有选择性填充）
  sender_id: str | None
  injected_event: str | None
  subagent_task_id: str | None
  # assistant only
  tool_calls: list[dict]
  reasoning_content: str | None
  # anthropic only
  thinking_blocks: list[dict]
  # tool only
  tool_call_id: str | None
  tool_call_name: str | None

nanobot_memory_docs
  workspace_id: str          # 索引；与 type 复合唯一
  type: str                  # "memory" / "soul" / "user"（USER 后续可能下线，SOUL 语义可能调整为报告风格）
  content: str
  created_at: datetime
  updated_at: datetime

nanobot_history
  workspace_id: str          # 索引；与 cursor 复合唯一
  cursor: int                # 单调递增
  content: str
  created_at: datetime

nanobot_history_state
  _id: str                   # workspace_id
  last_cursor: int           # 已分配的最大 cursor
  last_dream_cursor: int     # Dream 已处理到的 cursor
  updated_at: datetime
```

### 6.2 索引

```python
# nanobot_workspaces
IndexModel([("name", ASCENDING)])

# nanobot_agents
IndexModel([("workspace_id", ASCENDING)])
IndexModel([("workspace_id", ASCENDING), ("name", ASCENDING)], unique=True)  # 同 workspace 下 agent 名称唯一
IndexModel([("status", ASCENDING)])

# nanobot_sessions
IndexModel([("agent_id", ASCENDING), ("created_at", DESCENDING)])
IndexModel([("workspace_id", ASCENDING)])
IndexModel([("updated_at", ASCENDING)])  # 可加 TTL expireAfterSeconds

# nanobot_session_messages
IndexModel([("session_id", ASCENDING), ("seq", ASCENDING)], unique=True)

# nanobot_memory_docs
IndexModel([("workspace_id", ASCENDING), ("type", ASCENDING)], unique=True)

# nanobot_history
IndexModel([("workspace_id", ASCENDING), ("cursor", ASCENDING)], unique=True)

# nanobot_history_state： _id 即 workspace_id，自动唯一
```

### 6.3 为什么 messages 独立成集合、其他不合并

- 会话消息会随对话增长（单次分析 agent 可能产生数百条 tool call/result），内嵌 `nanobot_sessions.messages` 会碰到 16 MB 上限；并且 `AgentLoop._save_turn` 是增量 append，独立集合更自然。`SessionManager` 内仍然把 messages 装到 `Session.messages: list[dict]` 给 `ContextBuilder` 用，只是读写由 Mongo backend 承担。
- 业务状态（status/steps/todos/result）合并进 `nanobot_agents` 是利用"**同一 agent 同时只跑 1 个 session**"这个新约束：运行时 UI 关心的就是"这个 agent 现在怎么样"，查 agent 一张表即可；历史 run 可以按需要再做归档（本期不做）。

### 6.4 业务子集校验（service 层）

`AnalystService.create_agent` / `update_agent` 在写入前必须校验：

```python
assert agent.prompt_template_id in workspace.prompt_template_ids
assert agent.model_config_id    in workspace.model_config_ids
assert set(agent.tools)       <= set(workspace.enabled_tools)
assert set(agent.skills)      <= set(workspace.enabled_skills)
assert set(agent.mcp_servers) <= set(workspace.enabled_mcp_servers.keys())
```

Workspace 更新时如果**收窄了白名单**（去掉了某 tool/skill/mcp/prompt/model），需要级联校验"是否有已存在的 agent 仍在引用"：有的话要么拒绝更新，要么把相关字段从 agent 里清掉（本期选"拒绝更新"，更保守）。

---

## 七、分阶段实施路径

### 阶段 0：预清理（sdk 仓库内）

见 §4。产出：干净的 nanobot 代码库，跑通 `pytest` 与 `nanobot_tester.py`。

### 阶段 1：整包迁入 csi-back

1. 拷贝 `nanobot/` → `csi-back/app/service/nanobot/`。
2. 全仓库 import 替换 `from nanobot.` → `from app.service.nanobot.`。
3. 合并依赖到 csi-back 的 `requirements.txt` / `pyproject.toml`：
  - 新增：`loguru`、`tiktoken`、`jinja2`、`pypdf`、`python-docx`、`openpyxl`、`python-pptx`、`json-repair`、`chardet`、`readability-lxml`、`filelock`、`mcp`、`ddgs`、`openai`、`anthropic`、`langfuse`（按 csi-back 实际需要裁剪；web 工具禁用后 `ddgs/readability-lxml` 可不要）。
  - 注意 `anthropic` / `openai` 如果 csi-back 已有就对齐版本。
4. **不要**拷贝 `nanobot_tester.py`、`pyproject.toml`、`requirements*.txt`、`tests/`；这些留在 sdk 仓库作参考。tests 的迁移见阶段 6。
5. 在 csi-back 的 `.venv` 里 `pip install -r requirements.txt` 验证不报 import 错误。
6. 暂时不接入业务，验证 `app/service/nanobot/` 能被 import、语法与依赖正常即可；冒烟运行推迟到阶段 2 用 Mongo backend 跑。

**产出**：`app/service/nanobot/` 可以脱离 csi-back 其他部分独立实例化。

### 阶段 2：Mongo 存储 + 彻底去文件化

这一步**不动业务**，目标是把 §2.1 清单里所有文件 I/O **直接替换为 Mongo 版本**，不做"文件 + Mongo 双后端"的兼容层，存量文件路径相关代码（含 `~/.nanobot/`、workspace 目录下的 `sessions/` / `memory/` / `.cursor` / `.dream_cursor` / 历史迁移 `_maybe_migrate_legacy_history` / `legacy_sessions_dir` 等）一律删除。

Protocol 接口层的定义仍然保留，一方面给 `SessionManager` / `MemoryStore` 解耦于具体的 Beanie Document 调用（便于后续写单测时用 in-memory fake），一方面沿用 Python 惯例不让 nanobot 内部直接 import `app.models.*`。

#### 2.1 定义 Protocol（`app/service/nanobot/storage/base.py`）

```python
class SessionStore(Protocol):
    async def load(self, session_id: str) -> Session | None: ...
    async def save(self, session: Session) -> None: ...
    async def list_by_agent(self, agent_id: str) -> list[dict]: ...
    async def invalidate(self, session_id: str) -> None: ...  # 内存缓存失效，默认 no-op

class MemoryBackend(Protocol):
    # 注意：workspace_key 的实际取值是 workspace_id（不是 agent_id，也不是 session_id）
    async def read_doc(self, workspace_id: str, doc_type: str) -> str: ...
    async def write_doc(self, workspace_id: str, doc_type: str, content: str) -> None: ...
    async def append_history(self, workspace_id: str, entry: str) -> int: ...
    async def read_unprocessed_history(self, workspace_id: str, since_cursor: int) -> list[dict]: ...
    async def compact_history(self, workspace_id: str, max_entries: int) -> None: ...
    async def get_cursors(self, workspace_id: str) -> tuple[int, int]: ...  # (last_cursor, last_dream_cursor)
    async def set_dream_cursor(self, workspace_id: str, cursor: int) -> None: ...
```

> `SessionManager` 当前接口是同步的（`get_or_create/save`），但 `AgentLoop` 使用时已经在协程上下文。**改造时把 `SessionManager.save/_load/list_sessions` 一次性改 async**，对应调用点统一 `await`。这是本期工作量最大的一处改动。

> `SessionManager.get_or_create(key)` 的语义要从"按 key 懒加载"改成"按 session_id 精确加载 / create_new(agent_id) 新建"。`/agent/start` 每次走 create_new，不再复用同一 key。

#### 2.2 改 nanobot 内部调用链

- `nanobot/config/loader.py`：**删除** `load_config` / `save_config` / `resolve_config_env_vars` 等所有文件读取逻辑；只保留 `Config` / `ProviderConfig` / `AgentDefaults` 等 pydantic schema 定义（`config/schema.py`），让 `AnalystService.build_bot` 直接 `Config(...)` 构造。
- `nanobot/session/manager.py::SessionManager`：**删除** `workspace` / `sessions_dir` / `legacy_sessions_dir` / `_get_session_path` / `_get_legacy_session_path` / `_load` 文件版本 / `save` 文件版本 / `list_sessions` 目录扫描；重写为直接委托给 `SessionStore`；`_cache` 保留（内存层 LRU）；所有读写改 async；`get_or_create(key)` 拆成 `load(session_id)` 与 `create(agent_id, workspace_id) -> Session`。
- `nanobot/agent/memory.py::MemoryStore`：**删除** `memory_dir` / `memory_file` / `history_file` / `legacy_history_file` / `soul_file` / `user_file` / `_cursor_file` / `_dream_cursor_file` / `_maybe_migrate_legacy_history` 等所有 Path 字段；所有 `.read_text` / `.write_text` / `open(...).write` 改走 `MemoryBackend`；`append_history` 改 async。
- `nanobot/agent/loop.py`：`_save_turn` / `consolidator.maybe_consolidate_by_tokens` / `_schedule_background` 的调用点统一走 async。
- `nanobot/agent/context.py::ContextBuilder`：`build_system_prompt` 里 `self.memory.read_memory()` 等也要改 async（或让 ContextBuilder 自己缓存"一次对话期内的 memory snapshot"，减少阻塞）。**推荐后者**：`ContextBuilder.refresh_memory_snapshot()` 在 `_process_message` 入口先 await 一次，后续同步读快照。

#### 2.3 Beanie Document 与实现

- `app/models/agent/nanobot.py`：按 §6 定义 **7 个 Document**（Workspace/Agent/Session/Message/Memory/History/HistoryState）。
- `app/service/nanobot/storage/mongo_session.py` / `mongo_memory.py`：直白的 CRUD 封装，依赖 `app/models/agent/nanobot.py` 里的 Document。
- `app/models/__init__.py::get_all_models()`：把 7 个新 Document 加进列表，旧的 `CheckpointModel` / `CheckpointWriteModel` 删掉。

#### 2.4 `Nanobot` 入口

新增构造器：

```python
class Nanobot:
    @classmethod
    def from_components(
        cls,
        config: Config,
        *,
        session_store: SessionStore,
        memory_backend: MemoryBackend,
        agent_id: str,
        workspace_id: str,                     # 记忆隔离维度
        session_id: str,                       # 每次 run 由 AnalystService 分配
    ) -> "Nanobot":
        ...
```

**`from_config` 直接删除**（它依赖 `load_config` + 文件 SessionManager，已一并删除）。`app/service/nanobot/nanobot.py` 里 `Nanobot` 只暴露 `from_components` 一种构造方式，`_make_provider` 私有函数里对 `config_path` 的引用也清理掉。本地冒烟脚本改为在 csi-back 的 `.venv` 下连真实 Mongo，直接 `from_components(...)` 跑。

**产出**：`Nanobot.from_components(...)` 能用 MongoDB 跑一条会话，消息/记忆/历史落到 Mongo。文件系统完全不使用。

### 阶段 3：业务 Service 层

在 `app/service/analyst/` 里重建 LangChain 版的全部业务能力，并**新增 Workspace / Agent 的完整 CRUD**。

#### 3.1 AnalystService（`service.py` + `workspace.py` + `agent.py`）

**3.1.1 Workspace CRUD（`workspace.py`）**

- `create_workspace(name, description, prompt_template_ids, model_config_ids, enabled_tools, enabled_skills, enabled_mcp_servers)`：
  - 校验 `prompt_template_ids` / `model_config_ids` 在对应表里存在。
  - 校验 `enabled_tools` / `enabled_skills` 在系统支持列表里（工具来自 nanobot 注册表 + 业务工具；skills 来自 `nanobot/skills/` 目录）。
  - 写入 `NanobotWorkspaceModel`。
- `update_workspace(...)`：支持字段修改；如果收窄白名单，要先校验"没有 agent 仍在引用"，否则拒绝。
- `list_workspaces` / `get_workspace` / `delete_workspace`（删除前校验没有 agent 关联）。

**3.1.2 Agent CRUD（`agent.py`）**

- `create_agent(workspace_id, name, description, prompt_template_id, model_config_id, tools, skills, mcp_servers, llm_config)`：
  - 拉出所属 workspace → 做 §6.4 列的 5 个子集校验。
  - 写入 `NanobotAgentModel`，初始 `status=idle / current_session_id=None / steps=[] / todos=[] / pending_approval=None / result=None`。
- `update_agent(...)`：改动资源字段时同样做子集校验；`status/current_session_id/steps/...` 等运行时字段**只由 AnalystService 内部修改**，不开放对外编辑接口。
- `list_agents(workspace_id=None)` / `get_agent` / `delete_agent`（运行中的 agent 拒绝删除）。

**3.1.3 运行时编排（`service.py`）**

替换旧 `AgentService`：

```python
class AnalystService:
    _bots: dict[str, Nanobot] = {}               # key = agent_id，仅在运行期间存活
    _bots_lock = asyncio.Lock()
    sse_subscribers: dict[str, list[asyncio.Queue]] = {}  # key = agent_id
    sse_lock = asyncio.Lock()
    running_tasks: dict[str, asyncio.Task] = {}           # key = agent_id
    task_lock = asyncio.Lock()
    cancel_reasons: dict[str, str] = {}                   # key = agent_id
    pending_resumes: dict[str, asyncio.Queue] = {}        # key = agent_id

    @classmethod
    async def build_bot(cls, agent: NanobotAgent, workspace: NanobotWorkspace) -> tuple[Nanobot, str]:
        """构造 Nanobot 实例并分配新 session_id。返回 (bot, session_id)。"""
        ...

    @classmethod
    async def start_agent(cls, agent_id: str, user_prompt: str, context: dict | None = None) -> str:
        """/agent/start 入口：拉 agent+workspace → build_bot → run_analysis（后台）→ 返回 session_id。"""
        ...

    @classmethod
    async def run_analysis(cls, agent_id: str, session_id: str, bot: Nanobot, user_prompt: str): ...

    @classmethod
    async def broadcast_sse(cls, agent_id: str, payload): ...
```

- `build_bot` 做这几件事（每次 /start 都重新构造，不做跨 run 缓存）：
  1. 拉 agent 绑定的 `AgentModelConfigModel` → `base_url/api_key/model`；叠加 `agent.llm_config`。
  2. 拉 agent 绑定的 `AgentPromptTemplateModel` → `system_prompt`。
  3. 构造 nanobot `Config` 对象（不落库）：只填 `providers.openai_compat` / `agents.defaults` / `tools.mcp_servers`（按 agent.mcp_servers 从 workspace.enabled_mcp_servers 里挑子集）。
  4. 生成新 `session_id`（`generate_id()`），更新 `agent.current_session_id` 并重置运行时字段（steps/todos/pending_approval/result 清空，status=running）。
  5. `Nanobot.from_components(config, session_store=mongo_session_store, memory_backend=mongo_memory_backend, agent_id=agent.id, workspace_id=workspace.id, session_id=session_id)`。
  6. 注入 hooks + 业务工具（见 3.2/3.3），业务工具里通过 `agent.tools/skills/mcp_servers` 动态过滤。

#### 3.2 Hooks（`hooks.py`）

- `StatusHook`：`before_execute_tools` / `after_iteration` 里把 step 写入 **`NanobotAgentModel.steps`** 并 SSE 广播 `status`。
- `TodosHook`：响应 `write_todos` 工具调用结果，把新 todos 同步到 **`NanobotAgentModel.todos`**。
- `ApprovalHook`：在工具执行之前不能 skip（nanobot 没提供原生接口），**审批逻辑放进工具本身**（见 3.3），Hook 只负责 SSE 的 `approval_required` 广播与 `pending_approval` 字段清理。
- `ResultHook`：`on_run_complete`（或读 `RunResult.content`）里解析最终 JSON → `ResultPayloadSchema`；广播 `result`；落到 **`NanobotAgentModel.result`**，同时 `status=completed/failed`。

所有 Hook 写库目标都统一到 `NanobotAgentModel`（按 `agent_id`）。

#### 3.3 业务工具（`tools.py`）

用 nanobot `BaseTool`（见 `nanobot/agent/tools/base.py`）重写：


| 工具                 | 说明                                                                                                                                                                                                                                                                        |
| ------------------ | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `get_current_time` | 直接返回时间字符串，无状态。                                                                                                                                                                                                                                                            |
| `get_entity`       | 从 `contextvars` 拿不到可以省略 agent_id；直接复用 `get_es()`。                                                                                                                                                                                                                         |
| `modify_entity`    | **在 `execute()` 里完成审批握手**：`contextvars` 取 `agent_id` → 更新 `NanobotAgentModel.status=awaiting_approval` + `pending_approval=payload` → SSE `approval_required` → `await AnalystService.pending_resumes[agent_id].get()` → 按决策走 approve/reject 分支。无需改 nanobot 核心。           |
| `notify_user`      | SSE 广播 `message`；`agent_id` 也从 `contextvars` 拿。                                                                                                                                                                                                                           |
| `write_todos`      | 参数 `todos: list[{content, status}]`；写 `NanobotAgentModel.todos` + SSE `status`。                                                                                                                                                                                          |


上下文注入方式：`app/service/analyst/context.py` 定义 `current_agent_id: ContextVar[str]` 和 `current_session_id: ContextVar[str]`，`AnalystService.run_analysis` 在 await `bot.run(...)` 外层 set，finally 里 reset。

> 对外 API 的 `thread_id` 参数本期直接替换为 `agent_id`；SSE 订阅也按 `agent_id` 分发。`session_id` 作为只读字段在 SSE 事件里返回给前端用于调试。

#### 3.4 系统提示装配（`prompt.py`）

- `TODO_MIDDLEWARE_SYSTEM_PROMPT` / `TOOL_DESCRIPTION` / `RESULT_FORMAT_INSTRUCTION` 平移。
- Agent 的最终 system prompt = `AgentPromptTemplateModel.system_prompt` + todo 段 + 结果格式段。
- 初期直接在 `AnalystService.start_agent` 拼好后塞进 `Config.agents.defaults` 是不行的（nanobot 的 system prompt 来自 `ContextBuilder` + workspace 里 `AGENTS.md`）。两个选择：
  - **A. 覆盖方案**：在 `ContextBuilder.build_system_prompt` 追加一个 `extra_system_suffix`；AnalystService 启动时设置。
  - **B. 首条 user 消息注入**：把业务 system 文本拼在 user_prompt 前面。鲁棒性差，跳过。
- 推荐 A，改动量小。

#### 3.5 结构化结果（`result.py`）

- 优先走 provider 的 `response_format: json_schema`（OpenAI 兼容）：在 `OpenAICompatProvider.chat_with_retry` 现有 `extra_kwargs` 透传路径上，`AnalystService` 构造时传 `response_format={"type":"json_schema","json_schema":{"name":"result","schema": ResultPayloadSchema.model_json_schema(), "strict": True}}`。
- 不支持的 provider 兜底：`json_repair.loads(RunResult.content)` → `ResultPayloadSchema(**parsed)`；失败填 `summary=raw, success=False, failure_reason="格式异常"`。

### 阶段 4：路由切换

- `app/api/v1/endpoints/agent.py`：
  - **新增**：`/agent/workspaces` CRUD（create / list / get / update / delete）。
  - **新增**：`/agent/agents` CRUD（create / list / get / update / delete，支持按 `workspace_id` 过滤）。
  - **保留**：`/agent/configs/models/*`、`/agent/configs/prompt-templates/*`（已经在用）。
  - **重写**：`/agent/start`（入参改为 `agent_id + user_prompt + 可选业务上下文`）、`/agent/status?agent_id=...`（SSE）、`/agent/approve`（body 用 `agent_id`）。
- SSE 订阅按 `agent_id` 分发（`AnalystService.sse_subscribers`）。
- `/agent/approve` 的 `pending_resumes[agent_id].put_nowait(...)` 由新的 `modify_entity` 工具端消费。
- `/agent/configs/tools`、`/agent/configs/tools-list`：返回系统级支持的工具/技能/MCP 清单（而不是具体 agent 的），供前端创建 workspace 时选白名单用。

### 阶段 5：彻底移除 LangChain

- 删文件：`app/service/agent/agent.py`、`app/service/agent/tools.py`、`app/service/agent/motor_checkpinter.py`、`app/models/agent/checkpoint.py`、`app/service/agent/__init__.py`（若无其它引用），最后删除 `app/service/agent/` 目录。
- `app/models/__init__.py` 去掉 `CheckpointModel` / `CheckpointWriteModel`。
- `app/utils/agent.py` 里的 `parse_approval_decision`、`modify_entity_approval_description`、`normalize_todo`、`update_session_status`、`get_step_detail`、`inject_template_fields`：保留（`AnalystService` 还会用到）；删除只服务 langchain 的部分（如果有）。
- MongoDB 侧 drop 旧集合：`agent_checkpointer`、`agent_checkpointer_writes`。`agent_analysis_sessions` **保留**（模型同名，向前兼容即可；本期用户说允许数据重置）。
- requirements：删 `langchain`* / `langgraph*`。

### 阶段 6：测试迁移与回归

- **现状（2026-04）**：旧版 nanobot 中与「总线调度、统一 session、文件型 session、AutoCompact、旧 Consolidator/Dream/MemoryStore 文件路径」强耦合的 `tests/nanobot/**` 用例已**整文件删除**；与新版仍兼容的部分（Provider、多数 tools、security、config 插值等）保留。新架构覆盖按本文 **§12** 清单在 `tests/models/`、`tests/nanobot/` 下**分批新增**（见 TODO #25）。
- 已从仓库移除的 nanobot 单测文件（非穷举，便于审计）：`test_auto_compact.py`、`test_unified_session.py`、`test_task_cancel.py`、`test_session_manager_history.py`、`test_runner.py`、`test_loop_save_turn.py`、`test_loop_consolidation_tokens.py`、`test_consolidator.py`、`test_dream.py`、`test_memory_store.py`、`test_consolidate_offset.py`、`test_context_prompt_cache.py`、`test_hook_composite.py`、`cli/test_restart_command.py`、`test_mcp_connection.py`。
- **辅助**：`tests/nanobot/fakes.py` 提供 `FakeMemoryBackend` / `FakeSessionStore`，供仍依赖 `AgentLoop` 构造的轻量用例（如 `tools/test_search_tools.py`）在无 Mongo 时注入。
- 后续：按 §12.3 起继续补 MongoSessionStore / MongoMemoryBackend 等集成单测；全链路 `AnalystService` 集成测试另立 `tests/.../test_analyst_flow.py`（待排期）。

---

## 八、关键技术点补充说明

### 8.1 SessionManager 同步→异步

现状：`SessionManager.get_or_create / save / _load` 是同步的；`AgentLoop._save_turn` 在 tool loop 热路径里同步调用 `self.sessions.save(session)`。

改造后这些调用都要 `await`。影响点（grep `self.sessions.save` / `self.sessions.get_or_create`）：

- `nanobot/agent/loop.py`：约 10+ 处。
- `nanobot/agent/autocompact.py::AutoCompact.prepare_session / check_expired`。
- `nanobot/command/builtin.py::cmd_status` 等命令处理器。
- `nanobot/agent/memory.py::Consolidator.maybe_consolidate_by_tokens`。

`check_expired` 当前被 `AgentLoop.run()` 主循环调用（非 async 回调），改造方案：

- csi-back 里我们不跑 `AgentLoop.run()` 这个 bus 主循环，而是直接用 `process_direct` / `bot.run()` 单次调用。`check_expired` 这条路径本期**可以不管**（等到需要多会话 TTL 时再做）。
- 直接删除 `AgentLoop.run()` 整个方法，让这个类只服务"一次 run 一条请求"模式（csi-back 不需要 bus + 主循环）。

### 8.2 `AgentLoop` 的 Bus/主循环是否保留

`AgentLoop.run()` + `_dispatch()` 用 `MessageBus` 做异步队列，是给 CLI/IM 等场景用的；csi-back 的 agent 是 per-request、短生命周期，不需要消息总线。

方案：

- 保留 `MessageBus` 类（`nanobot/bus/queue.py`），`process_direct` 内部仍用它发事件。
- 删除 `AgentLoop.run()` / `_dispatch()` / `_pending_queues` 路由（它们服务 bus 主循环）；保留 `_process_message` / `process_direct`。
- 删除 `nanobot/command/builtin.py::cmd_stop` / `cmd_restart`；`cmd_status` 可保留，但不再被 slash 触发，改成 `AnalystService` 内部的诊断 helper。

### 8.3 取消/暂停/恢复

- 取消：`task.cancel()`；`_process_message` 的 `asyncio.CancelledError` 分支已经做了 runtime_checkpoint 的持久化，因此下一次同 `session_key` 进来会自动恢复——只要 Mongo session store 工作正常。
- 暂停：业务上等同于取消 + 设置 `status=paused`；下次调 `/agent/start?thread_id=...` 用同 thread_id 即可恢复。
- 恢复接口：需要新增一个"续跑"路由（或复用 `/agent/start` 支持传 `thread_id` 不传 `entity_uuid`）。本期**不做**，作为后续迭代。本期 `cancel_reasons=='pause'` 仍写 `status=paused`，前端展示静态，要重跑需要用户手动发起新任务。

### 8.4 Context 上下文估算 + Dream 强制触发

```python
# nanobot/agent/memory.py::Dream
async def maybe_force_run(self, session) -> bool:
    prompt_tokens, _ = self._consolidator.estimate_session_prompt_tokens(session)
    dream_prompt_tokens = self._cached_dream_prompt_tokens()      # 预 tokenize 一次
    threshold = int(self._context_window_tokens * self._force_trigger_ratio)
    if prompt_tokens + dream_prompt_tokens < threshold:
        return False
    if not self.store.read_unprocessed_history(...):
        return False
    await self.run()
    return True
```

调用点：`AgentLoop._process_message` 在 `await self.consolidator.maybe_consolidate_by_tokens(session, ...)` 之后再 `await self.dream.maybe_force_run(session)`（让 Consolidator 先把消息压进 history，再让 Dream 把 history 整理到 MEMORY）。

### 8.5 Skills 只读 builtin

阶段 0 清理后 `nanobot/skills/` 仅剩非 cron 的源码 md。`SkillsLoader` 改动：

- `__init__` 不再接收 workspace skills 目录（只留 builtin）。
- `list_skills` / `load_skill` 只扫 builtin。
- `workspace_skills` 属性删除。
- `Dream._build_tools` 里 `WriteFileTool(allowed_dir=skills_dir)` 的"允许 Dream 写 workspace skills"这条分支**本期去掉**（Dream 只写 MEMORY/SOUL/USER）。这里要同时更新 Phase 2 提示词模板去掉 skill 写入指令。

---

## 九、风险与回滚


| 风险                                                      | 缓解                                                                                                      |
| ------------------------------------------------------- | ------------------------------------------------------------------------------------------------------- |
| `SessionManager` 改 async 引发大面积调用点修改                     | 每改一个文件就跑 `pytest tests/agent/` 定点回归，最后全量跑                                                               |
| Dream 强制触发引入额外 LLM 延迟                                   | 设上限 `max_batch_size=10`；`force_trigger_ratio` 可 per-agent 调                                             |
| OpenAI 兼容 provider 对 `response_format=json_schema` 支持不一 | 按 provider spec 判定；不支持时 fallback 文本 + `json_repair`                                                     |
| MongoDB 大量小文档写入压力                                       | 开 connection pool（csi-back 已有 `maxPoolSize=50`）；`session_messages` 按 `(session_key, seq)` 复合索引，单会话写入量可控 |
| 旧 LangChain 集合残留                                        | 阶段 5 里显式 drop，文档里列出命令                                                                                   |
| 迁移期线上不可用                                                | 迁移在 feature branch 进行，合并前灰度跑 `/agent/start` 压测                                                          |


回滚策略：阶段 0/1/2 都在独立 feature 分支；阶段 4 切路由前保留 `AgentService` 原文件直到下一个 sprint。一旦出问题，revert 到阶段 4 之前即可。

---

## 十、验收标准

本期完成条件：

1. `csi-back` 启动时仅依赖 MongoDB / ES / Redis / MariaDB / RabbitMQ（与现状一致），**不**写任何 nanobot 相关文件（`~/.nanobot`、`workspace/`、`memory/`、`skills/` 都不出现）。
2. `POST /agent/start` → 走 nanobot agent → SSE 正常推送 `status / approval_required / message / result`。
3. `POST /agent/approve` 能让 `modify_entity` 按决策继续或拒绝。
4. `AgentAnalysisSessionModel` 在 MongoDB 中能看到 `steps / todos / pending_approval / result` 正确更新。
5. 同一 `agent_id` 跨两次 `/agent/start` 能看到 `nanobot_memory_docs` 累积（即 agent 级记忆生效）。
6. 删除了所有 langchain / langgraph / cron / git / heartbeat / evaluator 代码与依赖。

---

## 十一、TODO（建议拆成独立 commit 的颗粒度）


| #   | 内容                                                                                               | 阶段     | 状态   | 预估影响文件数 |
| --- | ------------------------------------------------------------------------------------------------ | ------ | ---- | ------- |
| 1   | 清理 cron 模块、工具、测试、skill、模板、依赖                                                                     | 阶段 0   | 完成   | ~20     |
| 2   | 清理 GitStore、Dream 注释与 `annotate_line_ages`、dulwich 依赖                                            | 阶段 0   | 完成   | ~10     |
| 3   | 清理 heartbeat、evaluator、`cmd_restart`                                                             | 阶段 0   | 完成   | ~8      |
| 4   | 清理后回归：`pytest` + `nanobot_tester.py`                                                             | 阶段 0   | 完成   | 0       |
| 5   | nanobot → `csi-back/app/service/nanobot/` 整包拷贝 + import 替换                                       | 阶段 1   | 完成   | all     |
| 6   | 合并 python 依赖到 csi-back                                                                           | 阶段 1   | 完成   | 1       |
| 7   | 定义 7 张 Beanie Document（Workspace / Agent / Session / Message / Memory / History / HistoryState） | 阶段 2   | 完成   | 2       |
| 8   | `get_all_models()` 注册新 Document；删除旧 `CheckpointModel`                                            | 阶段 2   | 完成   | 2       |
| 9   | 定义 storage Protocol（SessionStore / MemoryBackend，不含 ConfigStore）                                 | 阶段 2   | 完成   | 1       |
| 10  | Mongo 实现（`mongo_session.py` / `mongo_memory.py`）                                                 | 阶段 2   | 完成   | 2       |
| 11  | `SessionManager` 改 async + 对接 SessionStore；`get_or_create` 语义改 `load/create`                    | 阶段 2   | 完成   | ~6      |
| 12  | `MemoryStore` / `Consolidator` / `Dream` 改 async + 对接 MemoryBackend                              | 阶段 2   | 完成   | ~4      |
| 13  | `ContextBuilder.refresh_memory_snapshot` 异步快照                                                    | 阶段 2   | 完成   | ~2      |
| 14  | `AgentLoop` 调用点全部 await；删除 `run/_dispatch` 主循环与 slash 命令多余分支                                    | 阶段 2   | 完成   | ~5      |
| 15  | Dream 改阈值触发 + `DreamConfig` 字段调整                                                                 | 阶段 2   | 完成   | ~3      |
| 16  | `Nanobot.from_components(agent_id, workspace_id, session_id, ...)` 新构造器                          | 阶段 2   | 完成   | 1       |
| 17  | **Workspace Service** + CRUD 接口 + 白名单收窄级联校验                                                     | 阶段 3   | 完成   | ~4      |
| 18  | **Agent Service** + CRUD 接口 + 子集校验                                                              | 阶段 3   | 完成   | ~4      |
| 19  | `AnalystService`（build_bot / start_agent / run_analysis / SSE / approve），业务状态写入 `NanobotAgentModel` + `ContextBuilder.extra_system_suffix` + `/start`/`/status`/`/approve` 路由 | 阶段 3 | 完成 | ~3 |
| 20  | Hooks（Status / Todos / Approval / Result）+ 业务工具（get_current_time/get_entity/modify_entity/notify_user/write_todos）在 `build_bot` 中注入 | 阶段 3 | 完成 | ~4 |
| 21  | 结构化结果 `ResultPayloadSchema` + `response_format: json_schema` 透传 + `parse_run_result` 兜底 + system suffix 注入 | 阶段 3 | 完成 | ~3 |
| 22  | 路由升级：`app/api/v1/endpoints/agent.py`（Workspace/Agent CRUD + /start/status/approve/cancel + /configs/tools\* + /configs/statistics） | 阶段 4 | 完成 | 1 |
| 23  | 删除 `app/service/agent/`、`motor_checkpinter.py`、`checkpoint.py`、langchain/langgraph 依赖（完成：目录已移除、代码 import 无残留；`langchain-openai` 保留仅供 embedding 业务链路） | 阶段 5 | 完成 | ~6 |
| 24  | drop 旧集合 `agent_checkpointer` / `agent_checkpointer_writes`（核查 `csi_db` 实际无残留，NOOP 完成；若其它环境出现旧集合按文末命令执行） | 阶段 5 | 完成 | 0 |
| 25  | 新增 / 迁移核心单测（§12.1 `tests/models/test_nanobot_models.py`；§12.2 `tests/nanobot/storage/test_storage_protocol.py`；已清理旧 `tests/nanobot` 与总线/文件 session 相关用例） | 阶段 6 | 进行中 | ~10 |


---

## 十二、测试计划（test points & goals）

> 本章节记录**每次代码改动后需要补充的测试点**，只列目标与验证维度，不写具体实现。
> 最终统一在阶段 6（#25）落地，按模块归档在 `tests/nanobot/` 下。
> 约定：所有 Mongo 相关测试使用 `pytest-asyncio` + 隔离的 `csi_db_test` 数据库，每个 case 前清空涉及集合。

---

### 12.1 数据模型层（`app/models/agent/nanobot.py`、`app/schemas/constants.py`）

对应改动：7 个 Beanie Document + 3 个 Enum（`NanobotAgentStatusEnum` / `NanobotMemoryDocTypeEnum` / `NanobotMessageRoleEnum`）。

**已实现单测文件**：`tests/models/test_nanobot_models.py`（依赖可连通的 MongoDB；不可连时集成用例 `pytest.skip`）。映射：`test_models_registered` → `test_nanobot_models_are_registered_in_get_all_models` + `test_models_registered_collections_exist_after_insert`；其余用例与下表同名或语义一一对应。

| 用例                         | 测试点                                                              | 测试目标                                                       |
| -------------------------- | ---------------------------------------------------------------- | ---------------------------------------------------------- |
| `test_models_registered`   | `init_beanie` 后所有 7 个 Document 均可被 `.find()` 调用，且对应集合存在           | 确认 `models/__init__.py::get_all_models()` 注册完整，无遗漏         |
| `test_indexes_created`     | 启动时 7 张集合上的 index 与代码声明一一对应（名字 / 字段 / unique / 方向）               | 防止改索引定义后忘了清旧索引；校验 unique 复合索引                              |
| `test_id_alias`            | `NanobotWorkspaceModel / NanobotAgentModel / NanobotSessionModel / NanobotHistoryStateModel` 的 `id` 字段通过 alias 写入 / 读取 `_id` | 防止 alias 配错导致查询 miss                                       |
| `test_enum_roundtrip`      | 3 个 Enum 字段写入 Mongo 为 string value，读出自动还原为 Enum 实例                | 防止某些字段存成 int / dict                                        |
| `test_defaults_not_shared` | 多次 `NanobotAgentModel()` 默认的 `tools / steps / todos` 不共享同一 list 引用 | 防止 `default=[]` 类错误                                        |
| `test_unique_conflict`     | 重复插入 `(workspace_id, name)` Agent / `(session_id, seq)` Message / `(workspace_id, cursor)` History 触发 DuplicateKeyError | 保证业务层可依赖 unique 作强约束                                       |
| `test_agent_status_default`| 新建 Agent 默认 `status=IDLE`、`current_session_id=None`、`steps/todos=[]`、`pending_approval/result=None` | 防止默认值漂移影响上层判空                                              |

---

### 12.2 Storage Protocol（`app/service/nanobot/storage/base.py`）

对应改动：`SessionStore` / `MemoryBackend` 两个 `runtime_checkable` Protocol。

**已实现单测文件**：`tests/nanobot/storage/test_storage_protocol.py`（`test_protocol_isinstance_pass` + 两个 incomplete stub 的 `isinstance` 否定用例）。

| 用例                              | 测试点                                                       | 测试目标                             |
| ------------------------------- | --------------------------------------------------------- | -------------------------------- |
| `test_protocol_isinstance_pass` | `isinstance(MongoSessionStore(), SessionStore)` / `MongoMemoryBackend()` 对 `MemoryBackend` 返回 True | 保证实现类契约完整，也是 Protocol 稳定性的回归用例 |
| `test_protocol_isinstance_fail` | 构造一个缺方法的 stub 类，`isinstance` 返回 False                      | 防止接口签名悄悄放宽                       |

---

### 12.3 `MongoSessionStore`（`storage/mongo_session.py`）

> 覆盖目标：session 元数据 upsert + message 增量 append + 按 agent 列表。

**已实现单测文件**：`tests/nanobot/storage/test_mongo_session_store.py`  
说明：该文件为**纯 mock 单元测试**，不连接 MongoDB、不做真实 CURD；通过 monkeypatch 把 `MongoSessionStore` 依赖的 Beanie 调用替换为 `AsyncMock`，只校验 seq 分配、字段映射、upsert 分支与缓存行为。

| 用例                              | 测试点                                                                                                       | 测试目标                                              |
| ------------------------------- | --------------------------------------------------------------------------------------------------------- | ------------------------------------------------- |
| `test_save_new_session`         | 新 Session：先 `add_message` 写 3 条，再 `save`；`nanobot_sessions` 有 1 条元数据，`nanobot_session_messages` 有 3 条、seq=[1,2,3] | 验证首次 save 同时落元数据 + messages                       |
| `test_save_incremental_append`  | 已 save 过的 Session 再 `add_message` 2 条后 `save`；只新插 2 条，总计 5 条，seq=[1..5]                                  | 验证已带 seq 的消息不重复写入；seq 连续递增                         |
| `test_save_inplace_seq`         | save 完成后 `session.messages[i]["seq"]` 全部有值                                                                 | 确保 seq 原地写回，供下次 save 判幂等                           |
| `test_save_meta_overwrite`      | 修改 `session.metadata` / `last_consolidated` 后 save，DB 元数据同步更新，不产生新行                                         | 验证 upsert 语义                                       |
| `test_load_existing`            | save 后 `load(session_id)`：messages 按 seq 升序、所有可选字段（sender_id / tool_calls / thinking_blocks / tool_call_id 等）完整还原 | 验证完整字段映射                                           |
| `test_load_not_found`           | `load("not_exist")` 返回 None                                                                               | 防止返回假对象                                            |
| `test_load_roundtrip`           | `save → load → save → load`，最终 messages / metadata / last_consolidated 完全一致                               | 往返一致性保护                                            |
| `test_list_by_agent_order`      | 同一 agent 连续 start 3 个 session，`list_by_agent` 按 `created_at DESC` 返回且 `limit` 生效                             | 验证索引方向与分页                                          |
| `test_list_by_agent_isolation`  | 不同 agent_id 互不串                                                                                           | workspace 内 agent 数据隔离                             |
| `test_invalidate_cache_only`    | `invalidate` 后再 `load` 能从 DB 还原（未删 DB 记录）                                                                 | `invalidate` 只清缓存                                  |
| `test_save_empty_messages`      | 空 messages 的 Session `save` 只写元数据，不报错                                                                    | 边界兼容                                               |

---

### 12.4 `MongoMemoryBackend`（`storage/mongo_memory.py`）

> 覆盖目标：memory docs upsert + history append 原子性 + cursor 一致性 + workspace 隔离。

**已实现单测文件**：`tests/nanobot/storage/test_mongo_memory_backend.py`  
说明：该文件为**纯 mock 单元测试**，不连接 MongoDB、不做真实 CURD；通过 monkeypatch 替换 `MongoMemoryBackend` 内部引用的 Beanie 模型与 collection 方法，只验证逻辑分支与查询参数形状。

| 用例                              | 测试点                                                                                                   | 测试目标                                           |
| ------------------------------- | ----------------------------------------------------------------------------------------------------- | ---------------------------------------------- |
| `test_read_doc_default_empty`   | 空库读 `(workspace_id, "memory")` 返回 `""`                                                                | 不抛异常；约定 None→空串                                |
| `test_write_doc_upsert`         | 先 write 再 read 得到同 content；第二次 write 更新 content 与 updated_at，行数仍为 1                                  | 验证 upsert + 无重复行                               |
| `test_write_doc_all_types`      | 对 `memory / soul / user` 三种 doc_type 均可独立读写                                                           | 验证 unique `(workspace_id, type)` 约束不误伤         |
| `test_append_history_cursor_increment`  | 连续 append 3 条，返回值为 1,2,3；`nanobot_history` 与 `nanobot_history_state.last_cursor` 一致                   | 验证 `$inc` + `ReturnDocument.AFTER` 逻辑           |
| `test_append_history_state_autocreate`  | workspace_id 无 state 行时首次 append 自动创建 state（含 `last_dream_cursor=0`）                                  | 验证 `$setOnInsert`                               |
| `test_append_history_concurrent`        | `asyncio.gather` 并发 50 次 append，最终 cursor ∈ [1..50] 无重复、无缺口                                          | 验证原子分配，防并发竞争                                   |
| `test_read_history_filter_limit`        | `since_cursor` 过滤 + `limit` 生效 + 升序返回                                                                 | 验证查询参数                                         |
| `test_compact_history_over_limit`       | 20 条 + compact(10)：返回 deleted_count=10，剩下最新 10 条                                                    | 验证按 cursor 升序删除最旧                              |
| `test_compact_history_under_limit`      | 5 条 + compact(10)：返回 0，无删除                                                                            | 边界：≤阈值不动                                       |
| `test_compact_history_zero_limit`       | compact(0)：全删                                                                                         | 边界                                             |
| `test_cursors_default`          | 无 state 行时 `get_cursors` 返回 `(0, 0)`                                                                  | 防 None 解包                                      |
| `test_set_dream_cursor`         | `set_dream_cursor(X)`：last_dream_cursor=X，last_cursor 不变；state 不存在时自动建                                  | 验证 dream 游标独立推进                                 |
| `test_workspace_isolation`      | workspace_A 与 workspace_B 的 memory_docs / history / cursors 互不可见                                     | 多 workspace 并存的基础隔离保证                           |

---

### 12.5 `Session` 领域对象（`session/manager.py::Session`）

**已实现单测文件**：`tests/nanobot/session/test_session_domain.py`

| 用例                                         | 测试点                                                                                                       | 测试目标                                              |
| ------------------------------------------ | --------------------------------------------------------------------------------------------------------- | ------------------------------------------------- |
| `test_session_init_required_fields`        | 构造 Session 必须提供 `id / agent_id / workspace_id`；缺失会 `TypeError`                                            | 防止字段漂移                                            |
| `test_session_add_message_fields`          | `add_message("user", "hi", tool_call_id="x")` 后 messages 末位含 role / content / timestamp / tool_call_id；**不含 seq** | seq 由 SessionStore 分配，领域对象不管                       |
| `test_session_clear`                       | `clear()` 后 messages 为空、last_consolidated=0                                                               | 语义正确                                              |
| `test_retain_recent_legal_suffix_boundary` | 构造带 user / assistant / tool_call 的消息序列，`retain_recent_legal_suffix(n)` 后首条为 user；orphan tool 消息被剥离         | 保护上下文窗口裁剪的合法性                                     |
| `test_retain_recent_zero_clears`           | `retain_recent_legal_suffix(0)` 等价于 clear                                                                 | 边界                                                |
| `test_get_history_skip_consolidated`       | `last_consolidated=N` 后 `get_history()` 只返回 `messages[N:]`                                                | 与 Consolidator 衔接                                  |

---

### 12.6 `SessionManager`（async 协调层）

**已实现单测文件**：`tests/nanobot/session/test_session_manager.py`（纯 mock，不依赖数据库环境）

| 用例                                 | 测试点                                                                                                        | 测试目标                                                        |
| ---------------------------------- | ---------------------------------------------------------------------------------------------------------- | ----------------------------------------------------------- |
| `test_manager_create_assigns_uuid` | 未传 session_id 的 `create()` 生成 uuid4，落入 DB 且 `status.metadata == {}`                                         | session_id 生成逻辑稳定                                            |
| `test_manager_create_custom_id`    | 传入 `session_id="fixed"` 被原样使用                                                                              | 可外部指定（测试 / 幂等恢复）                                            |
| `test_manager_create_conflict`     | 同一 session_id 二次 `create` 抛 DuplicateKeyError（由 `_id` 唯一约束保证）                                              | 防止重复创建                                                      |
| `test_manager_load_after_create`   | create → load 返回的是同一内存对象（命中 store 缓存）                                                                      | 进程内共享语义                                                     |
| `test_manager_load_missing`        | 未知 session_id 返回 None                                                                                      | 不抛异常                                                        |
| `test_manager_save_incremental`    | `add_message` → save → `add_message` → save，消息总量等于两次追加之和；无重复                                                | 增量 append 在 Manager 层一致                                      |
| `test_manager_list_by_agent`       | 同 agent 创建 3 个 session，`list_by_agent(agent_id)` 按时间倒序返回 3 条元数据；`limit=1` 只返回最新                              | 列表 API 合约                                                   |
| `test_manager_invalidate`          | `invalidate(session_id)` 后 `load(session_id)` 会重新走 DB（重新构造 Session 实例，但内容相同）                                | cache 语义                                                    |
| `test_manager_agent_isolation`     | 两个 Agent 各自 `list_by_agent` 不互相可见                                                                           | 隔离保证                                                        |

---

### 12.7 `MemoryStore`（`agent/memory.py::MemoryStore`）

> 覆盖目标：workspace 级长期记忆门面，所有路径都走 MemoryBackend。

**已实现单测文件**：`tests/nanobot/agent/test_memory_store_facade.py`（纯内存 backend，不依赖数据库环境）

| 用例                                  | 测试点                                                                                                          | 测试目标                                               |
| ----------------------------------- | ------------------------------------------------------------------------------------------------------------ | -------------------------------------------------- |
| `test_memory_roundtrip`             | `write_memory/soul/user(x)` → `read_*` 等于 x                                                                 | 验证三份 doc 映射到正确 doc_type                             |
| `test_memory_context_empty_vs_full` | `read_memory()==""` 时 `get_memory_context()` 返回空串；非空时返回 `## Long-term Memory\n...`                           | 防止把空文档塞进 system prompt                             |
| `test_append_history_strips_think`  | 传入含 `<think>...</think>` 的 entry，落库 content 已被 strip_think 处理                                                | 验证 append 前置处理                                     |
| `test_read_unprocessed_filter`      | append 5 条后 `read_unprocessed_history(since_cursor=2)` 只返回后 3 条                                               | cursor 语义与 backend 一致                              |
| `test_count_unprocessed_history`    | 同上场景下 `count_unprocessed_history(2)==3`                                                                     | 供 Dream 阈值判断                                       |
| `test_compact_history_by_limit`     | `max_history_entries=5` 时超过 5 条会裁剪；`<=0` 时不做事                                                                | 验证参数生效                                             |
| `test_cursor_dream_roundtrip`       | `set_last_dream_cursor(10)` 后 `get_last_dream_cursor()==10`；不影响 `get_last_cursor()`                         | Dream 游标独立于 history cursor                          |
| `test_raw_archive_fallback`         | `raw_archive(msgs)` append 的 entry 以 `[RAW]` 开头且含消息条数                                                         | 兜底路径仍可观测                                           |
| `test_workspace_isolation`          | 两个 workspace_id 互不可见所有 doc / history / cursor                                                              | workspace 级隔离                                      |

---

### 12.8 `Consolidator`（`agent/memory.py::Consolidator`）

> 覆盖目标：token 预算触发的滚动归档；锁按 `session.id` 区分；通过 SessionManager/SessionStore 保存。

**已实现单测文件**：`tests/nanobot/agent/test_consolidator_tokens.py`（纯 mock，不依赖数据库环境）

| 用例                                     | 测试点                                                                                                                        | 测试目标                                                 |
| -------------------------------------- | -------------------------------------------------------------------------------------------------------------------------- | ---------------------------------------------------- |
| `test_lock_per_session_id`             | `get_lock("s1") is get_lock("s1")`；`get_lock("s1") is not get_lock("s2")`                                                 | 锁粒度按 session.id（而非 workspace）                          |
| `test_pick_boundary_at_user_turn`      | 构造 user/assistant/tool 混合序列，`pick_consolidation_boundary` 返回的 idx 所在消息 `role=="user"`                                     | 只在 user 回合边界做切分                                      |
| `test_pick_boundary_insufficient_tokens` | 剩余 tokens 不够时返回最后一个合法 boundary（`remove_tokens < target`）                                                                  | fallback 策略                                           |
| `test_cap_chunk_size`                  | `_MAX_CHUNK_MESSAGES=60` 时若理想 end_idx 超过该值，cap 到 user 边界                                                                   | 单轮归档不无限膨胀                                            |
| `test_archive_success_appends_history` | 模拟 provider 返回 summary，`archive(msgs)` 返回 summary 字符串，同 workspace 的 history 新增 1 条且内容等于 summary                            | 验证 LLM 成功路径                                          |
| `test_archive_failure_raw_dump`        | provider.chat_with_retry 抛异常，`archive(msgs)` 返回 None，history 新增 1 条 `[RAW] ...`                                            | 验证失败兜底                                              |
| `test_maybe_consolidate_noop_under_budget` | estimated_tokens < budget 时不调用 archive，session.last_consolidated 不变                                                       | 不必要时不做归档                                            |
| `test_maybe_consolidate_loop_advances`     | estimated_tokens > budget 时循环归档直到 <= target 或 boundary 耗尽；`session.last_consolidated` 前移；`session.metadata["_last_summary"]` 被写入 | 主循环正确性 + session 元数据回写                                |
| `test_maybe_consolidate_session_saved`     | 每轮归档后都 await sessions.save(session)（可 mock 验证 save 调用次数 == 归档轮数 + metadata 落库次数）                                          | 与 SessionManager 正确衔接                                 |
| `test_probe_build_messages_channel_none`   | `estimate_session_prompt_tokens` 传给 `_build_messages` 的 channel/chat_id 均为 None                                             | token 探针与线上调用解耦（由 loop.py 在真实调用时补齐）                    |

---

### 12.9 `Dream`（`agent/memory.py::Dream`）

> 覆盖目标：阈值触发 + 单次 LLM 全量回写；段落解析稳定。

**已实现单测文件**：`tests/nanobot/agent/test_dream_behaviour.py`（`DreamTestBackend` 纯内存 + provider `AsyncMock`，不依赖数据库环境）

| 用例                                  | 测试点                                                                                                                       | 测试目标                                               |
| ----------------------------------- | ------------------------------------------------------------------------------------------------------------------------- | -------------------------------------------------- |
| `test_should_trigger_disabled`      | `DreamConfig.enabled=False` 时 `should_trigger()==False`                                                                  | 硬开关有效                                              |
| `test_should_trigger_below_threshold` | 未处理条目数 < `trigger_unprocessed_count` 返回 False                                                                             | 阈值语义                                               |
| `test_should_trigger_at_threshold`  | 未处理条目数 == `trigger_unprocessed_count` 返回 True                                                                             | 边界                                                 |
| `test_run_noop_when_disabled`       | `DreamConfig.enabled=False` 时 `run()==False`，不调用 LLM、不 compact                                                         | 与 `should_trigger` 一致的硬开关                            |
| `test_run_noop_when_no_entries`     | `read_unprocessed_history` 为空时 `run()==False`，cursor 不变                                                                  | 早退路径                                               |
| `test_run_llm_failure_returns_false` | provider 抛异常时 `run()==False`，cursor 不前移、memory doc 不被改写                                                                   | 失败不破坏状态                                            |
| `test_run_no_change_preserves_docs` | LLM 返回三段都是 NO_CHANGE，doc 内容不变；cursor 仍前移到 batch[-1]["cursor"]                                                           | "无更新但已处理"                                           |
| `test_run_partial_update`           | LLM 返回 MEMORY=新文本 / SOUL=NO_CHANGE / USER=新文本，write_memory/write_user 被调用且内容正确，write_soul 不被调用                          | 单独写回受影响的 doc                                       |
| `test_run_advances_cursor_and_compacts` | run 成功后 `last_dream_cursor == batch[-1]["cursor"]`；`compact_history` 按 `max_history_entries` 触发                             | 游标前移 + 历史压缩联动                                      |
| `test_parse_sections_basic`         | 三段都有 → 返回 dict 三键都非 None                                                                                                 | 正则正确                                               |
| `test_parse_sections_no_change_case_insensitive` | 段内为 `no_change` / `No_Change` 等 → 该键对应 value 为 None（`raw.upper()=="NO_CHANGE"`）                                        | NO_CHANGE 语义                                       |
| `test_parse_sections_missing_section` | 只输出 MEMORY 段 → SOUL/USER 键值为 None                                                                                        | 缺段兜底                                              |
| `test_parse_sections_extra_whitespace` | 多行空白 / 含中文 / 含 ```markdown``` 代码块时不截断内容                                                                                 | 解析器鲁棒性                                             |
| `test_batch_size_honored`           | 未处理条目 50 条、`max_batch_size=20`，`run()` 只处理前 20 条；`last_dream_cursor` 前移到第 20 条                                         | batch 限制                                           |
| `test_run_llm_error_finish_reason_returns_false` | `finish_reason=="error"` 时 `run()==False`，游标不前移、不写 doc                                                           | 与 `chat_with_retry` 返回错误态一致                          |

---

### 12.10 `ContextBuilder` + `MemorySnapshot`（`agent/context.py`）

> 覆盖目标：快照刷新并发性、空快照安全兜底、system prompt 段落可控组装。

**已实现单测文件**：`tests/nanobot/agent/test_context_builder.py`（`FakeMemoryStore` 纯内存 + 可选 `asyncio.gather` 包装，不依赖数据库环境）。实现上 `refresh_memory_snapshot` 对 MEMORY/SOUL/USER/`get_last_dream_cursor` 使用一次 `asyncio.gather(4)`，再单独 `read_unprocessed_history`；`MemorySnapshot` 仅含 `memory` / `soul` / `user` / `recent_history` 四字段（不含 dream_cursor 副本）。

| 用例                                   | 测试点                                                                                                                            | 测试目标                                             |
| ------------------------------------ | ------------------------------------------------------------------------------------------------------------------------------ | ------------------------------------------------ |
| `test_empty_snapshot_prompt`         | 全空 MemorySnapshot → system prompt 只含 identity + Search & Discovery，不渲染空的 SOUL/USER/Memory/Recent History 段落                      | 防止空字符串污染 prompt                                   |
| `test_refresh_snapshot_concurrent`   | mock memory 返回各 read + history；`refresh_memory_snapshot` 内对 `asyncio.gather` 传入 4 个协程（四路 read），snapshot 四字段与 history 子集正确      | 验证并发预取与 gather 宽度                                  |
| `test_refresh_history_capped`        | history 返回 100 条时 snapshot.recent_history 只保留最后 50 条（`_MAX_RECENT_HISTORY`）                                                       | 上下文体积上限                                           |
| `test_persona_block_soul_only`       | SOUL 有内容、USER 空（或仅空白）→ prompt 含 `## SOUL`、不出现 persona 形式的 `## USER\n\n`                                                      | 可选段落逻辑                                           |
| `test_persona_block_user_only`       | USER 有内容、SOUL 空 → prompt 含 `## USER`、不出现 persona 形式的 `## SOUL\n\n`                                                                 | 同上                                                 |
| `test_memory_section_injection`      | snapshot.memory 非空 → prompt 含 `# Memory\n\n## Long-term Memory\n...`                                                            | Memory 片段挂载点                                      |
| `test_recent_history_render`         | snapshot.recent_history 条目渲染为 `- [YYYY-MM-DD HH:MM] content`，接受 datetime / ISO 字符串 / 缺失                                          | 时间格式归一化                                          |
| `test_build_messages_single_user_turn` | 末条是 user 时 `build_messages(..., current_role='user')` 会合并到末条 content，不追加新条                                                      | 与旧实现行为一致（防多轮 user）                                 |
| `test_build_messages_runtime_ctx_merged` | runtime_ctx 前缀出现在 user message 开头，包含 Current Time / Channel / Chat ID                                                          | 注入位置正确                                          |
| `test_identity_no_workspace_path`    | identity.md 渲染结果**不含** `{{ workspace_path }}` 占位符或任何文件路径提示                                                                     | 确认模板迁移干净                                          |
| `test_skills_none_safely`            | `ContextBuilder(skills=None)` 调 build_system_prompt 不抛异常，只是没有 Active Skills / Skills Summary 段                                   | skills 未配置时的兜底                                    |

---

### 12.11 `WorkspaceService`（`app/service/analyst/workspace.py`）

> 覆盖目标：CRUD 基本 contract + 资源存在性校验 + 白名单收窄级联一致性 + 删除保护。

**已实现单测文件**：  
- `tests/analyst/test_workspace_service.py`（通过 patch `NanobotWorkspaceModel`/`NanobotAgentModel`/`AgentPromptTemplateModel`/`AgentModelConfigModel` 为纯内存桩，覆盖 create/get/list/update/delete 与收窄冲突载荷）。  
- `tests/api/test_agent_workspaces_endpoints.py`（路由层契约：成功路径走 HTTP；冲突 payload 因 `response_model=ApiResponseSchema[NanobotWorkspaceSchema]` 与 error data 泛型不一致，按现有惯例直接测协程返回体）。  

| 用例                                           | 测试点                                                                                                                          | 测试目标                                           |
| -------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------- | ---------------------------------------------- |
| `test_create_success`                        | 写入 `prompt_template_ids` / `model_config_ids` 均存在、MCP 配置合法 → DB 落 1 行，返回 Schema 中字段齐全                                      | 基本 create 路径                                   |
| `test_create_name_conflict`                  | 同名 workspace 再次 create 返回 `CONFLICT_NAME`                                                                                   | 同名保护                                           |
| `test_create_missing_prompt_template`        | `prompt_template_ids` 含不存在的 ID → `NOT_FOUND_TEMPLATE`                                                                        | 资源存在性校验                                       |
| `test_create_missing_model_config`           | `model_config_ids` 含不存在的 ID → `NOT_FOUND_MODEL_CONFIG`                                                                       | 资源存在性校验                                       |
| `test_create_duplicate_prompt_ids`           | `prompt_template_ids` / `model_config_ids` 含重复项 → `INVALID_ARGUMENT`                                                          | 数据清洁                                           |
| `test_create_invalid_mcp_config`             | `enabled_mcp_servers` value 不符合 `MCPServerConfig` → `INVALID_ARGUMENT` 且错误信息含 server_name                                    | MCP 配置合法性                                      |
| `test_create_empty_mcp_server_name`          | `enabled_mcp_servers` 出现空字符串 key → `INVALID_ARGUMENT`                                                                        | 边界                                             |
| `test_get_not_found`                         | `get("missing")` 抛 `WorkspaceServiceError(NOT_FOUND_WORKSPACE)`                                                                | 错误路径                                          |
| `test_list_page_pagination`                  | 创建 3 个 workspace，`list_page(page=1,page_size=2)` 返回 2 条 + total=3                                                            | 分页准确                                          |
| `test_list_page_search`                      | `search='foo'` 只匹配名称或描述含 `foo` 的 workspace                                                                                   | 模糊搜索                                          |
| `test_list_all_brief`                        | 返回 id/name 列表，按 `created_at DESC`                                                                                            | 下拉用列表顺序稳定                                      |
| `test_update_success`                        | 合法更新 → DB 字段更新、`updated_at` 前移；返回 Schema 一致                                                                                 | update 基本路径                                    |
| `test_update_name_conflict`                  | 改名到另一个存在的 workspace 名称 → `CONFLICT_NAME`                                                                                     | 同名保护                                          |
| `test_update_narrow_tools_with_reference`    | Workspace 现有 Agent 引用 tool=`t1`，更新时移除 `t1` → `CONFLICT_STATE` 且 `data.conflicts` 列出该 Agent                                  | 白名单收窄级联                                       |
| `test_update_narrow_prompt_template`         | 移除某 prompt_template_id 但有 Agent 仍选 → `CONFLICT_STATE`                                                                        | 同上                                             |
| `test_update_widen_allowed`                  | 在保留原有引用的前提下新增条目 → 更新成功                                                                                                   | 允许"放宽"                                         |
| `test_update_resource_missing`               | 更新时给出不存在的 prompt_template_id → `NOT_FOUND_TEMPLATE`，不触发级联校验分支                                                              | 校验顺序                                           |
| `test_delete_success`                        | 无关联 Agent 时删除成功，DB 中 workspace 消失                                                                                            | 删除基本路径                                         |
| `test_delete_blocked_by_agents`              | 存在关联 Agent 时返回 `CONFLICT_STATE`，workspace 仍然存在                                                                              | 删除保护                                           |
| `test_route_create_201`                      | `POST /agent/workspaces` 200 → `ApiResponseSchema` code=0，返回完整 workspace                                                      | 路由层契约                                         |
| `test_route_not_found`                       | `GET /agent/workspaces/missing` 返回 `NOT_FOUND_WORKSPACE`                                                                     | 错误码透传                                         |
| `test_route_narrowing_conflict_payload`      | `PUT /agent/workspaces/{id}` 收窄冲突时，响应 `data.conflicts` 清晰列出冲突 Agent                                                         | 错误载荷一致性                                      |

---

### 12.12 `AgentService`（`app/service/analyst/agent.py`）

> 覆盖目标：CRUD 基本 contract + 资源子集校验 + 运行时写保护 + workspace_id 过滤隔离。

**已实现单测文件**：  
- `tests/analyst/test_agent_service.py`（纯内存桩：patch `NanobotAgentModel`/`NanobotWorkspaceModel`，覆盖 create/get/list/update/delete、子集校验、运行态保护、重校验与同名规则）。  
- `tests/api/test_agent_agents_endpoints.py`（路由层契约：成功/not found/list 走 HTTP；subset 违规载荷按惯例直接测协程返回的 `ApiResponseSchema`）。  

| 用例                                           | 测试点                                                                                                         | 测试目标                                             |
| -------------------------------------------- | ----------------------------------------------------------------------------------------------------------- | ------------------------------------------------ |
| `test_create_success`                        | 合法 subset 下创建 Agent，DB 写 1 行，`status=IDLE`、`current_session_id=None`                                      | 基本 create + 默认运行时字段                                |
| `test_create_workspace_missing`              | `workspace_id` 不存在 → `NOT_FOUND_WORKSPACE`                                                                   | 关联校验                                            |
| `test_create_prompt_not_in_whitelist`        | `prompt_template_id` 不在 workspace.prompt_template_ids → `INVALID_ARGUMENT` 且 `data.violations` 列出原因           | 子集校验（prompt）                                      |
| `test_create_model_not_in_whitelist`         | 同上，model_config_id                                                                                         | 子集校验（model）                                       |
| `test_create_tools_outside`                  | `tools` 含 workspace.enabled_tools 之外的条目 → `INVALID_ARGUMENT` + violations 列出全部额外工具                         | 子集校验（tools）                                       |
| `test_create_skills_outside`                 | 同上，skills                                                                                                   | 子集校验（skills）                                      |
| `test_create_mcp_outside`                    | `mcp_servers` 含 workspace.enabled_mcp_servers 之外的 server 名 → `INVALID_ARGUMENT`                              | 子集校验（MCP）                                         |
| `test_create_duplicate_fields`               | tools / skills / mcp_servers 中存在重复项 → `INVALID_ARGUMENT`                                                     | 数据清洁                                            |
| `test_create_name_unique_per_workspace`      | 同 workspace 下重名 → `CONFLICT_NAME`；不同 workspace 下同名可共存                                                      | `(workspace_id, name)` 唯一约束                         |
| `test_get_not_found`                         | `get('missing')` 抛 `AgentServiceError(NOT_FOUND_AGENT)`                                                        | 错误路径                                            |
| `test_list_page_filter_by_workspace`         | 两个 workspace 各自有 Agent，`list_page(workspace_id=wsA)` 只返回 wsA 的                                               | workspace 过滤 + 隔离                                   |
| `test_list_page_search`                      | `search='foo'` 模糊匹配 name / description                                                                     | 模糊搜索                                            |
| `test_list_brief`                            | 返回 id / name / workspace_id / status，按 `created_at DESC`                                                      | 简表                                               |
| `test_update_success`                        | IDLE 状态下合法更新 → 字段更新、`updated_at` 前移；运行时状态字段（status / steps / todos / result）保持不变                     | 仅更新配置字段，不污染业务状态                              |
| `test_update_blocked_running`                | `status=RUNNING` 时更新 → `CONFLICT_STATE`                                                                    | 运行时写保护                                         |
| `test_update_blocked_awaiting_approval`      | `status=AWAITING_APPROVAL` 时更新 → `CONFLICT_STATE`                                                          | HITL 阶段写保护                                       |
| `test_update_allowed_after_completed`        | `status=COMPLETED` / `FAILED` / `PAUSED` 时允许更新                                                               | 状态分区正确                                         |
| `test_update_rename_conflict`                | 同 workspace 下改名到别的 Agent 已有名称 → `CONFLICT_NAME`                                                            | 同名保护                                            |
| `test_update_rename_no_conflict_self`        | 保持自己名称时不触发 name 冲突分支                                                                                      | 不误伤                                              |
| `test_update_resubset_check`                 | Workspace 白名单变化后（非收窄，通过另一路径）更新 Agent 时资源子集校验仍基于最新 workspace                                             | 总是拿最新 workspace 做校验                                |
| `test_delete_success`                        | 非运行时删除成功，DB 中消失                                                                                             | 删除基本路径                                         |
| `test_delete_blocked_running`                | `status=RUNNING` / `AWAITING_APPROVAL` 时删除 → `CONFLICT_STATE`                                              | 运行时写保护                                         |
| `test_route_create_201`                      | `POST /agent/agents` 200 → `ApiResponseSchema` code=0，返回完整 Agent                                             | 路由层契约                                         |
| `test_route_not_found`                       | `GET /agent/agents/missing` 返回 `NOT_FOUND_AGENT`                                                             | 错误码透传                                         |
| `test_route_subset_violation_payload`        | `POST /agent/agents` 触发 subset 违规时，响应 `data.violations` 明细齐全                                                 | 错误载荷                                         |
| `test_route_list_filter_query`               | `GET /agent/agents?workspace_id=xxx&search=foo` 传参生效                                                          | Query 契约                                         |

---

### 12.13 `AnalystService`（`app/service/analyst/service.py` + `context.py` + `/start` `/status` `/approve` 路由）

对应改动（TODO #19）：
- 新增 `app/service/analyst/context.py`：`current_agent_id` / `current_session_id` ContextVar
- 新增 `app/service/analyst/service.py`：`AnalystService` 类（SSE / HITL / build_bot / start_agent / run_analysis / cancel_agent）
- 在 `ContextBuilder` 上新增 `extra_system_suffix` 字段并在 `build_system_prompt` 末尾追加
- 路由升级：`POST /agent/start` → `AnalystService.start_agent` / `GET /agent/status?agent_id=...` → SSE / `POST /agent/approve` → `submit_approval`
- Schema 升级：`StartAgentRequestSchema` 改为 `agent_id + user_prompt + extra_context`；`ApproveRequestSchema` 改为 `agent_id + decisions`；新增 `StartAgentResponseSchema`

**已实现单测文件**：  
- `tests/analyst/test_analyst_service_core.py`（覆盖 `ContextVar`、SSE 订阅/广播、审批队列、`run_analysis` 成功与 CancelledError(pause) 路径；patch `NanobotAgentModel` 为纯内存桩，`Nanobot` 用 `AsyncMock`）。  
- `tests/api/test_agent_start_approve_endpoints.py`（覆盖 `/agent/start` 与 `/agent/approve` 的路由成功路径与错误码透传（含 unknown agent），不连 DB）。  
- `tests/api/test_agent_status_sse_endpoints.py`（覆盖 `/agent/status` 的 SSE 输出格式、keep-alive 与断线 unsubscribe 清理，不连 DB）。  

| 用例                                              | 测试点                                                                                                                                          | 测试目标                                                               |
| ----------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------ |
| `test_context_set_reset`                        | `current_agent_id.set()` / `current_session_id.set()` 后 `get_current_*` 返回正确值，`reset(token)` 后恢复 None                                     | ContextVar 正确性                                                    |
| `test_context_isolation_between_tasks`          | 两个并发 `asyncio.create_task`，各自 set 不同 `agent_id`，互不污染                                                                                      | 协程级上下文隔离                                                         |
| `test_sse_subscribe_and_broadcast`              | `subscribe(agent_id)` → Queue；`broadcast_sse` 事件能从 Queue 取到                                                                                | SSE 基本通路                                                         |
| `test_sse_multiple_subscribers`                 | 同一 agent 订阅 2 路，每路都能收到同一事件；`unsubscribe` 其中一路后，另一路仍能收到                                                                                  | 扇出 + 个别退订                                                        |
| `test_sse_unsubscribe_cleans_subs_map`          | 订阅者全部 unsubscribe 后，`_sse_subscribers` 中不再保留该 agent_id                                                                                    | 防内存泄漏                                                           |
| `test_submit_approval_puts_queue`               | AWAITING_APPROVAL 时 `submit_approval(agent_id, decisions)` 后 `await_approval(agent_id)` 能取到相同 decisions                                  | HITL 决策通路                                                       |
| `test_submit_approval_non_awaiting_warns`       | 非 AWAITING_APPROVAL 状态 `submit_approval` 仍入队但 log warning（通过 `caplog` 断言）                                                                  | 幂等写入，避免决策丢失                                                   |
| `test_submit_approval_unknown_agent_404`        | `submit_approval` 到不存在的 agent_id → `AgentServiceError(NOT_FOUND_AGENT)`                                                                    | 路由层 404                                                         |
| `test_build_bot_reads_model_and_prompt`         | `build_bot` 会按 agent 的 `model_config_id` / `prompt_template_id` 查模型和提示词；缺失时抛 `NOT_FOUND_MODEL_CONFIG` / `NOT_FOUND_TEMPLATE`                 | 资源查询闭合                                                         |
| `test_build_bot_mcp_subset_filter`              | agent.mcp_servers 中出现但不在 workspace.enabled_mcp_servers 的 key 被过滤掉                                                                        | 避免越权使用 MCP                                                      |
| `test_build_bot_resets_runtime_fields`          | `build_bot` 写入新 `current_session_id`，并把 `steps/todos=[]`、`pending_approval/result=None`                                                 | 每次 /start 是全新回合                                                 |
| `test_build_bot_injects_system_suffix`          | `bot.loop.context.extra_system_suffix == prompt_tpl.system_prompt.strip()`；`build_system_prompt()` 末尾包含该字符串                             | prompt template 正确落地                                             |
| `test_start_agent_returns_session_id`           | `start_agent(agent_id, prompt)` 返回非空 session_id，且与 DB 中 `current_session_id` 一致                                                        | 基本启动路径                                                         |
| `test_start_agent_broadcasts_status`            | 启动成功后 SSE 发一条 `event=status, status=running`                                                                                            | 前端能立即看到状态切换                                                  |
| `test_start_agent_rejects_running`              | agent.status=RUNNING 再 start → `CONFLICT_STATE`；AWAITING_APPROVAL 同理                                                                      | 单会话并发约束                                                        |
| `test_start_agent_rejects_duplicate_task`       | 即便 DB status=IDLE（状态漂移），但 `_running_tasks[agent_id]` 仍存在且未 done → 拒绝                                                                    | 本进程幂等                                                           |
| `test_start_agent_unknown_agent_404`            | 未知 agent_id → `NOT_FOUND_AGENT`                                                                                                            | 错误码透传                                                           |
| `test_start_agent_missing_workspace_404`        | agent 存在但其 workspace_id 对应 workspace 不存在 → `NOT_FOUND_WORKSPACE`                                                                         | 级联校验                                                             |
| `test_run_analysis_success_path`                | `bot.run` 正常返回 → agent.status=COMPLETED，`result` 含 content/tools_used；SSE 发 `event=result`；`bot.close()` 被调用；`_bots/_running_tasks/_pending_resumes` 清空 | 成功路径完整闭环                                                      |
| `test_run_analysis_exception_to_failed`         | `bot.run` 抛异常 → agent.status=FAILED，`result={"error": ...}`；SSE result 事件含 `error`；bot.close 仍被调用                                     | 异常兜底                                                             |
| `test_run_analysis_cancel_to_paused`            | `cancel_agent(agent_id, reason="pause")` → agent.status=PAUSED                                                                           | 手动暂停 / 取消区分                                                   |
| `test_run_analysis_cancel_to_failed_default`    | `cancel_agent(agent_id)` 默认 reason=cancel → agent.status=FAILED                                                                           | 默认取消语义                                                         |
| `test_run_analysis_context_var_scoped`          | run 期间 `get_current_agent_id()` 返回正确值；run 结束后回到 None（token 被 reset）                                                                    | ContextVar 生命周期                                                 |
| `test_run_analysis_closes_bot_on_any_exit`      | 成功 / 异常 / 取消三路径，`bot.close()` 均被调用至少一次                                                                                                 | 资源释放                                                             |
| `test_start_resets_pending_resumes`             | 上一轮未消费的 `_pending_resumes[agent_id]` 在 `start_agent` 时被清理                                                                                | 防串场                                                               |
| `test_route_start_returns_session_id`           | `POST /agent/start` 返回 code=0，`data.agent_id` / `data.session_id` 齐全                                                                      | 路由契约                                                             |
| `test_route_start_conflict_state_payload`       | agent RUNNING 时调用 `/agent/start` → `ApiResponseSchema.error(code=CONFLICT_STATE, message=...)`                                             | 错误码直出                                                           |
| `test_route_status_sse_keepalive_and_event`     | `GET /agent/status?agent_id=...` 响应 text/event-stream；收到 `broadcast_sse` 的 `event:` 行；空闲 15s 发 `: keep-alive`                         | SSE 协议正确 + keep-alive                                        |
| `test_route_status_unsubscribes_on_disconnect`  | 客户端断开后 `_sse_subscribers` 中该 queue 被移除                                                                                               | 断线清理                                                             |
| `test_route_approve_submits_queue`              | `POST /agent/approve` 200，`_pending_resumes[agent_id].get()` 能取到 decisions                                                              | approve 路由闭环                                                   |
| `test_route_approve_unknown_agent_404`          | `/agent/approve` 对未知 agent_id → `NOT_FOUND_AGENT`                                                                                      | 错误码透传                                                           |

### 12.14 业务 Hooks（`app/service/analyst/hooks.py`）

对应改动（TODO #20）：
- `StatusHook` / `TodosHook` / `ApprovalHook` / `ResultHook` 继承 `AgentHook`，通过 `ContextVar` 读取 `agent_id` / `session_id`
- `default_analyst_hooks()` 按固定顺序返回 4 个 Hook，注入点位于 `AnalystService.build_bot` → `Nanobot.from_components(..., hooks=...)`

**已实现单测文件**：`tests/analyst/test_analyst_hooks.py`（纯 mock：patch `NanobotAgentModel` 为内存桩、SSE 广播用 stub；覆盖顺序、step 追加与广播、todos 触发/非触发、approval 兜底复位、result strip）。  

| 用例                                         | 测试点                                                                                                                              | 测试目标                                                    |
| ------------------------------------------ | -------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------- |
| `test_default_hooks_order`                 | `default_analyst_hooks()` 返回顺序固定为 `[StatusHook, TodosHook, ApprovalHook, ResultHook]`                                        | Hook 固定顺序保证 `finalize_content` pipeline 可预测        |
| `test_hook_noop_without_context`           | `get_current_agent_id()` 未 set 时，所有 Hook 的 `before_*/after_*` 方法安静返回（不抛异常、不访问 DB）                                           | ContextVar 防御                                          |
| `test_status_hook_before_tools_broadcasts` | `before_execute_tools(ctx)` 触发 SSE `event=step phase=before_tools`，`data.tool_calls` 含每个 tool call 的 name 和 arguments | 工具前预览事件                                             |
| `test_status_hook_after_iteration_step`    | `after_iteration(ctx)` 追加一条 step 到 `agent.steps` 并 save；SSE 发一条 `event=step phase=after_iteration`                       | step 流水 DB + SSE 双路                                 |
| `test_status_hook_step_fields_complete`    | step 包含 iteration / content / tool_calls / tool_events / usage / stop_reason / error / created_at                     | 避免字段漂移                                              |
| `test_status_hook_db_error_isolated`       | `agent.save()` 抛异常时，Hook 捕获并打 exception log，不传播到外层                                                                          | 单 Hook 故障不影响 loop                                  |
| `test_todos_hook_broadcast_on_write_todos` | tool_events 中含 `name=write_todos` 时，Hook 从 DB 读最新 `agent.todos` 并 SSE `event=todos`                                        | 与工具侧 DB 写解耦，Hook 负责广播兜底                       |
| `test_todos_hook_noop_on_other_events`     | tool_events 只含其它工具时不广播 `todos` 事件                                                                                            | 最小化副作用                                              |
| `test_approval_hook_resets_stuck_state`    | agent.status=AWAITING_APPROVAL 且 stop_reason != "awaiting_approval" 时，Hook 将 status 复位为 RUNNING，`pending_approval=None` | 异常退出兜底                                              |
| `test_approval_hook_skips_when_healthy`    | status=RUNNING 时 Hook 不修改 DB                                                                                                | 不误伤正常路径                                            |
| `test_result_hook_strips_whitespace`       | `finalize_content(ctx, "  hi\\n")` 返回 `"hi"`；None 原样返回                                                                      | 输出规整化                                                |

### 12.15 业务工具（`app/service/analyst/tools.py`）

对应改动（TODO #20）：5 个工具 + `build_business_tools(enabled_names)` 白名单过滤。

**已实现单测文件**：  
- `tests/analyst/test_analyst_tools.py`（覆盖工具 schema、白名单过滤、get_entity 的 ES 分支、write_todos/notify_user/modify_entity 的 ContextVar + DB/SSE/HITL 行为，纯 mock）。  
- `tests/analyst/test_analyst_service_build_bot.py`（覆盖 `AnalystService.build_bot` 装配：注入 4 个 hooks、按 agent.tools 注册业务工具、system suffix 叠加模板与 `RESULT_FORMAT_INSTRUCTION`，纯 mock）。  

| 用例                                              | 测试点                                                                                                                                                                                     | 测试目标                                                       |
| ----------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ---------------------------------------------------------- |
| `test_tool_schemas_valid`                       | 5 个工具的 `to_schema()` 均可被 json.dumps，且 function.name 与类属性一致                                                                                                                           | OpenAI tool schema 契约                                    |
| `test_build_business_tools_whitelist`           | 传入 `['notify_user', 'write_todos', 'unknown']` → 仅返回前 2 个实例，`unknown` 打 warn                                                                                                        | 白名单过滤 + 未知项容错                                        |
| `test_get_current_time_returns_iso`             | `execute()` 返回 ISO 8601 字符串，`datetime.fromisoformat(r)` 解析不抛错                                                                                                                         | 无状态工具契约                                               |
| `test_get_entity_missing_type`                  | 未知 `entity_type` → 返回 `"[错误] 不支持的实体类型..."`                                                                                                                                          | 输入校验                                                     |
| `test_get_entity_es_not_initialized`            | `get_es()` 返回 None → 返回 `"[错误] Elasticsearch 未初始化"`                                                                                                                                  | 服务未就绪保护                                               |
| `test_get_entity_success`                       | mock es.get 返回 `{"_source": {...}}` → execute 返回源数据字符串                                                                                                                                 | 查询成功路径                                                 |
| `test_get_entity_es_exception_returns_error_str`| es.get 抛异常 → 返回 `"[错误] 查询实体失败: ..."`，不向上抛                                                                                                                                           | 工具永远不该 raise                                        |
| `test_tool_requires_context_var`                | 不 set `current_agent_id` 时，`write_todos.execute()` 抛 RuntimeError（ContextVar 防御）                                                                                                    | 防止工具在错误调用位置被触发                                 |
| `test_write_todos_updates_db_and_broadcasts`    | `execute(todos=[...])` → `agent.todos` 被完整替换，`updated_at` 刷新，SSE `event=todos` 含同一份列表                                                                                        | DB + SSE 一致                                              |
| `test_write_todos_normalizes_fields`            | 传入带前后空格、多余字段的 todos → 标准化后 `content` 被 strip、未知字段被丢弃、`id/status/updated_at` 补齐                                                                                                | 输入清洗                                                   |
| `test_write_todos_agent_missing`                | ContextVar agent_id 指向不存在的 agent → 返回 `"[错误] 当前 agent 不存在"`                                                                                                                        | 错误消息透传                                                |
| `test_notify_user_broadcasts`                   | `execute(message="hi", level="warning")` → SSE `event=notification data.level=warning data.message=hi`                                                                                   | SSE 消息契约                                                |
| `test_notify_user_empty_message`                | message 为空或纯空白 → 返回 `"[错误] message 不能为空"`，不广播                                                                                                                                   | 最小输入校验                                                |
| `test_modify_entity_handshake_approve`          | 工具启动 → status=AWAITING_APPROVAL + pending_approval 写入 + SSE 2 条（approval_required + status=awaiting_approval）；`submit_approval` approve → 工具返回 "获批准"、status 恢复 RUNNING、pending_approval=None、SSE `status=running` | HITL 同意分支                                               |
| `test_modify_entity_handshake_reject`           | `submit_approval` reject 且带 reason → 返回 "修改被拒绝：&lt;reason&gt;"，status 仍复位 RUNNING                                                                                                 | HITL 拒绝分支                                               |
| `test_modify_entity_empty_decisions`            | `submit_approval` 传空 decisions → 返回 "修改未获得任何批准，未执行。"                                                                                                                             | 决策缺省兜底                                                |
| `test_modify_entity_decision_parser_variants`   | `_parse_approval_decisions` 能识别 `{"action":"approve"}`、`{"approved":True}`、`{"action":"reject","reason":"bad"}` 三种形式                                                          | 决策结构兼容                                                |
| `test_modify_entity_await_exception_returns`    | `AnalystService.await_approval` 抛异常（通过 mock）→ 工具返回 `"[错误] 等待审批异常: ..."`，不上抛                                                                                                   | 工具异常隔离                                                |
| `test_build_bot_injects_hooks_and_tools`        | `AnalystService.build_bot` 完成后：`bot.loop._extra_hooks` 含 4 个 hook；`bot.loop.tools._tools` 键集包含 agent.tools 白名单、排除未启用的工具                                                 | 组装正确性                                                   |

### 12.16 结构化最终结果（`app/schemas/agent/result.py` + `AnalystService` + `OpenAICompatProvider`）

对应改动（TODO #21）：
- 新增 `app/schemas/agent/result.py`：`ResultPayloadSchema` / `RESULT_FORMAT_INSTRUCTION` / `build_response_format_schema()` / `parse_run_result(raw)`
- `OpenAICompatProvider.__init__` 新增 `response_format` 参数，`_build_kwargs` 透传；构造时未提供则请求里不含该字段
- `AnalystService.build_bot`：
  - 用 `build_response_format_schema()` 构造 provider 的 `response_format`
  - `ContextBuilder.extra_system_suffix` 叠加 `AgentPromptTemplateModel.system_prompt` + `RESULT_FORMAT_INSTRUCTION`
- `AnalystService.run_analysis` 成功路径改为 `parse_run_result(run_result.content)`，落库字段扩展为 `{**parsed.model_dump(), parsed, raw_content, tools_used}`

**已实现单测文件**：  
- `tests/schemas/agent/test_result_schema.py`（覆盖 schema roundtrip、`build_response_format_schema` 形状、`parse_run_result` 的 strict/围栏/前后缀/失败兜底/截断等）。  
- `tests/nanobot/providers/test_openai_compat_response_format.py`（覆盖 `OpenAICompatProvider._build_kwargs` 对 `response_format` 的透传与与 tools 共存）。  
- `tests/analyst/test_run_analysis_structured_result.py`（覆盖 `AnalystService.run_analysis`：可解析结果 parsed=True、不可解析 parsed=False 但仍 COMPLETED、异常路径 FAILED 且 `result={"error":...}`；同时校验 SSE `event=result` 载荷结构）。  

| 用例                                              | 测试点                                                                                                                                                                 | 测试目标                                                 |
| ----------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------ | ---------------------------------------------------- |
| `test_result_schema_roundtrip`                  | `ResultPayloadSchema(...).model_dump()` 与 `ResultPayloadSchema.model_validate(dump)` 双向互通，所有字段类型稳定                                                            | Pydantic schema 稳定                                 |
| `test_result_schema_required_fields`            | 缺 `summary` / `success` 抛 `ValidationError`                                                                                                                      | 必填约束                                             |
| `test_response_format_payload_shape`            | `build_response_format_schema()` 返回 `{"type":"json_schema","json_schema":{"name":"result","schema":{...},"strict":False}}`，`schema.properties` 含 5 个字段   | OpenAI 兼容契约                                      |
| `test_parse_strict_json`                        | `parse_run_result('{"summary":"x","success":true}')` → `(schema, True)`，字段与输入匹配                                                                             | 严格 JSON 路径                                       |
| `test_parse_fenced_json`                        | 带三反引号 ` ```json ... ``` ` 围栏的内容仍能解析成功（依赖 `json_repair`）                                                                                                       | 宽松修复路径                                         |
| `test_parse_extra_text_around_json`             | 前后附带散文本时 `json_repair` 能抽出核心 JSON（若 lib 能力支持）                                                                                                                  | 健壮性                                               |
| `test_parse_invalid_json_fallback`              | 传非 JSON 文本 → `(schema, False)`，`schema.success=False`，`failure_reason` 含 "无法解析"，`summary` ≤ 2000 字符并为原文前缀                                                | 兜底路径                                             |
| `test_parse_empty_or_none`                      | `None` / `""` / 纯空白 → `(schema, False)`，`failure_reason` 含 "未返回"                                                                                              | 空内容兜底                                           |
| `test_parse_missing_required_fallback`          | JSON 有效但缺 `summary/success` → `(schema, False)`，走兜底分支                                                                                                        | Pydantic 校验失败也走兜底                            |
| `test_parse_long_content_truncates_to_2000`     | 传长度 5000 的非 JSON 文本 → `len(schema.summary) == 2000`                                                                                                              | 防止巨型 prompt 落库                                 |
| `test_result_format_instruction_contains_keys`  | `RESULT_FORMAT_INSTRUCTION` 文本包含 `summary`、`success`、`failure_reason`、`details`、`todos_snapshot`、"输出格式"                                                | prompt 与 schema 同步                                |
| `test_provider_kwargs_includes_response_format` | 构造时传 `response_format` → `_build_kwargs(...)` 返回字典含同一对象                                                                                                      | provider 透传                                        |
| `test_provider_kwargs_without_response_format`  | 未传 `response_format` → `_build_kwargs` 返回字典**不含** `response_format` 键                                                                                      | 不意外注入                                          |
| `test_provider_response_format_coexists_tools`  | 同时传 `tools` + `response_format` → 两者同时出现在 kwargs                                                                                                              | 与 function calling 共存                             |
| `test_build_bot_sets_provider_response_format`  | `AnalystService.build_bot` 完成后 `bot.loop.provider.response_format['json_schema']['name'] == 'result'`                                                           | build_bot 正确装配                                  |
| `test_build_bot_system_suffix_combines`         | `bot.loop.context.extra_system_suffix` 同时包含 `prompt_tpl.system_prompt` 去空白后的内容和 `RESULT_FORMAT_INSTRUCTION`，两者以空行分隔                                   | prompt suffix 双段叠加                              |
| `test_run_analysis_success_structured_result`   | mock `bot.run` 返回合法 JSON → SSE `event=result data.result` 含 `parsed=True`、`success/summary/details` 与原始解析一致；`agent.result` 与 SSE 同步；`raw_content` 保留原文 | 成功路径端到端                                      |
| `test_run_analysis_unparseable_result`          | bot.run 返回非 JSON → SSE `data.result.parsed=False`、`success=False`、`failure_reason` 含 "无法解析"，`summary=raw_content`；status=COMPLETED（解析失败不等于运行失败） | 兜底路径                                             |
| `test_run_analysis_exception_result_shape`      | `bot.run` 抛异常 → `agent.result == {"error": "..."}`（不经 ResultPayloadSchema）、status=FAILED；SSE result 事件 `data.error` 存在                                   | 异常路径 result 结构保持                           |
| `test_build_bot_prompt_suffix_without_template` | 当 `prompt_tpl.system_prompt` 为空字符串时，`extra_system_suffix` 只含 `RESULT_FORMAT_INSTRUCTION`                                                                  | 空模板兼容                                         |

### 12.17 API 路由（`app/api/v1/endpoints/agent.py`）

对应改动（TODO #22）：
- 新增 `CancelAgentRequestSchema` / `CancelAgentResponseSchema` / `ToolDescriptorSchema`（`app/schemas/agent/agent.py`）
- 新增 `POST /agent/cancel`：调用 `AnalystService.cancel_agent`，允许 cancelled=False 的 2xx 返回
- `GET /agent/configs/tools-list`：返回 `list(BUSINESS_TOOL_CLASSES.keys())`，替换旧占位
- `GET /agent/configs/tools`：返回 `ToolDescriptorSchema[]`，含 name/description/read_only/exclusive 元信息
- `GET /agent/configs/statistics`：返回 `{model_configs, prompt_templates, workspaces, agents, business_tools}` 计数
- 移除 `PLACEHOLDER_MESSAGE` 常量

共 26 条 `/agent/**` 路由，涵盖：/start、/status（SSE）、/approve、/cancel、Workspace CRUD×6、Agent CRUD×6、configs/models×3、configs/prompt-templates×5、configs/tools×2、configs/statistics×1。

**已实现单测文件**：  
- `tests/api/test_agent_router_registration.py`（路由注册回归：/agent/** 总数为 26）。  
- `tests/api/test_agent_misc_endpoints.py`（覆盖 `/agent/cancel`、`/agent/configs/tools`、`/agent/configs/tools-list`、`/agent/configs/statistics`）。  
- `tests/api/test_agent_placeholder_removed.py`（确认 `app/api/v1/endpoints/agent.py` 不再引用 `PLACEHOLDER_MESSAGE`）。  

| 用例                                           | 测试点                                                                                                                                       | 测试目标                                   |
| -------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------- | -------------------------------------- |
| `test_router_registers_all_26_endpoints`     | `include_router` 后 `app.routes` 中 `/agent/**` 数量 == 26，必备 `(method, path)` 全部命中                                                     | 路由注册回归                             |
| `test_get_tools_list_returns_business_names` | `GET /agent/configs/tools-list` → 200 / `code=0` / `data` 为 `BUSINESS_TOOL_CLASSES` 键集合（含 5 个默认业务工具）                             | 真实工具名暴露                           |
| `test_get_tools_returns_descriptors`         | `GET /agent/configs/tools` → 数据含 `name/description/read_only/exclusive`；`get_current_time.read_only=True`、`modify_entity.exclusive=True` | 工具元信息暴露正确                     |
| `test_get_tools_instance_failure_skipped`    | 当某个工具类 `__init__` 抛异常时，不影响其它工具返回，只打 WARN                                                                                             | 工具注册表健壮性                       |
| `test_get_statistics_aggregates_counts`      | mock 各 Model.find().count() 的返回值 → 统计响应精确匹配 mock 值；`business_tools == len(BUSINESS_TOOL_CLASSES)`                                  | 统计聚合正确                           |
| `test_post_cancel_with_running_task`         | mock `AnalystService.cancel_agent` → True；响应 `data.cancelled=True` + message="取消请求已发送"；`cancel_agent` 被以 `reason=<传入>` 唤醒        | 取消成功路径                           |
| `test_post_cancel_without_running_task`      | mock `AnalystService.cancel_agent` → False；响应 200 + `data.cancelled=False` + message="该 Agent 当前没有正在运行的任务"                        | 无任务仍 2xx                           |
| `test_post_cancel_missing_agent_id_422`      | POST body `{}` → 422                                                                                                                      | 必填校验                               |
| `test_post_cancel_default_reason`            | POST `{ "agent_id": "a1" }`（不传 reason） → `cancel_agent` 以 `reason="user cancel"` 被调用                                                 | 默认理由                               |
| `test_start_agent_uses_agent_id`             | `POST /agent/start` 以 `agent_id` / `user_prompt` 调用 `AnalystService.start_agent`；上下文注入 `entity_uuid/entity_type/extra_context`        | 启动路径接入                           |
| `test_start_agent_service_error_mapped`      | `AnalystService.start_agent` 抛 `AgentServiceError(code=..., message=...)` → 响应 2xx 且 `code=业务码`，`message` 与 `data` 透传                | 业务错误映射                           |
| `test_status_sse_event_stream_format`        | `GET /agent/status?agent_id=...` 订阅后，`broadcast_sse` 推送 → 流中收到 `event: <name>\ndata: <json>\n\n`；断连后走 `finally` 取消订阅               | SSE 流格式                             |
| `test_status_sse_keepalive_on_idle`          | 无事件到达时 15s 超时 → 流输出 `: keep-alive\n\n`                                                                                              | 连接保活                               |
| `test_approve_submits_to_analyst`            | `POST /agent/approve` 调用 `AnalystService.submit_approval(agent_id, decisions)`；响应 `code=0 message="批准决策已提交"`                       | 审批路径接入                           |
| `test_workspace_crud_routes`                 | create/list/list-brief/get/update/delete 端到端覆盖；`WorkspaceServiceError` 被映射为 `code=业务码` 返回 2xx                                    | Workspace CRUD + 错误映射            |
| `test_agent_crud_routes`                     | create/list/list-brief/get/update/delete 覆盖；workspace_id 过滤生效；`AgentServiceError` 被映射为业务码                                       | Agent CRUD + 错误映射                |
| `test_placeholder_removed`                   | 模块不再引用 `PLACEHOLDER_MESSAGE` 常量（grep 确认）                                                                                             | 占位清理                               |

### 12.18 清理回归（TODO #23）

对应改动：
- 确认 `app/service/agent/` 目录整体删除（本期只剩空 `__init__.py` + `__pycache__`，已一并移除）
- 确认 `app/models/agent/` 下仅保留 `nanobot.py`、`configs.py`，`agent.py` / `checkpoint.py` 已不存在
- `app/**` 源码中对 `from langchain` / `from langgraph` / `CheckpointModel` / `motor_checkpinter` / `agent_checkpointer` / `app.service.agent` 的引用全部为 0
- `pyproject.toml` 仅保留 `langchain-openai`（被 `app/utils/embedding.py` 业务模块使用，不属于 agent 栈），`langfuse` 被 `openai_compat_provider.py` 使用

**已实现单测文件**：`tests/cleanup/test_cleanup_regression.py`（静态扫描 + 导入链校验：旧路径缺失、app/tests 无禁用引用、`import app.main` 不加载 langgraph/旧 agent 链路、langchain 仅通过 embedding 允许的子集）。  

| 用例                                          | 测试点                                                                                                                                                  | 测试目标                         |
| ------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------- | ---------------------------- |
| `test_legacy_agent_paths_absent`            | `Path('app/service/agent').exists()` → False；`Path('app/models/agent/agent.py').exists()` → False；`Path('app/models/agent/checkpoint.py').exists()` → False | 目录/文件已移除                 |
| `test_no_forbidden_agent_imports_in_app`    | `rg -g 'app/**' 'app\\.service\\.agent\\.\|CheckpointModel\|motor_checkpinter\|agent_checkpointer\|from langgraph\|import langgraph'` 结果为空           | import 链路干净               |
| `test_main_import_chain_clean`              | `import app.main` 后，`sys.modules` 中不含 `langgraph` / `langchain.chat_models` / `langchain.agents` / `app.service.agent` / `app.models.agent.checkpoint` / `app.models.agent.agent` | 运行时也不会意外加载          |
| `test_langchain_core_only_via_embedding`    | `sys.modules` 中存在的 `langchain_*` 模块全部来自 `langchain_core` / `langchain_openai`，且可追溯至 `app.utils.embedding`                                      | 仅允许 embedding 业务保留    |
| `test_get_all_models_contains_7_nanobot`    | `get_all_models()` 返回的 Document 类集合名 ⊇ {`nanobot_agents, nanobot_workspaces, nanobot_sessions, nanobot_session_messages, nanobot_history, nanobot_history_state, nanobot_memory_docs`}，且不含任何 `*checkpointer*` 集合 | 新模型注册、旧模型彻底下线    |
| `test_tests_dir_no_legacy_references`       | `rg -g 'tests/**' 'CheckpointModel\|motor_checkpinter\|agent_checkpointer\|app\\.service\\.agent\\.'` 结果为空                                       | 单测侧也无旧引用              |

### 12.19 旧 MongoDB 集合核查（TODO #24）

对应改动（纯数据运维，无源码改动）：
- 使用 `.env` 配置连接 `csi_db`，`db.listCollectionNames()` 结果中**不包含** `agent_checkpointer` / `agent_checkpointer_writes`（也不含 `agent_analysis_sessions`）；全部 23 个集合中 7 个 `nanobot_*` 新集合齐全。
- 结论：本环境 drop 为 NOOP；记录命令以供其它环境（例如从旧快照恢复后）使用：

> **本仓库单测默认跳过本节**：该核查需要真实 MongoDB 环境与权限，不符合“无 DB 环境也能跑（mock/纯内存）”的测试约束。本节作为**手动运维检查清单**保留。

```js
// 需先通过 .env 的 MONGODB_USERNAME/PASSWORD 以 admin 身份认证
use csi_db;
db.agent_checkpointer.drop();           // 返回 true 表示存在并已删除；false 则原本不存在
db.agent_checkpointer_writes.drop();
// 可选：若早期曾使用 LangGraph analysis sessions，同步清理
// db.agent_analysis_sessions.drop();
```

| 用例                                          | 测试点                                                                                                                         | 测试目标                       |
| ------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------- | -------------------------- |
| `test_no_legacy_checkpointer_collections`   | 连接 `csi_db` 后，`list_collection_names()` 结果不包含 `agent_checkpointer` 与 `agent_checkpointer_writes`                    | 旧集合已下线                 |
| `test_seven_nanobot_collections_present`    | 同样的连接下，集合集合 ⊇ `{nanobot_agents, nanobot_workspaces, nanobot_sessions, nanobot_session_messages, nanobot_history, nanobot_history_state, nanobot_memory_docs}` | 新模型已落位                 |
| `test_drop_cmd_idempotent`                  | 在本地测试库对不存在的 `agent_checkpointer` 调用 `drop_collection` 应当不抛异常（或被明确捕获），保证命令可在任意环境重放                                          | drop 命令幂等                |

### 12.20 上述待实现模块的先行测试点（占位，后续 Step 完成时补实现）

| 用例簇                        | 对应 TODO | 核心测试点（摘要）                                                                                                                       |
| -------------------------- | ------- | ------------------------------------------------------------------------------------------------------------------------------- |
| `AgentLoop` 全 await         | #14     | step 流水正常推进，无 `asyncio` warning；中断→ paused / await approval / result 上报各走一遍                                                       |
| `Nanobot.from_components`   | #16     | 只需 `(agent_id, workspace_id, session_id)` 即可拼装可运行 bot，无文件依赖                                                                      |

---

*最后更新：接入 Workspace/Agent 分层架构后；实施过程中请同步更新各阶段完成情况。*