<template><div class="agent-config-json-field w-full"><p class="text-xs text-gray-500 mb-2">可填写数值、布尔值、数组或嵌套配置。修改后检查格式再保存。</p><el-input v-model="text" type="textarea" :autosize="{ minRows: 6, maxRows: 16 }" aria-label="LLM 配置 JSON" @input="updateValue" /><p v-if="error" class="text-sm text-red-600 mt-2" role="alert">{{ error }}</p></div></template>
<script setup>
import { ref, watch } from 'vue'
const props = defineProps({ modelValue: { type: Object, default: () => ({}) } })
const emit = defineEmits(['update:modelValue', 'validity-change'])
const text = ref(JSON.stringify(props.modelValue, null, 2))
const error = ref('')
let emitted = ''
/** """只同步有效对象，保留错误输入并通知表单禁止提交。""" */
function updateValue() {
  try {
    const value = JSON.parse(text.value.trim() || '{}')
    if (!value || typeof value !== 'object' || Array.isArray(value)) throw new Error('请填写 JSON 对象，例如 {"temperature": 0.2}')
    emitted = JSON.stringify(value)
    error.value = ''
    emit('update:modelValue', value)
    emit('validity-change', true)
  } catch (cause) {
    error.value = cause instanceof SyntaxError ? 'JSON 格式有误，请检查引号、逗号和括号' : cause.message
    emit('validity-change', false)
  }
}
watch(() => props.modelValue, value => {
  if (JSON.stringify(value) === emitted) return
  text.value = JSON.stringify(value, null, 2)
  error.value = ''
  emit('validity-change', true)
}, { deep: true })
</script>
