<template>
  <router-view v-slot="{ Component }">
    <keep-alive :include="cachedViewNames">
      <component :is="Component" />
    </keep-alive>
  </router-view>
</template>

<script setup>
import { computed } from 'vue'
import { useRouter } from 'vue-router'

defineOptions({ name: 'App' })

const router = useRouter()
const cachedViewNames = computed(() => {
  return router.getRoutes()
    .filter(r => r.meta?.keepAlive)
    .map(r => {
      const comp = r.components?.default ?? r.component
      return comp?.name
    })
    .filter(Boolean)
})
</script>
