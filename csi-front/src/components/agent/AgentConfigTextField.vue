<template>
  <div v-if="isMobile" class="agent-config-text-field">
    <div class="agent-config-text-toolbar"><span>{{ readOnly ? '内容' : '文本内容' }}</span><el-radio-group v-if="language === 'markdown'" v-model="view" aria-label="内容显示方式"><el-radio-button v-if="!readOnly" value="edit">编辑</el-radio-button><el-radio-button value="preview">预览</el-radio-button><el-radio-button v-if="readOnly" value="source">原文</el-radio-button></el-radio-group></div>
    <MarkdownViewer v-if="view === 'preview' && language === 'markdown'" :content="modelValue || '暂无内容'" class="agent-config-text-preview" />
    <pre v-else-if="readOnly" class="agent-config-source">{{ modelValue || '暂无内容' }}</pre>
    <el-input v-else :model-value="modelValue" type="textarea" :autosize="{ minRows: 12, maxRows: 22 }" aria-label="编辑文本内容" @update:model-value="emit('update:modelValue', $event)" />
  </div>
  <MarkdownPromptField v-else-if="prompt" :model-value="modelValue" :read-only="readOnly" :min-height="minHeight" layout="toggle" @update:model-value="emit('update:modelValue', $event)" />
  <MonacoEditor v-else :model-value="modelValue" :language="language" :read-only="readOnly" :min-height="minHeight" @update:model-value="emit('update:modelValue', $event)" />
</template>
<script setup>
import { ref, watch } from 'vue'
import { useMobileViewport } from '@/composables/useMobileViewport'
import MonacoEditor from '@/components/MonacoEditor.vue'
import MarkdownPromptField from '@/components/agent/MarkdownPromptField.vue'
import MarkdownViewer from '@/components/common/MarkdownViewer.vue'
const props = defineProps({ modelValue: { type: String, default: '' }, language: { type: String, default: 'markdown' }, readOnly: Boolean, prompt: Boolean, minHeight: { type: Number, default: 360 } })
const emit = defineEmits(['update:modelValue'])
const { isMobile } = useMobileViewport()
const view = ref(props.readOnly ? 'preview' : 'edit')
watch(() => props.readOnly, value => { view.value = value ? 'preview' : 'edit' })
</script>
<style scoped>
.agent-config-text-field{width:100%;min-width:0}.agent-config-text-toolbar{display:flex;align-items:center;justify-content:space-between;gap:8px;flex-wrap:wrap;margin-bottom:12px;color:#64748b;font-size:13px}.agent-config-text-field :deep(.el-radio-button__inner){min-height:40px;padding:12px}.agent-config-text-field :deep(.el-textarea__inner){font-size:16px;line-height:1.65}.agent-config-text-preview{padding:12px;border:1px solid #e2e8f0;border-radius:10px;overflow-wrap:anywhere;min-width:0}.agent-config-source{white-space:pre-wrap;overflow-wrap:anywhere;font-size:14px;line-height:1.7}.agent-config-text-preview :deep(table){display:block;overflow-x:auto;max-width:100%}
</style>
