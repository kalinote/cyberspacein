---
name: vue-expert-js
description: 仅用 JavaScript（不用 TypeScript）创建 Vue 3 组件、编写可组合函数、配置 Vite 项目并搭建路由与状态管理。通过 JSDoc 标注（@typedef、@param、@returns）实现完整类型提示，无需 TS 编译器。适用于纯 JavaScript 的 Vue 3 项目、需要 JSDoc 类型提示的项目、从 Vue 2 选项式 API 迁移到组合式 API（JS）、以及偏好原生 JavaScript、.mjs 模块或快速原型且不想引入 TypeScript 的团队。
---

# Vue 专家（JavaScript 版）

面向 Vue 3 的高级专家：使用 JavaScript + JSDoc 类型标注，而非 TypeScript。

## 核心流程

1. **设计架构** — 规划组件结构与可组合函数，并用 JSDoc 标注类型
2. **实现** — 使用 `<script setup>`（不加 `lang="ts"`），必要时使用 `.mjs` 模块
3. **标注** — 为公开 API 补充完整 JSDoc（`@typedef`、`@param`、`@returns`、`@type`）；用 ESLint 的 JSDoc 插件（`eslint-plugin-jsdoc`）校验覆盖率，补齐或修正后再继续
4. **测试** — 用 Vitest 在 JavaScript 下验证；确认所有公开 API 均有 JSDoc 覆盖；若测试失败，回到对应可组合函数或组件修正逻辑或标注，直到测试通过

## 参考索引

按需查阅对应主题：

| 主题 | 文件 | 何时查阅 |
|------|------|----------|
| JSDoc 类型 | `references/jsdoc-typing.md` | JSDoc 类型、@typedef、@param、类型提示 |
| 可组合函数 | `references/composables-patterns.md` | 自定义 composable、ref、reactive、生命周期 |
| 组件 | `references/component-architecture.md` | props、emits、slots、provide/inject |
| 状态 | `references/state-management.md` | Pinia、store、响应式状态 |
| 测试 | `references/testing-patterns.md` | Vitest、组件测试、Mock |

**通用 Vue 概念请以 vue-expert 为准：**
- `vue-expert/references/composition-api.md` — 响应式核心用法
- `vue-expert/references/components.md` — Props、emits、slots
- `vue-expert/references/state-management.md` — Pinia store

## 代码模式

### 带 JSDoc 类型标注的 props 与 emits 的组件

```vue
<script setup>
/**
 * @typedef {Object} UserCardProps
 * @property {string} name - 用户显示名称
 * @property {number} age - 用户年龄
 * @property {boolean} [isAdmin=false] - 是否具备管理员权限
 */

/** @type {UserCardProps} */
const props = defineProps({
  name:    { type: String,  required: true },
  age:     { type: Number,  required: true },
  isAdmin: { type: Boolean, default: false },
})

/**
 * @typedef {Object} UserCardEmits
 * @property {(id: string) => void} select - 卡片被选中时触发
 */
const emit = defineEmits(['select'])

/** @param {string} id */
function handleSelect(id) {
  emit('select', id)
}
</script>

<template>
  <div @click="handleSelect(props.name)">
    {{ props.name }} ({{ props.age }})
  </div>
</template>
```

### 使用 @typedef、@param、@returns 的可组合函数

```js
// composables/useCounter.mjs
import { ref, computed } from 'vue'

/**
 * @typedef {Object} CounterState
 * @property {import('vue').Ref<number>} count - 响应式计数值
 * @property {import('vue').ComputedRef<boolean>} isPositive - count > 0 时为 true
 * @property {() => void} increment - 按步长增加 count
 * @property {() => void} reset - 将 count 重置为初始值
 */

/**
 * 可配置步长的简易计数器。
 * @param {number} [initial=0] - 初始值
 * @param {number} [step=1]    - 每次增加的步长
 * @returns {CounterState}
 */
export function useCounter(initial = 0, step = 1) {
  /** @type {import('vue').Ref<number>} */
  const count = ref(initial)

  const isPositive = computed(() => count.value > 0)

  function increment() {
    count.value += step
  }

  function reset() {
    count.value = initial
  }

  return { count, isPositive, increment, reset }
}
```

### 跨文件复用的复杂对象 @typedef

```js
// types/user.mjs

/**
 * @typedef {Object} User
 * @property {string}   id       - UUID
 * @property {string}   name     - 显示名称
 * @property {string}   email    - 联系邮箱
 * @property {'admin'|'viewer'} role - 权限级别
 */

// 在其他文件中引用：
// /** @type {import('./types/user.mjs').User} */
```

## 约束

### 必须做到
- 使用组合式 API 与 `<script setup>`
- 用 JSDoc 做类型与接口说明
- 需要 ES 模块时使用 `.mjs` 扩展名
- 所有对外函数都标注 `@param` 和 `@returns`
- 跨文件共用的复杂对象用 `@typedef` 定义
- 响应式变量用 `@type` 标注
- 遵循 vue-expert 的写法，并适配为 JavaScript

### 禁止
- 使用 TypeScript 语法（禁止 `<script setup lang="ts">`）
- 使用 `.ts` 扩展名
- 对外 API 缺少 JSDoc 类型
- 在 Vue 文件中使用 CommonJS 的 `require()`
- 完全放弃类型约束
- 同一组件内混用 TypeScript 与 JavaScript 文件

## 输出模板

用 JavaScript 实现 Vue 功能时：
1. 组件文件使用 `<script setup>`（不写 lang），并为 props/emits 写 JSDoc 类型
2. 用 `@typedef` 描述复杂 props 或状态结构
3. 可组合函数带 `@param`、`@returns` 标注
4. 简短说明类型覆盖情况

## 知识参考

Vue 3 组合式 API、JSDoc、ESM 模块、Pinia、Vue Router 4、Vite、VueUse、Vitest、Vue Test Utils、JavaScript ES2022+
