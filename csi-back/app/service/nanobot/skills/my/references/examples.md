# `my` 工具 — 场景示例

按常见中文对话场景说明何时、如何调用 `my`。工具参数名保持英文，与实现一致。

## 排查类

### 用户问："怎么停了？""做到一半怎么不继续了？"

```
→ my(action="check", key="max_iterations")
  → 40
→ my(action="check", key="_last_usage")
  → {"prompt_tokens": 62000, "completion_tokens": 3000}
→ 向用户说明："本轮已达到工具迭代上限（40 次），任务较复杂。如需继续，可征得同意后调高 max_iterations。"
```

### 用户问："你现在用的什么模型？"

```
→ my(action="check", key="model")
  → 'anthropic/claude-sonnet-4-20250514'
→ 用自然语言告知当前模型名称即可，无需堆砌内部字段名。
```

## 按任务调参

### 大型代码库分析，上下文可能不够

```
→ my(action="check")
  → context_window_tokens: 65536
→ my(action="set", key="context_window_tokens", value=131072)
  → "Set context_window_tokens = 131072 (was 65536)"
→ 告知用户："已把上下文窗口从 6.5 万扩大到 12.8 万 Token，便于通读大仓库。"
```

### 批量简单任务，可换更快模型

```
→ my(action="set", key="model", value="anthropic/claude-haiku-4-5-20251001")
  → "Set model = '...haiku...' (was '...sonnet...')"
→ 告知用户："后续批量操作将改用更快模型，以节省时间和成本。"
```

## 会话便签（跨轮）

### 用户说："以后回答简短点"

```
# 第 1 轮
→ my(action="set", key="user_style", value="concise")
  → "Set scratchpad.user_style = 'concise'"

# 第 3 轮，话题已换
→ my(action="check", key="user_style")
  → 'concise'
→ 回复保持简练，不必用户重复提醒。
```

### 摸清当前项目上下文（仅本会话有效）

```
→ my(action="set", key="active_branch", value="feat/auth")
→ my(action="set", key="test_framework", value="pytest")
→ my(action="set", key="has_docker", value=true)
```

后续改代码、跑测试时可 `check` 上述键，避免反复问用户。

## 控制 Token 消耗

### 上下文已占用较多，后续宜收敛

```
→ my(action="check", key="_last_usage")
  → {"prompt_tokens": 58000, "completion_tokens": 12000}
→ 主动说明："本轮已消耗约 7 万 Token，后续我会尽量精简回复与工具输出。"
```
