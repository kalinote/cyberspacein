# CSI 后端 API 接口说明与鉴权要求

本文档基于当前代码（`app/api/v1`）整理：**基准路径**为环境变量中的 `API_V1_STR`（一般为 `/api/v1`），下列路径均相对于该前缀。

**鉴权列含义：**

| 标记 | 含义 |
|------|------|
| **公开** | 无需 `Authorization`，任意客户端可调用 |
| **需登录** | 请求头需 `Authorization: Bearer <access_token>`，校验通过即可 |
| **需登录 + 权限** | 在「需登录」基础上，还需具备所列权限码（任一缺失则返回业务码 `240300`） |

**建议列含义：** 与当前代码实现对照后的后续加固方向（含与前端路由权限 `PERM`、业务风险相关的约定），**非已实现行为**；落地时在路由上增加 `Depends(get_current_user)` / `require_permissions` 并在权限组中配置对应码。

> 说明：除下表明确标注的接口外，其余接口在代码中**均未**注入 `get_current_user` / `require_permissions`，即当前实现为**公开可调用**（仅依赖业务层自身校验）。

---

## 1. 认证鉴权 `/auth`

| 方法 | 路径 | 功能描述 | 鉴权 | 建议 |
|------|------|----------|------|------|
| POST | `/auth/login` | 用户名密码登录，返回 `access_token`、用户信息、权限码列表 | **公开** | 保持公开；生产环境建议 HTTPS、登录限流（账号+IP） |
| POST | `/auth/logout` | 退出登录（当前实现为无状态，不吊销 token） | **需登录** | 保持需登录；若需「立即失效」可后续接会话黑名单或 refresh 吊销 |
| GET | `/auth/me` | 获取当前用户信息与权限码列表 | **需登录** | 保持需登录；可与前端路由守卫、`permissions` 缓存策略一致 |

---

## 2. 系统用户与权限 `/system`

| 方法 | 路径 | 功能描述 | 鉴权 | 建议 |
|------|------|----------|------|------|
| GET | `/system/users` | 分页获取用户列表 | **需登录 + 权限** `system:user:view` | 保持现状；权限码与用户组配置、权限字典一致 |
| POST | `/system/users` | 创建用户 | **需登录 + 权限** `system:user:create` | 同上 |
| PUT | `/system/users/{user_id}` | 更新用户 | **需登录 + 权限** `system:user:edit` | 同上 |
| PATCH | `/system/users/{user_id}/status` | 修改用户启用/禁用状态 | **需登录 + 权限** `system:user:disable` | 同上；禁用操作建议记审计日志 |
| GET | `/system/groups` | 分页获取用户组（权限组）列表 | **需登录 + 权限** `system:group:view` | 同上 |
| POST | `/system/groups` | 创建用户组 | **需登录 + 权限** `system:group:create` | 同上 |
| PUT | `/system/groups/{group_id}` | 更新用户组（含组内权限码） | **需登录 + 权限** `system:group:edit` | 同上；变更组权限影响面大，建议审计 |
| GET | `/system/perm-codes` | 获取权限码字典列表（支持分类、标签、关键字筛选） | **需登录 + 权限** `system:permcode:view` | 同上 |
| POST | `/system/perm-codes` | 创建单条权限码 | **需登录 + 权限** `system:permcode:create` | 同上 |
| POST | `/system/perm-codes/batch` | 批量创建权限码 | **需登录 + 权限** `system:permcode:create` | 同上 |
| PUT | `/system/perm-codes/{perm_code_id}` | 更新权限码 | **需登录 + 权限** `system:permcode:edit` | 同上 |
| DELETE | `/system/perm-codes/{perm_code_id}` | 删除权限码（软删除） | **需登录 + 权限** `system:permcode:delete` | 同上 |

---

## 3. 分析引擎 `/agent`

