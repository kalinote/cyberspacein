<template>
  <component
    :is="isMobile ? ElDrawer : ElDialog"
    v-bind="$attrs"
    v-model="visible"
    :title="title"
    :class="{ 'agent-config-mobile-panel': isMobile }"
    :modal-class="isMobile ? 'agent-config-mobile-overlay' : undefined"
    :size="isMobile ? '100%' : undefined"
    :append-to-body="isMobile"
    :before-close="beforeClose"
    @open="beginSession"
  >
    <template v-if="isMobile || $slots.header" #header="scope">
      <div v-if="isMobile" class="agent-config-panel-heading"><el-button :disabled="busy" @click="requestClose">返回</el-button><div><h2>{{ title }}</h2><p v-if="dirty">有未保存的修改</p></div></div>
      <slot v-if="$slots.header" name="header" v-bind="scope" />
    </template>
    <slot />
    <template v-if="$slots.footer || isMobile" #footer>
      <slot name="footer" :close="requestClose"><el-button @click="requestClose">返回列表</el-button></slot>
    </template>
  </component>
</template>

<script setup>
import { computed, nextTick, onDeactivated, ref, watch } from 'vue'
import { onBeforeRouteLeave } from 'vue-router'
import { ElDialog, ElDrawer, ElMessageBox } from 'element-plus'
import { useMobileViewport } from '@/composables/useMobileViewport'

defineOptions({ inheritAttrs: false })
const props = defineProps({ title: { type: String, default: '' }, draft: { default: null }, busy: Boolean })
const visible = defineModel({ type: Boolean, default: false })
const { isMobile, keyboardOpen, viewportHeight } = useMobileViewport()
const baseline = ref('null')
const dirty = computed(() => isMobile.value && props.draft !== null && JSON.stringify(props.draft) !== baseline.value)
let awaitingInitialData = false

/** """记录打开时的表单，异步详情只在首次加载完成时更新基线。""" */
function beginSession() {
  baseline.value = JSON.stringify(props.draft)
  awaitingInitialData = props.busy
}

/** """手机关闭或离页前保护尚未保存的表单。""" */
async function allowClose() {
  if (!isMobile.value || !visible.value) return true
  if (props.busy) return false
  if (!dirty.value) return true
  try {
    await ElMessageBox.confirm('当前配置有未保存修改，确定放弃？', '未保存修改', { confirmButtonText: '放弃修改', cancelButtonText: '继续编辑', type: 'warning' })
    return true
  } catch { return false }
}

/** """统一返回按钮与页脚取消操作的关闭语义。""" */
async function requestClose() {
  if (await allowClose()) visible.value = false
}

/** """在抽屉自身的关闭入口执行同一草稿检查。""" */
async function beforeClose(done) {
  if (await allowClose()) done()
}

watch(() => props.busy, busy => {
  if (!busy && visible.value && awaitingInitialData) {
    baseline.value = JSON.stringify(props.draft)
    awaitingInitialData = false
  }
})
watch([keyboardOpen, viewportHeight], async ([open]) => {
  if (!open || !visible.value || !isMobile.value) return
  await nextTick()
  const field = document.activeElement
  if (field instanceof HTMLElement && field.closest('.agent-config-mobile-panel') && field.matches('input,textarea')) field.scrollIntoView({ block: 'nearest' })
})
onBeforeRouteLeave(allowClose)
onDeactivated(() => { visible.value = false })
</script>

<style>
@media(max-width:767px){
  .agent-config-mobile-overlay{top:var(--mobile-viewport-top,0px);height:var(--mobile-viewport-height,100dvh);bottom:auto}
  /* 抽屉仅平移动画，键盘改变高度时立即完成布局，避免焦点滚动使用过渡中的旧高度。 */
  .agent-config-mobile-panel.el-drawer{height:var(--mobile-viewport-height,100dvh);width:100%;max-width:100%;display:flex;flex-direction:column;border-radius:0;transition-property:transform}
  .agent-config-mobile-panel .el-drawer__header{margin:0;padding:12px 16px;border-bottom:1px solid #e2e8f0;flex-shrink:0}
  .agent-config-mobile-panel .el-drawer__close-btn{display:none}
  .agent-config-panel-heading{display:flex;align-items:center;gap:12px;min-width:0;width:100%}
  .agent-config-panel-heading>div{min-width:0}.agent-config-panel-heading h2{font-size:18px;font-weight:650;line-height:1.4;overflow-wrap:anywhere;margin:0}.agent-config-panel-heading p{font-size:12px;color:#b45309;margin:4px 0 0}
  .agent-config-mobile-panel .el-drawer__body{min-height:0;padding:16px;overflow-y:auto;overflow-x:hidden;overscroll-behavior:contain}
  .agent-config-mobile-panel .el-drawer__footer{display:flex;gap:8px;padding:12px 16px max(12px,env(safe-area-inset-bottom));border-top:1px solid #e2e8f0;flex-shrink:0}
  .agent-config-mobile-panel .el-drawer__footer>.el-button{flex:1;margin:0;min-width:0}
  .agent-config-mobile-panel .el-button{min-height:44px;white-space:normal}
  .agent-config-mobile-panel .el-form-item{display:block;margin-bottom:22px}.agent-config-mobile-panel .el-form-item__label{width:auto!important;line-height:1.5;height:auto;justify-content:flex-start;margin-bottom:8px;white-space:normal}.agent-config-mobile-panel .el-form-item__content{margin-left:0!important;display:block;min-width:0}
  .agent-config-mobile-panel .el-input__wrapper,.agent-config-mobile-panel .el-select__wrapper{min-height:44px}.agent-config-mobile-panel .el-input__inner,.agent-config-mobile-panel .el-textarea__inner{font-size:16px}.agent-config-mobile-panel .el-select{width:100%}
  /* 覆盖 autosize 的行数下限，键盘弹出后在文本框内滚动到输入位置。 */
  .agent-config-mobile-panel .agent-config-text-field .el-textarea__inner,.agent-config-mobile-panel .agent-config-json-field .el-textarea__inner{min-height:96px!important;max-height:clamp(96px,calc(var(--mobile-viewport-height,100dvh) - 240px),360px)!important;overflow-y:auto!important;overscroll-behavior:contain;resize:none}
  .agent-config-mobile-panel .el-descriptions__table{table-layout:fixed;width:100%}.agent-config-mobile-panel .el-descriptions__cell{overflow-wrap:anywhere}.agent-config-mobile-panel pre{white-space:pre-wrap;overflow-wrap:anywhere;max-width:100%}
  .agent-config-mobile-panel .el-upload,.agent-config-mobile-panel .el-upload-dragger{width:100%}.agent-config-mobile-panel .el-tabs__item{min-height:44px}
  .agent-config-mobile-panel.sandbox-browser-dialog .el-drawer__body{display:flex;min-height:0}.agent-config-mobile-panel.sandbox-browser-dialog .el-drawer__body>div{flex:1;width:100%}
}
</style>
