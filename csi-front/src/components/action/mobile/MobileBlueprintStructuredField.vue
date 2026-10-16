<template>
  <div class="blueprint-structured-field">
    <p class="field-help">{{ kind === 'conditions' ? '逐条填写条件，例如 field__gte=value；未修改的条件保持原样。' : kind === 'key-value' ? '逐项编辑配置，复杂值使用 JSON。' : '逐项添加或编辑内容。' }}</p>
    <button v-for="entry in entries" :key="entry.key" type="button" :disabled="disabled" class="structured-entry" @click="edit(entry.key)"><span><strong>{{ kind === 'key-value' ? entry.key : `第 ${Number(entry.key) + 1} 项` }}</strong><small>{{ typeof entry.value === 'string' ? entry.value : JSON.stringify(entry.value) }}</small></span><Icon icon="mdi:pencil-outline" /></button>
    <el-button :disabled="disabled" plain @click="edit(null)">添加{{ kind === 'key-value' ? '配置' : kind === 'conditions' ? '条件' : '内容' }}</el-button>
    <MobileSheet v-model="visible" :title="originalKey === null ? '添加一项' : '编辑一项'" :destroy-on-close="true">
      <el-form label-position="top" :disabled="disabled" @submit.prevent="apply">
        <el-form-item v-if="kind === 'key-value'" label="配置名称" required><el-input v-model="draftKey" /></el-form-item>
        <el-form-item v-if="kind === 'key-value' || draftMode === 'json'" label="值类型"><el-select v-model="draftMode"><el-option label="文本" value="text" /><el-option label="JSON 值" value="json" /></el-select></el-form-item>
        <el-form-item :label="draftMode === 'json' ? 'JSON 内容' : kind === 'conditions' ? '条件表达式' : '内容'" required><el-input v-model="draftValue" type="textarea" :rows="7" :placeholder="kind === 'conditions' ? 'field__gte=value' : ''" /></el-form-item>
        <p v-if="error" class="field-error" role="alert">{{ error }}</p>
      </el-form>
      <template #footer><el-button v-if="originalKey !== null" :disabled="disabled" type="danger" plain @click="remove">删除此项</el-button><el-button :disabled="disabled" @click="visible = false">取消</el-button><el-button :disabled="disabled" type="primary" @click="apply">应用</el-button></template>
    </MobileSheet>
  </div>
</template>

<script setup>
import { computed, ref, inject, watch, onBeforeUnmount } from 'vue'
import { Icon } from '@iconify/vue'
import MobileSheet from '@/components/mobile/MobileSheet.vue'
const props = defineProps({ modelValue: { type: [Array, Object], default: null }, kind: { type: String, required: true }, disabled: { type: Boolean, default: false } })
const emit = defineEmits(['update:modelValue'])
const entries = computed(() => Object.entries(props.modelValue || {}).map(([key, value]) => ({ key, value })))
const visible = ref(false), originalKey = ref(null), draftKey = ref(''), draftValue = ref(''), draftMode = ref('text'), error = ref('')
const localDrafts = inject('blueprintLocalDrafts', null), draftKeyId = Symbol('结构化字段草稿'), initialDraft = ref('')
const draftSignature = computed(() => JSON.stringify([draftKey.value, draftMode.value, draftValue.value]))
watch([visible, draftSignature], () => {
  if (visible.value && draftSignature.value !== initialDraft.value) localDrafts?.set(draftKeyId, draftSignature.value)
  else localDrafts?.delete(draftKeyId)
}, { flush: 'sync' })

/** """复制当前项到独立草稿，取消时不改变主节点。""" */
function edit(key) {
  if (props.disabled) return
  originalKey.value = key
  draftKey.value = key ?? ''
  const value = key === null ? '' : props.modelValue[key]
  draftMode.value = typeof value === 'string' ? 'text' : 'json'
  draftValue.value = draftMode.value === 'text' ? value : JSON.stringify(value, null, 2)
  error.value = ''
  initialDraft.value = draftSignature.value
  visible.value = true
}

/**
 * 校验单项后复制更新集合，保留未编辑的值和未知字段。
 * @returns {void} 无效 JSON、重复名称或空内容不会发出更新。
 */
function apply() {
  if (props.disabled || !visible.value) return
  let value = draftValue.value
  if (draftMode.value === 'json') {
    try { value = JSON.parse(draftValue.value, (_key, entry) => { if (typeof entry === 'number' && !Number.isFinite(entry)) throw new Error('数字超出有效范围'); return entry }) } catch { error.value = 'JSON 格式不正确或数字超出范围，请修改后再应用'; return }
  }
  if (props.kind === 'key-value') {
    const key = draftKey.value.trim()
    if (!key) { error.value = '请填写配置名称'; return }
    if (key !== originalKey.value && Object.hasOwn(props.modelValue || {}, key)) { error.value = '此配置名称已存在'; return }
    const next = { ...props.modelValue }
    if (originalKey.value !== null) delete next[originalKey.value]
    Object.defineProperty(next, key, { value, enumerable: true, configurable: true, writable: true })
    emit('update:modelValue', next)
  } else {
    if (typeof value === 'string' && !value.trim()) { error.value = '请填写内容'; return }
    if (props.kind === 'conditions' && typeof value === 'string' && !/^[^=]+=[\s\S]+$/.test(value)) { error.value = '条件需要字段和值，例如 field=value'; return }
    const next = [...(props.modelValue || [])]
    if (originalKey.value === null) next.push(value)
    else next[Number(originalKey.value)] = value
    emit('update:modelValue', next)
  }
  visible.value = false
}

/** """删除所选项时复制集合，不修改传入的节点资料。""" */
function remove() {
  if (props.disabled || !visible.value || originalKey.value === null) return
  const next = props.kind === 'key-value' ? { ...props.modelValue } : [...props.modelValue]
  if (props.kind === 'key-value') delete next[originalKey.value]
  else next.splice(Number(originalKey.value), 1)
  emit('update:modelValue', next)
  visible.value = false
}
onBeforeUnmount(() => { visible.value = false; localDrafts?.delete(draftKeyId) })
</script>

<style scoped>
.blueprint-structured-field { display: grid; gap: 10px; width: 100%; min-width: 0; }
.field-help { color: #64748b; font-size: 12px; line-height: 1.7; }
.structured-entry { display: flex; justify-content: space-between; gap: 12px; text-align: left; min-height: 56px; border: 1px solid #e2e8f0; border-radius: 12px; padding: 12px; background: #f8fafc; }
.structured-entry span { min-width: 0; }.structured-entry strong { font-size: 13px; display: block; color: #334155; overflow-wrap: anywhere; }.structured-entry small { display: block; font-size: 12px; color: #64748b; overflow-wrap: anywhere; max-height: 64px; overflow: hidden; }.structured-entry svg { flex-shrink: 0; color: #2563eb; }
.field-error { color: #dc2626; font-size: 13px; }.blueprint-structured-field :deep(.el-button) { min-height: 44px; }
</style>