| 方法 | 路径 | 功能描述 | 鉴权 | 建议 |
|------|------|----------|------|------|
| POST | `/agent/configs/models` | 新增模型配置 | **公开**（代码未鉴权） | 需登录 + 配置类权限（如 `page:agent:use` + 写权限细分）；避免匿名改配置 |
| GET | `/agent/configs/models` | 分页查询模型配置列表 | **公开** | 需登录 + `page:agent:use` 或 `agent:config:view` |
| GET | `/agent/configs/models-list` | 查询模型配置名称列表 | **公开** | 同上 |
| POST | `/agent/configs/prompt-templates` | 新增提示词模板 | **公开** | 需登录 + 模板/配置写权限 |
| GET | `/agent/configs/prompt-templates` | 分页查询提示词模板列表 | **公开** | 需登录 + 读权限 |
| GET | `/agent/configs/prompt-template/{prompt_template_id}` | 查询提示词模板详情 | **公开** | 需登录 + 读权限 |
| PUT | `/agent/configs/prompt-template/{prompt_template_id}` | 编辑提示词模板 | **公开** | 需登录 + 写权限 |
| POST | `/agent/agents` | 创建分析引擎 | **公开** | 需登录 + 引擎配置写权限 |
| GET | `/agent/agents` | 分页查询分析引擎列表 | **公开** | 需登录 + `page:agent:use` |
| GET | `/agent/configs/agents-list` | 查询分析引擎名称列表 | **公开** | 需登录 + 读权限 |
| GET | `/agent/configs/tools` | 查询工具列表 | **公开** | 需登录 + 读权限 |
| GET | `/agent/configs/tools-list` | 查询工具名称列表 | **公开** | 需登录 + 读权限 |
| GET | `/agent/configs/statistics` | 配置资源数量统计 | **公开** | 需登录 + 读权限 |
| POST | `/agent/start` | 启动分析引擎会话 | **公开** | 需登录 + `page:agent:use`；与会话资源占用相关，建议限流 |
| GET | `/agent/status` | 获取会话状态（SSE 流式） | **公开** | 需登录 + 仅能访问本人 `thread_id` 或同组织会话（需会话归属校验） |
| POST | `/agent/approve` | 提交行为批准 | **公开** | 需登录 + 与会话绑定的批准权限；校验 `thread_id` 归属 |

---

## 4. 嵌入向量 `/embedding`

| 方法 | 路径 | 功能描述 | 鉴权 | 建议 |
|------|------|----------|------|------|
| POST | `/embedding` | 获取文本向量 | **公开** | 需登录或仅内网；对外建议限流、防滥用；或独立 API Key |
| POST | `/embedding/batch` | 批量获取文本向量 | **公开** | 同上；批量更需限流与大小上限 |

---

## 5. 重点目标 `/highlight`

| 方法 | 路径 | 功能描述 | 鉴权 | 建议 |
|------|------|----------|------|------|
| PUT | `/highlight/{entity_type}/{uuid}` | 设置或取消重点目标标记（实体类型：article / forum） | **公开** | 需登录 + `page:target:use`；写操作与 ES 数据一致性与审计 |

---

## 6. 文章 `/article`

| 方法 | 路径 | 功能描述 | 鉴权 | 建议 |
|------|------|----------|------|------|
| GET | `/article/detail/{uuid}` | 获取文章详情 | **公开** | 若产品允许匿名读可保持公开；否则需登录 + `page:search:view` 或与检索一致 |

---

## 7. 论坛 `/forum`

| 方法 | 路径 | 功能描述 | 鉴权 | 建议 |
|------|------|----------|------|------|
| GET | `/forum/detail/{uuid}` | 获取论坛详情 | **公开** | 同文章详情策略 |
| GET | `/forum/comments` | 分页查询评论或点评 | **公开** | 同详情策略；若仅登录用户可看评论则需登录 |

---

## 8. 时间线 `/timeline`

| 方法 | 路径 | 功能描述 | 鉴权 | 建议 |
|------|------|----------|------|------|
| GET | `/timeline/{entity_type}/{source_id}` | 分页获取指定 source_id 的时间线数据 | **公开** | 与文章/论坛详情可见性策略一致 |
| GET | `/timeline/{entity_type}/{uuid}/diff-compare` | 获取指定 uuid 的 raw_content 用于变更对比 | **公开** | 建议需登录；内容敏感时做数据范围校验 |

---

## 9. 搜索 `/search`

| 方法 | 路径 | 功能描述 | 鉴权 | 建议 |
|------|------|----------|------|------|
| POST | `/search/entity` | 搜索实体 | **公开** | 需登录 + `page:search:use`；大查询建议限流 |
| POST | `/search/template` | 创建检索模板 | **公开** | 需登录 + 模板写权限 |
| GET | `/search/templates` | 分页获取检索模板列表 | **公开** | 需登录 + 仅本人/本组织模板（数据范围） |
| GET | `/search/template/{template_id}` | 获取检索模板详情 | **公开** | 同上 + 资源可见性 |
| PUT | `/search/template/{template_id}` | 更新检索模板 | **公开** | 需登录 + 写权限 + 归属校验 |
| DELETE | `/search/template/{template_id}` | 删除检索模板 | **公开** | 需登录 + 删除权限 + 归属校验 |

---

## 10. 批注 `/annotation`

