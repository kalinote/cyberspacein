<template>
  <div class="resource-values">
    <button v-for="(value, key) in modelValue" :key="key" type="button" :disabled="disabled" @click="edit(key)"><span><strong>{{ key }}</strong><small>{{ typeof value === 'object' ? JSON.stringify(value) : String(value) }}</small></span><Icon icon="mdi:pencil-outline" /></button>
    <el-button plain :disabled="disabled" @click="edit('')"><Icon icon="mdi:plus" />添加配置项</el-button>
    <MobileSheet v-model="visible" title="编辑配置项">
      <el-form label-position="top" @submit.prevent="apply"><el-form-item label="名称"><el-input v-model="draftKey" /></el-form-item><el-form-item label="值类型"><el-select v-model="valueType"><el-option v-for="option in TYPED_VALUE_OPTIONS" :key="option.value" :label="option.label" :value="option.value" /></el-select></el-form-item><el-form-item label="值"><el-input v-model="draftValue" type="textarea" :rows="5" /></el-form-item><p v-if="error" role="alert" class="text-red-600 text-sm">{{ error }}</p></el-form>
      <template #footer><el-button v-if="originalKey" type="danger" plain @click="remove">删除此项</el-button><el-button type="primary" @click="apply">应用此项</el-button></template>
    </MobileSheet>
  </div>
</template>

<script setup>
import { ref, onBeforeUnmount } from 'vue'
import { Icon } from '@iconify/vue'
import MobileSheet from '@/components/mobile/MobileSheet.vue'
import { TYPED_VALUE_OPTIONS, inferValueType, parseTypedValue, valueToEditString } from '@/utils/typedKeyValue'
const props = defineProps({ modelValue: { type: Object, default: () => ({}) }, disabled: { type: Boolean, default: false } })
const emit = defineEmits(['update:modelValue'])
const visible = ref(false), originalKey = ref(''), draftKey = ref(''), draftValue = ref(''), valueType = ref('string'), error = ref('')
/** """单独编辑一项草稿，关闭面板不会写入主表单。""" */
function edit(key) {
  if (props.disabled) return
  originalKey.value = key
  draftKey.value = key
  valueType.value = key ? inferValueType(props.modelValue[key]) : 'string'
  draftValue.value = key ? valueToEditString(props.modelValue[key], valueType.value) : ''
  error.value = ''
  visible.value = true
}
/** """校验名称及类型后应用到主表单，不覆盖同名配置。""" */
function apply() {
  if (props.disabled) return
  const key = draftKey.value.trim()
  if (!key) { error.value = '请填写配置名称'; return }
  if (key !== originalKey.value && Object.hasOwn(props.modelValue, key)) { error.value = '此名称已存在'; return }
  const parsed = parseTypedValue(draftValue.value, valueType.value)
  if (!parsed.ok) { error.value = parsed.error; return }
  if (typeof parsed.value === 'number' && !Number.isFinite(parsed.value)) { error.value = '请输入有限数字'; return }
  const next = { ...props.modelValue }
  if (originalKey.value) delete next[originalKey.value]
  Object.defineProperty(next, key, { value: parsed.value, enumerable: true, configurable: true, writable: true })
  emit('update:modelValue', next)
  visible.value = false
}
/** """从当前草稿移除所选配置项，仍需主表单保存才会生效。""" */
function remove() {
  if (props.disabled) return
  const next = { ...props.modelValue }
  delete next[originalKey.value]
  emit('update:modelValue', next)
  visible.value = false
}
onBeforeUnmount(() => { visible.value = false })
</script>

<style scoped>
.resource-values { width: 100%; display: grid; gap: 8px; }
.resource-values > button:not(.el-button) { display: flex; align-items: center; justify-content: space-between; gap: 10px; width: 100%; text-align: left; min-height: 52px; padding: 10px; border-radius: 9px; border: 1px solid #e2e8f0; background: #f8fafc; }
.resource-values span { min-width: 0; }
.resource-values strong { display: block; overflow-wrap: anywhere; font-size: 13px; }
.resource-values small { display: block; color: #64748b; max-height: 40px; overflow: hidden; overflow-wrap: anywhere; }
.resource-values svg { flex-shrink: 0; color: #2563eb; }
</style>
