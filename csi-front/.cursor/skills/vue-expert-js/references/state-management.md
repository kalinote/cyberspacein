# 状态管理

---

## 初始化

```javascript
// main.js
import { createApp } from 'vue'
import { createPinia } from 'pinia'
import App from './App.vue'

createApp(App).use(createPinia()).mount('#app')
```

---

## 选项式 Store

```javascript
// stores/counter.js
import { defineStore } from 'pinia'

export const useCounterStore = defineStore('counter', {
  state: () => ({
    count: 0,
    name: 'Counter'
  }),

  getters: {
    doubleCount: (state) => state.count * 2,
    countPlusN: (state) => (n) => state.count + n
  },

  actions: {
    increment() {
      this.count++
    },
    /** @param {number} amount */
    incrementBy(amount) {
      this.count += amount
    }
  }
})
```

---

## 组合式 Store（Setup 语法）

```javascript
// stores/user.js
import { defineStore } from 'pinia'
import { ref, computed } from 'vue'

/**
 * @typedef {Object} User
 * @property {number} id
 * @property {string} name
 * @property {string} email
 */

export const useUserStore = defineStore('user', () => {
  /** @type {import('vue').Ref<User | null>} */
  const currentUser = ref(null)
  const isLoading = ref(false)
  const error = ref(null)

  const isLoggedIn = computed(() => currentUser.value !== null)
  const userName = computed(() => currentUser.value?.name ?? 'Guest')

  async function login(email, password) {
    isLoading.value = true
    error.value = null
    try {
      const res = await fetch('/api/login', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email, password })
      })
      currentUser.value = (await res.json()).user
      return true
    } catch (e) {
      error.value = e.message
      return false
    } finally {
      isLoading.value = false
    }
  }

  function logout() {
    currentUser.value = null
  }

  return { currentUser, isLoading, error, isLoggedIn, userName, login, logout }
})
```

---

## 在组件中使用 Store

```vue
<script setup>
import { useUserStore } from '@/stores/user'
import { storeToRefs } from 'pinia'

const userStore = useUserStore()

const { currentUser, isLoggedIn, isLoading } = storeToRefs(userStore)
const { login, logout } = userStore
</script>

<template>
  <div v-if="isLoading">加载中...</div>
  <div v-else-if="isLoggedIn">
    欢迎，{{ currentUser?.name }}
    <button @click="logout">退出</button>
  </div>
</template>
```

---

## Store 组合

```javascript
// stores/cart.js
import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { useProductsStore } from './products'
import { useUserStore } from './user'

export const useCartStore = defineStore('cart', () => {
  const items = ref([])

  const productsStore = useProductsStore()
  const userStore = useUserStore()

  const total = computed(() =>
    items.value.reduce((sum, item) => {
      const product = productsStore.items.find(p => p.id === item.productId)
      return sum + (product?.price ?? 0) * item.quantity
    }, 0)
  )

  function addItem(productId, quantity = 1) {
    const existing = items.value.find(i => i.productId === productId)
    if (existing) existing.quantity += quantity
    else items.value.push({ productId, quantity })
  }

  async function checkout() {
    if (!userStore.isLoggedIn) throw new Error('请先登录')
    await fetch('/api/checkout', {
      method: 'POST',
      body: JSON.stringify({ userId: userStore.currentUser.id, items: items.value })
    })
    items.value = []
  }

  return { items, total, addItem, checkout }
})
```

---

## 持久化

```javascript
// stores/settings.js
import { defineStore } from 'pinia'
import { ref, watch } from 'vue'

const STORAGE_KEY = 'app-settings'

function loadFromStorage() {
  try {
    return JSON.parse(localStorage.getItem(STORAGE_KEY)) ?? {}
  } catch {
    return {}
  }
}

export const useSettingsStore = defineStore('settings', () => {
  const saved = loadFromStorage()

  const theme = ref(saved.theme ?? 'light')
  const language = ref(saved.language ?? 'en')

  watch([theme, language], () => {
    localStorage.setItem(STORAGE_KEY, JSON.stringify({
      theme: theme.value,
      language: language.value
    }))
  })

  return { theme, language }
})
```

---

## 测试 Store

```javascript
// stores/__tests__/counter.test.js
import { describe, it, expect, beforeEach } from 'vitest'
import { setActivePinia, createPinia } from 'pinia'
import { useCounterStore } from '../counter'

describe('Counter Store', () => {
  beforeEach(() => setActivePinia(createPinia()))

  it('increments count', () => {
    const store = useCounterStore()
    store.increment()
    expect(store.count).toBe(1)
  })

  it('computes double count', () => {
    const store = useCounterStore()
    store.count = 5
    expect(store.doubleCount).toBe(10)
  })
})
```

---

## 速查

| 功能 | 选项式 | Setup 式 |
|------|--------|----------|
| 状态 | `state: () => ({})` | `const x = ref()` |
| 计算属性 | `getters: { x: (state) => }` | `const x = computed()` |
| 方法 | `actions: { fn() {} }` | `function fn() {}` |
| 组件中使用 | `storeToRefs()` 取状态 | 同上 |
| 重置状态 | `store.$reset()` | 自行实现重置函数 |
| 订阅 | `store.$subscribe((mutation, state) => {})` | 同上 |
| 使用其他 store | 在 actions 里用 | 在 setup 顶层调用 |