| 方法 | 路径 | 功能描述 | 鉴权 | 建议 |
|------|------|----------|------|------|
| GET | `/annotation/list` | 按实体查询批注列表 | **公开** | 需登录 + 与实体访问权限一致 |
| POST | `/annotation` | 创建批注 | **公开** | 需登录 + 写权限；建议记录操作者 |
| PUT | `/annotation/{annotation_id}` | 更新批注 | **公开** | 需登录 + 仅作者或管理员可改 |
| DELETE | `/annotation/{annotation_id}` | 删除批注 | **公开** | 需登录 + 删除权限 + 归属校验 |

---

## 11. 平台管理 `/platform`

| 方法 | 路径 | 功能描述 | 鉴权 | 建议 |
|------|------|----------|------|------|
| POST | `/platform` | 创建平台 | **公开** | 需登录 + 平台管理写权限（如后续定义 `platform:*`） |
| GET | `/platform/list` | 分页获取平台列表 | **公开** | 需登录 + 读权限 |
| GET | `/platform/detail/{platform_id}` | 获取平台详情 | **公开** | 需登录 + 读权限 |
| GET | `/platform/filter/platforms` | 平台过滤器列表 | **公开** | 需登录 + 读权限 |

---

## 12. HTML 静态分析 `/html-analyze`

| 方法 | 路径 | 功能描述 | 鉴权 | 建议 |
|------|------|----------|------|------|
| POST | `/html-analyze/extract-text` | 提取 HTML 中的纯文本 | **公开** | 需登录或内网；防滥用建议限流 |
| POST | `/html-analyze/clean` | 清理 HTML 标签与脚本 | **公开** | 同上 |
| POST | `/html-analyze/extract-links` | 提取 HTML 中资源链接 | **公开** | 同上 |
| POST | `/html-analyze/extract-text-batch` | 批量提取纯文本 | **公开** | 同上；批量接口优先限流与 body 大小限制 |
| POST | `/html-analyze/clean-batch` | 批量清理 HTML | **公开** | 同上 |
| POST | `/html-analyze/extract-links-batch` | 批量提取链接 | **公开** | 同上 |

---

## 13. 行动模块（前缀 `/action`）

以下子路由均挂载在 `/action` 下；**鉴权**列反映**当前代码**（均未注入鉴权依赖，均为 **公开**）。**建议**列为与前端「行动部署」「任务」「资源配置」等能力对齐的加固方向。

### 13.1 行动实例（无额外子前缀）

| 方法 | 路径 | 功能描述 | 鉴权 | 建议 |
|------|------|----------|------|------|
| POST | `/action/start` | 开始行动 | **公开**（代码未鉴权） | 需登录 + `page:action:use`；后续可按蓝图/任务拆 `action:task:create` 等 |
| GET | `/action/list` | 分页获取行动列表 | **公开** | 需登录 + `page:action:use`；列表建议接数据范围（owner/组织） |
| GET | `/action/detail/{action_id}` | 获取行动详情 | **公开** | 需登录 + 读权限 + 单条资源可见性校验 |

### 13.2 行动蓝图 `/action/blueprint`

| 方法 | 路径 | 功能描述 | 鉴权 | 建议 |
|------|------|----------|------|------|
| POST | `/action/blueprint` | 创建蓝图 | **公开** | 需登录 + `page:action:use`；写操作可对应 `agent:config:create` 或蓝图专用码 |
| GET | `/action/blueprint/list` | 分页获取蓝图列表 | **公开** | 需登录 + 读权限 + 数据范围 |
| GET | `/action/blueprint/detail/{blueprint_id}` | 获取蓝图详情 | **公开** | 需登录 + 资源可见性 |

### 13.3 行动资源 `/action/resource`

| 方法 | 路径 | 功能描述 | 鉴权 | 建议 |
|------|------|----------|------|------|
| GET | `/action/resource/nodes` | 获取节点列表 | **公开** | 需登录 + 行动资源配置读权限 |
| POST | `/action/resource/nodes` | 创建节点 | **公开** | 需登录 + 节点/资源写权限 |
| GET | `/action/resource/nodes/{node_id}` | 获取节点详情 | **公开** | 需登录 + 读权限 |
| PUT | `/action/resource/nodes/{node_id}` | 修改节点 | **公开** | 需登录 + 写权限 |
| DELETE | `/action/resource/nodes/{node_id}` | 删除节点 | **公开** | 需登录 + 删除类高风险权限；建议二次确认与审计 |
| GET | `/action/resource/base_components` | 分页获取基础组件列表 | **公开** | 需登录 + 读权限 |

### 13.4 行动 SDK `/action/sdk`

