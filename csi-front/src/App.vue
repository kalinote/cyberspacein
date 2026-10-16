<template>
  <div :class="{ 'mobile-app': mobileShell, 'mobile-keyboard-open': keyboardOpen }">
    <MobileNavigation v-if="mobileShell" />
    <router-view v-slot="{ Component }">
      <keep-alive :key="cacheIdentity" :include="cachedViewNames">
        <component :is="Component" />
      </keep-alive>
    </router-view>
  </div>
</template>

<script setup>
import { computed, nextTick, watch, watchEffect } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { getAuthState } from '@/stores/auth'
import { rememberRecentVisit } from '@/stores/recentVisits'
import { useMobileViewport } from '@/composables/useMobileViewport'
import MobileNavigation from '@/components/mobile/MobileNavigation.vue'

defineOptions({ name: 'App' })

const router = useRouter()
const route = useRoute()
const { isMobile, keyboardOpen, viewportHeight, viewportTop, keyboardOffset } = useMobileViewport()
const mobileShell = computed(() => isMobile.value && Boolean(getAuthState().accessToken) && route.name !== 'login')
const cacheIdentity = computed(() => getAuthState().sessionId || getAuthState().accessToken || 'anonymous')

watch(() => [route.fullPath, cacheIdentity.value], () => rememberRecentVisit(route), { immediate: true })

watchEffect(() => {
  const style = document.documentElement.style
  style.setProperty('--mobile-viewport-height', `${viewportHeight.value}px`)
  style.setProperty('--mobile-viewport-top', `${viewportTop.value}px`)
  style.setProperty('--mobile-keyboard-offset', `${keyboardOffset.value}px`)
})

watch([keyboardOpen, viewportHeight], async ([open]) => {
  if (!open) return
  await nextTick()
  // 等弹层适应键盘高度后，将正在编辑的字段滚动到可见区域。
  document.activeElement?.scrollIntoView?.({ block: 'nearest', inline: 'nearest' })
})
const cachedViewNames = computed(() => {
  return router.getRoutes()
    .filter(r => r.meta?.keepAlive)
    .map(r => {
      if (r.meta?.cacheName) return r.meta.cacheName
      const comp = r.components?.default ?? r.component
      return comp?.name
    })
    .filter(Boolean)
})
</script>
