<template>
  <div class="mobile-blueprint-node-fields">
    <p v-if="!groups.length" class="node-fields-empty">此节点没有可编辑参数。</p>
    <details v-for="(group, index) in groups" :key="group.key" :open="index === 0" class="node-field-group">
      <summary>{{ group.label }} <span>{{ group.inputs.filter(input => input.type !== 'comment').length }} 项</span></summary>
      <div class="node-field-group-content"><InputRenderer v-for="input in group.inputs" :key="`${node.id}:${input.id}`" :input-config="input" :model-value="node.data?.[input.id]" :node-id="node.id" :disabled="disabled" @update:model-value="changeField(input.id, $event)" /></div>
    </details>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import InputRenderer from '@/components/action/nodes/components/InputRenderer.vue'
const props = defineProps({ node: { type: Object, required: true }, disabled: { type: Boolean, default: false } })
const emit = defineEmits(['field-change'])
const visibleInputs = computed(() => (props.node?.data?.config?.inputs || []).filter(input => !input.custom_props?.hide_when_boundary_bound || !props.node?.data?.boundaryBinding))
const groups = computed(() => {
  const result = []
  let current = null
  for (const input of visibleInputs.value) {
    if (!current || input.type === 'comment') {
      current = { key: input.id, label: input.type === 'comment' ? input.label || '说明与配置' : '节点参数', inputs: [] }
      result.push(current)
    }
    current.inputs.push(input)
  }
  return result
})

/** """只提交可见且可编辑的字段值，节点其它资料交由主控保留。""" */
function changeField(inputId, value) {
  if (props.disabled || !visibleInputs.value.some(input => input.id === inputId && input.type !== 'comment')) return
  emit('field-change', { inputId, value })
}
</script>

<style scoped>
.mobile-blueprint-node-fields { display: grid; gap: 14px; min-width: 0; }
.node-field-group { border: 1px solid #e2e8f0; border-radius: 14px; background: white; min-width: 0; }
.node-field-group summary { min-height: 50px; padding: 14px; font-size: 14px; font-weight: 650; color: #334155; cursor: pointer; overflow-wrap: anywhere; }.node-field-group summary span { color: #94a3b8; margin-left: 8px; font-size: 12px; font-weight: 400; }
.node-field-group-content { padding: 0 14px 14px; display: grid; gap: 18px; }.node-fields-empty { padding: 20px; color: #64748b; font-size: 14px; text-align: center; }
</style>