| 方法 | 路径 | 功能描述 | 鉴权 | 建议 |
|------|------|----------|------|------|
| GET | `/action/sdk/{node_instance_id}/init` | 获取节点配置初始化数据 | **公开** | 运行时调用：建议内网/mTLS/工作负载身份；若公网必须鉴权并校验 `node_instance_id` |
| POST | `/action/sdk/{node_instance_id}/result` | 上报节点配置结果 | **公开** | 同上；防止伪造上报建议签名校验或短期令牌 |
| POST | `/action/sdk/{node_instance_id}/heartbeat` | 上报节点心跳 | **公开** | 同上 |

### 13.5 节点配置 `/action/configs`

| 方法 | 路径 | 功能描述 | 鉴权 | 建议 |
|------|------|----------|------|------|
| GET | `/action/configs/statistics` | 获取节点配置统计信息 | **公开** | 需登录 + 节点配置读权限 |
| GET | `/action/configs/handles/all` | 获取所有节点配置 handle 列表 | **公开** | 需登录 + 读权限 |
| GET | `/action/configs/handles` | 分页获取节点配置 handle 列表 | **公开** | 需登录 + 读权限 |
| POST | `/action/configs/handles` | 创建节点配置 handle | **公开** | 需登录 + 写权限 |
| GET | `/action/configs/filter/node_type` | 获取节点类型过滤列表 | **公开** | 需登录 + 读权限 |

### 13.6 基础组件任务 `/action/components-task`

| 方法 | 路径 | 功能描述 | 鉴权 | 建议 |
|------|------|----------|------|------|
| POST | `/action/components-task/configs` | 创建基础组件任务配置 | **公开** | 需登录 + `page:action:task:use`；配置写权限可细分 |
| GET | `/action/components-task/configs` | 分页获取任务配置列表 | **公开** | 需登录 + `page:action:task:use` + 数据范围 |
| GET | `/action/components-task/configs/detail/{config_id}` | 获取任务配置详情 | **公开** | 需登录 + 资源可见性 |
| PATCH | `/action/components-task/configs/{config_id}` | 更新任务配置 | **公开** | 需登录 + 写权限 |
| DELETE | `/action/components-task/configs/{config_id}` | 删除任务配置 | **公开** | 需登录 + 删除权限 |
| GET | `/action/components-task/tasks` | 分页获取基础组件任务列表 | **公开** | 需登录 + `page:action:task:use` |
| GET | `/action/components-task/schedules` | 分页获取调度计划列表 | **公开** | 需登录 + 同上 |

### 13.7 账号管理（任务/站点账号）`/action/accounts`

| 方法 | 路径 | 功能描述 | 鉴权 | 建议 |
|------|------|----------|------|------|
| POST | `/action/accounts` | 创建账号 | **公开** | 需登录 + 任务账号管理权限；**勿**与系统用户 `auth_users` 混淆 |
| GET | `/action/accounts/list` | 分页获取账号列表 | **公开** | 需登录 + 读权限 + 数据范围 |
| GET | `/action/accounts/detail/{account_id}` | 获取账号详情 | **公开** | 需登录 + 详情可见性；敏感字段脱敏 |
| PATCH | `/action/accounts/{account_id}` | 更新账号 | **公开** | 需登录 + 写权限；密码类字段禁止日志明文 |
| DELETE | `/action/accounts/{account_id}` | 删除账号（软删除） | **公开** | 需登录 + 删除权限 |

### 13.8 沙盒 `/action/sandbox`

| 方法 | 路径 | 功能描述 | 鉴权 | 建议 |
|------|------|----------|------|------|
| POST | `/action/sandbox/create` | 创建沙盒 | **公开** | 需登录 + 沙盒/资源类写权限；高成本操作建议配额与审计 |
| DELETE | `/action/sandbox/{sandbox_id}` | 销毁沙盒 | **公开** | 需登录 + 删除权限 + 归属校验 |
| GET | `/action/sandbox/list` | 分页沙盒列表 | **公开** | 需登录 + 列表数据范围 |
| GET | `/action/sandbox/detail/{sandbox_id}` | 沙盒详情 | **公开** | 需登录 + 单条可见性 |

---

## 14. 统计摘要

| 类别 | 说明 |
|------|------|
| **明确需登录** | `/auth/logout`、`/auth/me` |
| **明确需登录 + 权限码** | 全部 `/system/*` 接口（见第 2 节） |
| **明确公开** | `/auth/login` |
| **当前未加鉴权依赖** | 除上述 `/auth/*`（除 login）与 `/system/*` 外的所有业务接口；表中 **鉴权** 标为 **公开** 或 **公开（代码未鉴权）**，**建议** 列为后续在代码中补充 `Depends(get_current_user)`、`require_permissions` 及数据范围时的参考。 |

---

*文档随路由实现变更，以 `app/api/v1/endpoints` 下代码为准。*
