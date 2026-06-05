---
name: memory
description: 基于 Mongo 的两层记忆体系，长期内容由 Dream 自动维护。
always: true
---

# Memory

## 结构

- **SOUL**：Bot 个性与沟通风格，由 Dream 写入 Mongo，**请勿手动修改**。
- **USER**：用户画像与偏好，由 Dream 维护，**请勿手动修改**。
- **MEMORY**：长期事实（项目背景、重要决策等），由 Dream 维护，**请勿手动修改**。
- **history**：按 workspace 追加的会话摘要流，由 Consolidator 写入；运行时通过 system prompt 的 `Recent History` 段落可见近期条目，完整检索能力后续通过专用工具提供。

## 使用说明

- 若发现记忆过时，说明即可；下次 Dream 触发时会尝试修正。
- 不要尝试直接编辑 SOUL / USER / MEMORY 文档；本后端无文件系统记忆路径。
- 需要回顾更早会话时，优先阅读 system prompt 中的 `Recent History`；更深层检索待后续接口支持。
