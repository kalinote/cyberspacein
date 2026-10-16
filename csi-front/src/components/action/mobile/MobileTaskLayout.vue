<template>
  <div>
    <Header />
    <main class="mobile-action-page">
      <h1>定时任务</h1>
      <nav class="mobile-task-tabs" aria-label="任务分类">
        <button v-for="item in navItems" :key="item.key" type="button" :class="{ active: selected === item.key }" :aria-current="selected === item.key ? 'page' : undefined" @click="selected = item.key">{{ item.label }}</button>
      </nav>
      <slot name="toolbar" />
      <slot />
    </main>
  </div>
</template>
<script setup>
import Header from '@/components/Header.vue'
defineProps({ navItems: { type: Array, default: () => [] }, titlePrefix: String, titleSuffix: String, subtitle: String, sidebarTitle: String, getBadge: Function })
const selected = defineModel({ type: String, default: 'tasks' })
</script>
<style scoped>
.mobile-task-tabs { display: flex; gap: 8px; margin: 16px 0; padding: 4px; border-radius: 12px; background: #e2e8f0; }
.mobile-task-tabs button { flex: 1; min-height: 44px; padding: 8px; border: 0; border-radius: 9px; color: #475569; background: none; font-size: 15px; }
.mobile-task-tabs button.active { background: #fff; color: #2563eb; font-weight: 600; box-shadow: 0 1px 3px #0f172a12; }
</style>
