<template>
  <el-drawer
    v-model="visible"
    :title="title"
    direction="btt"
    size="auto"
    class="mobile-sheet"
    modal-class="mobile-sheet-overlay"
    append-to-body
    :destroy-on-close="destroyOnClose"
  >
    <slot />
    <template v-if="$slots.footer" #footer><slot name="footer" /></template>
  </el-drawer>
</template>

<script setup>
defineProps({ title: { type: String, required: true }, destroyOnClose: { type: Boolean, default: false } })
const visible = defineModel({ type: Boolean, default: false })
</script>

<style>
.mobile-sheet-overlay {
  top: var(--mobile-viewport-top, 0px);
  bottom: auto;
  height: var(--mobile-viewport-height, 100dvh);
}
.mobile-sheet.el-drawer {
  max-height: calc(var(--mobile-viewport-height, 100dvh) - 16px);
  border-radius: 22px 22px 0 0;
}
.mobile-sheet .el-drawer__header { margin-bottom: 0; padding: 20px 20px 12px; color: #0f172a; font-weight: 700; }
.mobile-sheet .el-drawer__header, .mobile-sheet .el-drawer__footer { flex-shrink: 0; }
.mobile-sheet .el-drawer__close-btn { min-width: 44px; min-height: 44px; }
.mobile-sheet .el-drawer__body { min-height: 0; overflow-y: auto; overscroll-behavior: contain; padding: 12px 20px max(20px, env(safe-area-inset-bottom)); }
.mobile-sheet .el-drawer__footer { padding: 12px 20px max(16px, env(safe-area-inset-bottom)); border-top: 1px solid #e2e8f0; }
.mobile-sheet .el-drawer__footer .el-button { min-height: 44px; }
</style>
