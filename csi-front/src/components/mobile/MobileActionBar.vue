<template>
  <div v-if="isMobile" class="mobile-action-space">
    <div v-show="!keyboardOpen" class="mobile-action-bar" role="toolbar" :aria-label="ariaLabel">
      <slot />
    </div>
  </div>
</template>

<script setup>
import { useMobileViewport } from '@/composables/useMobileViewport'

defineProps({ ariaLabel: { type: String, default: '页面操作' } })
const { isMobile, keyboardOpen } = useMobileViewport()
</script>

<style scoped>
.mobile-action-space { height: 76px; }
.mobile-action-bar {
  position: fixed;
  z-index: 90;
  bottom: var(--mobile-nav-height);
  left: 0;
  right: 0;
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 10px max(12px, env(safe-area-inset-right)) 10px max(12px, env(safe-area-inset-left));
  background: rgb(255 255 255 / 97%);
  border-top: 1px solid #e2e8f0;
}
.mobile-action-bar :deep(button) { flex: 1; min-width: 0; min-height: 44px; margin: 0; }
</style>
